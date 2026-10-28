from datetime import datetime, timedelta, timezone
import math
import unittest
from research.simulation import SimulationPolicy, SimulationSignal, simulate, chronological_partitions
from test_data import bar


def signal(at='2025-01-02T22:00:00Z',action='LONG'):
    return {'instrument_id':'US:AAPL','decision_at':at,'information_cutoff':at,'action':action}


class SimulationTests(unittest.TestCase):
    def test_cash_fees_positions_and_next_open(self):
        policy=SimulationPolicy(initial_cash=10000,max_position_fraction=.1,fee_bps=10,spread_bps=10,slippage_bps=10)
        result=simulate([bar('2025-01-03'),bar('2025-01-06')],[signal(),signal('2025-01-03T22:00:00Z','FLAT')],policy,initial_previous=bar('2025-01-02'))
        orders=[o for o in result['orders'] if o['status']=='filled']
        self.assertEqual(len(orders),2)
        buy,sell=orders
        self.assertEqual(buy['side'],'buy');self.assertEqual(sell['side'],'sell')
        self.assertLess(datetime.fromisoformat(buy['decision_at']),datetime.fromisoformat(buy['execution_at']))
        expected=10000-buy['quantity']*buy['price']-buy['fee']+sell['quantity']*sell['price']-sell['fee']
        self.assertAlmostEqual(result['end_position']['cash'],expected)
        self.assertEqual(result['end_position']['shares'],0)
        self.assertGreater(result['metrics']['fees'],0)
        self.assertLess(result['metrics']['total_return'],0)
        for point in result['equity_curve']: self.assertAlmostEqual(point['equity'],point['cash']+point['shares']*point['close'])

    def test_no_same_bar_or_pre_signal_fills(self):
        result=simulate([bar('2025-01-03'),bar('2025-01-06')],[signal('2025-01-03T14:30:00Z')],initial_previous=bar('2025-01-02'))
        self.assertEqual(result['orders'][0]['execution_at'],'2025-01-06T14:30:00+00:00')
        with self.assertRaises(ValueError): SimulationSignal(**(signal()|{'information_cutoff':'2025-01-04T00:00:00Z'}))

    def test_missing_liquidity_and_zero_volume_prevent_fills(self):
        result=simulate([bar('2025-01-03')],[signal()])
        self.assertEqual(result['metrics']['filled_orders'],0)
        result=simulate([bar('2025-01-03',volume=1000000)],[signal()],initial_previous=bar('2025-01-02',volume=0))
        self.assertEqual(result['metrics']['filled_orders'],0)
        self.assertEqual(result['end_position']['cash'],100000)

    def test_late_market_availability_and_gaps_rejected(self):
        previous=bar('2025-01-02',available_at='2025-01-04T00:00:00Z')
        self.assertEqual(simulate([bar('2025-01-03')],[signal()],initial_previous=previous)['metrics']['filled_orders'],0)
        with self.assertRaisesRegex(ValueError,'Missing market session'):
            simulate([bar('2025-01-03'),bar('2025-01-07')],[])

    def test_adjustments_and_cash_benchmark(self):
        with self.assertRaises(ValueError): simulate([bar(adjustment_policy='total_return')],[])
        with self.assertRaises(ValueError): simulate([bar(provenance='historical_approximate')],[])
        result=simulate([bar('2025-01-03'),bar('2025-01-06')],[])
        self.assertEqual(result['metrics']['total_return'],0)
        self.assertIsNone(result['metrics']['sharpe_ratio'])
        self.assertEqual(result['validity_tier'],'synthetic_pipeline')

    def test_partition_boundaries_and_embargo(self):
        sessions=[f'2025-01-{day:02d}' for day in range(1,31)]
        split=chronological_partitions(sessions,'2025-01-10','2025-01-20','2025-01-21',2)
        self.assertEqual(split['train'][-1],'2025-01-08')
        self.assertEqual(split['validation'][0],'2025-01-13')
        self.assertEqual(split['test'][0],'2025-01-23')
        self.assertFalse(set(split['train'])&set(split['test']))
        with self.assertRaises(ValueError): chronological_partitions(sessions,'2025-01-20','2025-01-10','2025-01-21')
