"""Bounded, process-local request admission for the single-user deployment.

All clients share limits; proxy headers cannot create new buckets. Cancellation
has its own allowance so starting or polling jobs cannot consume it. Limits reset
on process restart and are not a distributed/multi-user quota system.
"""
from collections import deque
import math
import os
import re
import threading
import time


class RequestLimiter:
    WINDOW_SECONDS = 60
    DEFAULTS = {'read': 600, 'write': 120, 'start': 60, 'cancel': 60}

    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.limits = {}
        for category, default in self.DEFAULTS.items():
            name = f'RESEARCH_RATE_{category.upper()}_PER_MINUTE'
            try:
                value = int(os.getenv(name, str(default)))
            except ValueError as exc:
                raise ValueError(f'{name} must be an integer from 1 to 10000') from exc
            if not 1 <= value <= 10000:
                raise ValueError(f'{name} must be an integer from 1 to 10000')
            self.limits[category] = value
        self.requests = {category: deque() for category in self.limits}
        self.lock = threading.Lock()

    @staticmethod
    def category(method, path):
        # Health and the always-denied trade endpoint do no research work.
        if (method == 'GET' and path == '/health') or path == '/trade':
            return None
        if method == 'POST':
            if re.fullmatch(r'/api/(runs|studies)/[^/]+/cancel/?', path):
                return 'cancel'
            if path.rstrip('/') in {'/api/runs', '/api/evaluations', '/api/experiments'} or re.fullmatch(r'/api/runs/[^/]+/retry/?', path):
                return 'start'
        return 'read' if method in {'GET', 'HEAD', 'OPTIONS'} else 'write'

    def admit(self, method, path):
        category = self.category(method, path)
        if category is None:
            return None
        with self.lock:
            current = self.clock()
            entries = self.requests[category]
            while entries and entries[0] <= current - self.WINDOW_SECONDS:
                entries.popleft()
            if len(entries) >= self.limits[category]:
                return {'category': category,
                        'retry_after_seconds': max(1, math.ceil(entries[0] + self.WINDOW_SECONDS - current))}
            entries.append(current)
        return None
