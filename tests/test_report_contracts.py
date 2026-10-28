from copy import deepcopy
import json
from types import SimpleNamespace
from unittest.mock import patch

from research.configuration import Configuration, register
from research.jobs import Jobs
from research.outputs import validate_output
from research.reports import ReportSnapshot
from research.store import digest
from workflow_support import WorkflowFixture


class ReportContractTests(WorkflowFixture):
    def test_nested_report_corruption_is_rejected(self):
        report=self.wait(self.submit()['id'])['report']
        validate_output('report',{'report':report})
        changes=[
            (('findings',),{}),
            (('findings','US:AAPL','quantitative','last_close'),float('nan')),
            (('findings','US:AAPL','quantitative','observation_id'),'a'*64),
            (('findings','US:AAPL','quantitative','available_at'),'2026-01-01T00:00:00Z'),
            (('findings','US:AAPL','sentiment','independent_sources'),99),
            (('findings','US:AAPL','research_signal','signal'),'LONG'),
            (('findings','US:AAPL','counterevidence'),[]),
            (('external_execution',),True),
            (('external_execution',),0),
            (('execution_mode',),'real_local_inference'),
            (('snapshot','id'),'a'*64),
            (('status',),'completed'),
            (('trace_reference',),'/api/runs/wrong/steps'),
        ]
        for path,value in changes:
            with self.subTest(path=path,value=value):
                changed=deepcopy(report);node=changed
                for key in path[:-1]: node=node[key]
                node[path[-1]]=value
                with self.assertRaises(ValueError): validate_output('report',{'report':changed})

    def test_api_refuses_corrupted_stored_report_without_echoing_content(self):
        run=self.wait(self.submit()['id'])
        report=deepcopy(run['report']);report['configuration_id']='a'*64
        report['question']='private fixture marker must not appear in an error'
        with self.client.app.state.store.connect() as c:
            c.execute('UPDATE runs SET report=? WHERE id=?',(json.dumps(report),run['id']))
        response=self.client.get('/api/runs/'+run['id'])
        self.assertEqual(response.status_code,500)
        self.assertEqual(response.json()['error']['code'],'invalid_response')
        self.assertNotIn('private fixture marker',response.text)
        self.assertNotIn('report',response.json())

    def test_historical_snapshot_serialization_keeps_frozen_identity(self):
        snapshot=deepcopy(self.snap)
        snapshot['request']['cutoff']=snapshot['request']['cutoff'].replace('Z','+00:00')
        snapshot['id']=digest({'request':snapshot['request'],'manifest':snapshot['manifest']})
        serialized=ReportSnapshot.model_validate(snapshot).model_dump(mode='json')
        self.assertEqual(serialized['request'],snapshot['request'])
        self.assertEqual(ReportSnapshot.model_validate(serialized).id,snapshot['id'])

    def test_plausible_but_unsupported_numeric_claim_is_not_served(self):
        run=self.wait(self.submit()['id'])
        report=deepcopy(run['report'])
        report['findings']['US:AAPL']['quantitative']['last_close']+=1
        # Shape and internal consistency alone cannot verify a financial number.
        validate_output('report',{'report':report})
        with self.client.app.state.store.connect() as c:
            c.execute('UPDATE runs SET report=? WHERE id=?',(json.dumps(report),run['id']))
        response=self.client.get('/api/runs/'+run['id'])
        self.assertEqual(response.status_code,500)
        self.assertEqual(response.json()['error']['code'],'invalid_response')

    def test_invalid_numeric_synthesis_fails_before_report_is_saved(self):
        from research.workflow import Workflow
        original=Workflow.report
        def corrupted(workflow,state):
            result=original(workflow,state)
            result['report']['findings']['US:AAPL']['quantitative']['last_close']+=1
            return result
        with patch.object(Workflow,'report',corrupted):
            run=self.wait(self.submit()['id'])
        self.assertEqual(run['status'],'failed')
        self.assertIsNone(run['report'])

    def test_tool_trace_write_failure_prevents_accepted_report(self):
        with self.client.app.state.store.connect() as c:
            c.execute("CREATE TRIGGER fixture_trace_write_failure BEFORE UPDATE ON tool_calls WHEN NEW.status='completed' BEGIN SELECT RAISE(ABORT,'fixture trace persistence failure'); END")
        run=self.wait(self.submit()['id'])
        self.assertEqual(run['status'],'failed')
        self.assertIsNone(run['report'])
        steps=self.client.get('/api/runs/'+run['id']+'/steps').json()['items']
        self.assertEqual(steps[-1]['status'],'failed')
        self.assertIn('IntegrityError',steps[-1]['data']['validation_failures'])

    def test_single_pass_has_durable_individual_tools_and_bounded_queries(self):
        config=register(self.client.app.state.store,Configuration(workflow='single_pass'))
        run=self.wait(self.submit(configuration_id=config['id'])['id'])
        steps=self.client.get('/api/runs/'+run['id']+'/steps').json()['items']
        self.assertEqual(len(steps),1)
        calls=steps[0]['tool_calls']
        self.assertEqual([call['tool_name'] for call in calls],['eligible-snapshot-read','entity-sentiment',
            'eligible-close-summary','evidence-report-template','mandatory-citation-and-cutoff-check'])
        self.assertEqual(calls[-1]['parent_call_id'],calls[-2]['id'])
        self.assertTrue(all(call['status']=='completed' and call['latency_ms']>=0 for call in calls))
        for call in calls:
            self.assertEqual(call['data']['input_hash'],digest(call['data']['input']))
            self.assertIn('output',call['data'])
        url='/api/runs/'+run['id']+'/tools'
        page=self.client.get(url+'?limit=2&offset=2').json()['items']
        self.assertEqual([call['id'] for call in page],[call['id'] for call in calls[2:4]])
        self.assertEqual(self.client.get(url+'?limit=301').status_code,422)

    def test_retry_attempts_share_parent_time_budget_and_record_failures(self):
        current=[0.0];budgets=[]
        def provider(texts,cancelled,timeout):
            budgets.append(timeout);current[0]+=.6
            raise TimeoutError('fixture inference timeout')
        config=register(self.client.app.state.store,Configuration(workflow='single_pass',sentiment_engine='finbert',
            inference_retries=2,step_timeout_seconds=1,run_timeout_seconds=5))
        with patch('research.workflow.time',SimpleNamespace(monotonic=lambda:current[0])), patch('research.workflow.local_finbert',side_effect=provider):
            run=self.wait(self.submit(configuration_id=config['id'])['id'])
        self.assertEqual(run['status'],'failed')
        self.assertEqual(len(budgets),2)  # A third attempt cannot refresh the exhausted parent budget.
        self.assertAlmostEqual(budgets[0],1);self.assertAlmostEqual(budgets[1],.4)
        calls=self.client.get('/api/runs/'+run['id']+'/tools').json()['items']
        attempts=[call for call in calls if call['tool_name']=='local-finbert-inference']
        self.assertEqual(len(attempts),2)
        self.assertTrue(all(call['status']=='failed' and call['data']['validation_failures']==['TimeoutError'] for call in attempts))

    def test_interrupted_tool_history_is_preserved_on_recovery(self):
        run=self.wait(self.submit()['id'])
        jobs=self.client.app.state.jobs
        original=jobs.tool_calls(run['id'])[0]
        jobs.close()
        with jobs.store.connect() as c:
            c.execute("UPDATE tool_calls SET status='running',finished_at=NULL WHERE id=?",(original['id'],))
            c.execute("UPDATE runs SET status='running',cancelled=0 WHERE id=?",(run['id'],))
        self.client.app.state.jobs=Jobs(jobs.store)
        recovered=self.wait(run['id'])
        self.assertEqual(recovered['attempt'],2)
        calls=self.client.get('/api/runs/'+run['id']+'/tools').json()['items']
        old=next(call for call in calls if call['id']==original['id'])
        self.assertEqual(old['status'],'failed')
        self.assertEqual(old['data']['validation_failures'],['InterruptedProcess'])
        self.assertTrue(any(call['attempt']==2 and call['status']=='completed' for call in calls))
