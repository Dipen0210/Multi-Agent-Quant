import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from api.main import app
from agent.nodes.critic.node import critic_node
from agent.nodes.risk_manager.node import risk_manager_node
from agent.schemas import FinancialNewsOutput, PortfolioSignal, RiskDecision, MacroContextOutput


def source(direction='bullish'):
    return FinancialNewsOutput(decision=direction, sentiment_label=direction, sentiment_score=.8,
        headline_count=1, headlines=['fixture'], keywords=[], reasoning='fixture')


def state(confidence=.8):
    return {'ticker':'AAPL', 'portfolio_signal':PortfolioSignal(signal='BUY', confidence=confidence,
        bull_case='fixture',bear_case='fixture',resolution='fixture'),
        'risk_decision':RiskDecision(decision='APPROVED', original_size=1,adjusted_size=1,
            stop_loss_pct=.05,stop_loss_price=95,reason='fixture'),
        'financial_news':source(), 'reddit_sentiment':source(), 'sec_filing':source(),
        'analyst_ratings':source('neutral')}


class BaselineTests(unittest.TestCase):
    def test_api_health_and_order_isolation(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict('os.environ',{'RESEARCH_DB':str(Path(directory)/'baseline.sqlite3')}), TestClient(app) as client, patch('agent.tools.alpaca_tool._get_client') as broker:
            self.assertEqual(client.get('/health').status_code,200)
            self.assertEqual(client.post('/trade',json={'ticker':'AAPL','side':'buy','shares':1,'stop_loss':1}).status_code,403)
            broker.assert_not_called()
        from agent.tools.alpaca_tool import place_order
        with self.assertRaisesRegex(RuntimeError,'disabled'):
            place_order('AAPL','buy',1,95)

    @patch.dict('os.environ',{},clear=True)
    def test_critic_requires_both_gates_and_risk(self):
        self.assertEqual(critic_node(state())['critic_decision'].decision,'PROCEED')
        for change in ['confidence','agreement','missing_risk','missing_sources']:
            s=state()
            if change=='confidence': s['portfolio_signal']=state(.2)['portfolio_signal']
            if change=='agreement':
                s.update({key:source('neutral') for key in ['financial_news','reddit_sentiment','sec_filing']})
            if change=='missing_risk': s.pop('risk_decision')
            if change=='missing_sources':
                for key in ['financial_news','reddit_sentiment','sec_filing','analyst_ratings']: s.pop(key)
            with self.subTest(change=change):
                self.assertEqual(critic_node(s)['critic_decision'].decision,'HOLD')

    def test_inference_failure_is_not_neutral(self):
        from agent.tools.finbert_tool import score_headlines
        with patch('agent.tools.finbert_tool._get_pipeline',side_effect=RuntimeError('failure')):
            with self.assertRaisesRegex(RuntimeError,'inference failed'): score_headlines(['fixture'])

    def test_market_failure_is_not_invented_data(self):
        from agent.tools.yfinance_tool import get_market_indices
        with patch('agent.tools.yfinance_tool.yf.Ticker',side_effect=RuntimeError('offline')):
            with self.assertRaises(RuntimeError): get_market_indices()

    def test_risk_remaining_capacity_and_missing_inputs(self):
        macro=MacroContextOutput(vix=15,yield_10yr=4,spy_5d_return=.01,dxy=100,
            fed_stance='neutral',risk_environment='risk_on',market_trend='neutral',
            sentiment_score=.5,sentiment_label='neutral')
        s={'ticker':'AAPL','macro_context':macro}
        module='agent.nodes.risk_manager.node.'
        with patch(module+'_get_portfolio_value',return_value=10000), patch(module+'_get_exposure',return_value=.09), patch(module+'get_current_price',return_value=50):
            result=risk_manager_node(s)['risk_decision']
            self.assertLessEqual(result.adjusted_size*50,100.000001)
        with patch(module+'_get_exposure',side_effect=ValueError('missing')):
            self.assertEqual(risk_manager_node(s)['risk_decision'].decision,'VETOED')
        with patch(module+'_get_portfolio_value',return_value=100), patch(module+'_get_exposure',return_value=0), patch(module+'get_current_price',return_value=50):
            self.assertEqual(risk_manager_node(s)['risk_decision'].adjusted_size,0)

    def test_chunking_terminates(self):
        from agent.tools.sec_edgar_tool import chunk_filing_text
        with self.assertRaises(ValueError): chunk_filing_text('word '*100,50,50)
