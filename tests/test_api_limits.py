from concurrent.futures import ThreadPoolExecutor
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.boundaries import RequestBoundary
from api.rate_limits import RequestLimiter


class RequestLimitTests(unittest.TestCase):
    def test_rolling_window_rejects_until_oldest_request_expires(self):
        current = [100.0]
        with patch.dict('os.environ', {'RESEARCH_RATE_START_PER_MINUTE': '2'}):
            limiter = RequestLimiter(clock=lambda: current[0])
        self.assertIsNone(limiter.admit('POST', '/api/runs'))
        current[0] = 110.0
        self.assertIsNone(limiter.admit('POST', '/api/evaluations'))
        denied = limiter.admit('POST', '/api/experiments')
        self.assertEqual(denied, {'category': 'start', 'retry_after_seconds': 50})
        current[0] = 159.9
        self.assertEqual(limiter.admit('POST', '/api/runs')['retry_after_seconds'], 1)
        current[0] = 160.0
        self.assertIsNone(limiter.admit('POST', '/api/runs/example/retry'))
        self.assertIsNotNone(limiter.admit('POST', '/api/runs/'))

    def test_concurrent_clients_share_bounded_capacity(self):
        with patch.dict('os.environ', {'RESEARCH_RATE_WRITE_PER_MINUTE': '3'}):
            limiter = RequestLimiter(clock=lambda: 0)
        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(lambda _: limiter.admit('POST', '/api/imports'), range(50)))
        self.assertEqual(sum(result is None for result in results), 3)
        self.assertEqual(len(limiter.requests['write']), 3)

    def test_api_limits_before_handler_and_reserves_cancellation(self):
        calls = []
        app = FastAPI()
        app.add_middleware(RequestBoundary)

        @app.api_route('/{path:path}', methods=['GET', 'POST'])
        def endpoint(path: str):
            calls.append(path)
            return {'ok': True}

        limits = {f'RESEARCH_RATE_{key}_PER_MINUTE': '1' for key in ['READ', 'WRITE', 'START', 'CANCEL']}
        with patch.dict('os.environ', limits), TestClient(app) as client:
            self.assertEqual(client.post('/api/runs', json={}).status_code, 200)
            response = client.post('/api/runs/r/retry', json={}, headers={'X-Forwarded-For': 'different-client'})
            self.assertEqual(response.status_code, 429)
            self.assertEqual(response.json()['error']['code'], 'rate_limited')
            self.assertGreater(int(response.headers['Retry-After']), 0)
            self.assertNotIn('api/runs/r/retry', calls)
            self.assertEqual(client.get('/api/runs/r').status_code, 200)
            self.assertEqual(client.get('/api/studies').status_code, 429)
            self.assertEqual(client.post('/api/imports', json={}).status_code, 200)
            self.assertEqual(client.post('/api/demo/import', json={}).status_code, 429)
            self.assertEqual(client.post('/api/runs/r/cancel', json={}).status_code, 200)
            self.assertEqual(client.post('/api/studies/s/cancel', json={}).status_code, 429)
            self.assertEqual(client.get('/health').status_code, 200)
            # Exemption preserves the production route's unconditional denial.
            self.assertIsNone(RequestLimiter.category('POST', '/trade'))

    def test_invalid_configuration_fails_closed(self):
        for value in ['0', '-1', '10001', 'nan', '1.5']:
            with self.subTest(value=value), patch.dict('os.environ', {'RESEARCH_RATE_READ_PER_MINUTE': value}):
                with self.assertRaises(ValueError):
                    RequestLimiter()
