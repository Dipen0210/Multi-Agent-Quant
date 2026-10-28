from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import tempfile
import unittest
from research.contracts import Document, MarketObservation, SnapshotRequest
from research.store import Store
from research.calendar import session_times
from research.importers import parse_csv


def doc(**changes):
    data=dict(provider='fixture',original_id='news-1',revision=1,title='Synthetic company news',
        content='Apple reported higher earnings in this fictional test scenario.',instrument_ids=['US:AAPL'],
        published_at='2025-01-03T15:00:00Z',first_observed_at='2025-01-03T15:01:00Z',
        provenance='synthetic',usage_restrictions='Synthetic test fixture, no market claims')
    return data | changes


def bar(day='2025-01-03', **changes):
    start,end=session_times(day)
    return dict(instrument_id='US:AAPL',provider='fixture',original_id='AAPL-'+day,revision=1,
        interval_start=start.isoformat(),interval_end=end.isoformat(),available_at=(end+timedelta(minutes=1)).isoformat(),
        open=100,high=102,low=99,close=101,volume=10000,adjustment_policy='raw',
        provenance='synthetic',usage_restrictions='Synthetic test prices') | changes


class DataTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.store=Store(Path(self.temp.name)/'db.sqlite3')
        self.request=SnapshotRequest(instrument_ids=['US:AAPL'],cutoff='2025-01-03T22:00:00Z')
    def tearDown(self): self.temp.cleanup()

    def test_idempotency_and_revision_immutability(self):
        first=self.store.import_records([doc()],[bar()])
        again=self.store.import_records([doc()],[bar()])
        self.assertEqual(first['inserted'],2)
        self.assertEqual(again['duplicates'],2)
        conflict=self.store.import_records([doc(content='changed')])
        self.assertEqual(len(conflict['rejected']),1)
        with self.store.connect() as c:
            with self.assertRaises(sqlite3.IntegrityError): c.execute("UPDATE documents SET content_hash='bad'")

    def test_cutoff_filters_availability_not_publication_and_preserves_old_revision(self):
        first=self.store.import_records([doc()])['document_ids'][0]
        late=doc(original_id='late',first_observed_at='2025-01-04T15:00:00Z')
        revised=doc(revision=2,content='Later corrected negative earnings.',published_at='2025-01-04T15:00:00Z',first_observed_at='2025-01-04T15:01:00Z')
        self.store.import_records([late,revised],[bar()])
        snap=self.store.snapshot(self.request)
        self.assertEqual(snap['manifest']['document_ids'],[first])
        self.assertEqual(snap,self.store.snapshot(self.request))
        later=self.store.snapshot(self.request.model_copy(update={'cutoff':datetime(2025,1,5,tzinfo=timezone.utc)}))
        self.assertNotIn(first,later['manifest']['document_ids'])
        self.assertEqual(self.store.get_snapshot(snap['id'])['manifest']['document_ids'],[first])

    def test_duplicate_evidence_keeps_provenance(self):
        self.store.import_records([doc(),doc(original_id='syndicated',provider='other')])
        snap=self.store.snapshot(self.request)
        self.assertEqual(len(snap['manifest']['document_ids']),2)
        self.assertEqual(len(snap['manifest']['duplicate_groups']),1)

    def test_missing_observation_requires_disclosed_approximation(self):
        with self.assertRaises(ValueError): Document(**doc(first_observed_at=None))
        value=Document(**doc(first_observed_at=None,provenance='historical_approximate',latency_assumption_seconds=3600))
        self.assertEqual(value.available_at.hour,16)

    def test_invalid_inputs_quarantined_and_no_raw_secrets_retained(self):
        bad=[doc(published_at='2025-01-03T15:00:00'),doc(instrument_ids=['UNKNOWN']),doc(first_observed_at='2024-01-01T00:00:00Z')]
        result=self.store.import_records(bad,[bar(close=float('nan')),bar(open=-1),bar(high=1)])
        self.assertEqual(len(result['rejected']),6)
        self.assertEqual(result['inserted'],0)
        with self.store.connect() as c: self.assertEqual(c.execute('SELECT count(*) FROM rejections').fetchone()[0],6)

    def test_calendar_holiday_early_close_and_dst(self):
        with self.assertRaises(ValueError): session_times('2025-01-01')
        with self.assertRaises(ValueError): session_times('2025-01-04')
        self.assertEqual(session_times('2025-11-28')[1].hour,18)
        self.assertEqual(session_times('2025-03-07')[0].hour,14)
        self.assertEqual(session_times('2025-03-10')[0].hour,13)
        with self.assertRaises(ValueError): MarketObservation(**bar(interval_end='2025-01-03T20:00:00Z'))

    def test_stale_unresolved_and_wrong_entity_excluded(self):
        self.store.import_records([doc(entity_status='ambiguous'),doc(original_id='other',instrument_ids=['US:MSFT']),
            doc(original_id='old',published_at='2024-01-01T00:00:00Z',first_observed_at='2024-01-01T01:00:00Z')],
            [bar(quality_flags=['stale'])])
        snap=self.store.snapshot(self.request)
        self.assertEqual(snap['manifest']['document_ids'],[])
        self.assertEqual(snap['manifest']['market_ids'],[])

    def test_csv_import_and_content_bounds(self):
        rows=parse_csv('provider,original_id,revision,instrument_ids\nfixture,id,1,"[""US:AAPL""]"\n','documents')
        self.assertEqual(rows[0]['instrument_ids'],['US:AAPL'])
        with self.assertRaises(ValueError): parse_csv('x'*2000001,'documents')
        with self.assertRaises(ValueError): self.store.import_records([doc()]*501)

    def test_near_duplicate_and_revision_order(self):
        text=' '.join('token'+str(i) for i in range(150))
        self.store.import_records([doc(content=text),doc(original_id='syndicated-near',content=text.replace('token100','replacement'))])
        snap=self.store.snapshot(self.request)
        self.assertEqual(len(snap['manifest']['duplicate_groups']),1)
        bad=self.store.import_records([doc(revision=2,published_at='2025-01-02T15:00:00Z',first_observed_at='2025-01-02T15:01:00Z')])
        self.assertEqual(len(bad['rejected']),1)

    def test_recorded_provider_adapters_do_not_invent_publication_times(self):
        from research.adapters import normalize_text,normalize_yfinance
        capture=datetime(2025,1,3,17,tzinfo=timezone.utc)
        with self.assertRaises(ValueError):
            normalize_text('tavily',{'title':'Apple earnings','content':'Apple grew.','url':'https://example.com/news'},['US:AAPL'],capture,'Local authorized research')
        news=normalize_text('tavily',{'title':'Apple earnings','content':'Apple grew.','url':'https://example.com/news','published_at':'2025-01-03T16:00:00Z'},['US:AAPL'],capture,'Local authorized research')
        self.assertEqual(news['provenance'],'recorded')
        market=normalize_yfinance({'session':'2025-01-03','Open':100,'High':102,'Low':99,'Close':101,'Volume':10000,'adjustment_policy':'split_adjusted'},'US:AAPL',60,'Local research')
        self.assertEqual(market['provenance'],'historical_approximate')
        self.assertEqual(market['available_at'],'2025-01-03T21:01:00Z')
