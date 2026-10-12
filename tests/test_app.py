import copy
import http.client
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from domain import *
from adapters import FixtureAdapter, BigQueryReadAdapter
from demo import seed_state, CLOCK
from storage import Store, Conflict
from server import make_server


def ready(overrides=None):
    c = make_contract(contract_inputs(overrides), plus(CLOCK, -31), 'oc-test')
    c.update(state='armed', armed_at=plus(CLOCK, -31))
    complete_action(c, plus(CLOCK, -30))
    return c


class DomainTests(unittest.TestCase):
    def test_descriptive_comparison_is_not_causal(self):
        c = ready();a=analyze(c,FixtureAdapter().measure(c,CLOCK,'action-owner'),CLOCK)
        self.assertEqual(a['status'],'improved');self.assertFalse(a['causal_claim'])
        self.assertEqual(a['attribution'],'matched_comparison')
    def test_guardrail_overrides_primary_success(self):
        c=ready({'scenario':'guardrail'});a=analyze(c,FixtureAdapter().measure(c,CLOCK,'action-owner'),CLOCK)
        self.assertGreater(a['primary']['benefit'],c['inputs']['threshold']);self.assertEqual(a['status'],'harmed')
    def test_raw_guardrail_cannot_be_hidden_by_control(self):
        c=ready();e=FixtureAdapter().measure(c,CLOCK,'action-owner')
        for r in e['rows']:
            if r['metric']=='guardrail' and r['period']=='observed':
                r['numerator']=round((.07 if r['cohort']=='treatment' else .4)*r['count']);r['value']=r['numerator']/r['count']
        self.assertEqual(analyze(c,e,CLOCK)['status'],'harmed')
    def test_invalid_contract_schema(self):
        for patch in ({'threshold':float('nan')},{'end_day':1,'start_day':2},{'action_id':'bad space'}, {'max_bytes':True},{'profile':'unknown'},{'owner':'metric-owner'},{'method':'randomized'},{'config_ref':'https://example.com'}, {'end_day':1000}):
            with self.subTest(patch=patch),self.assertRaises(ValueError):make_contract(contract_inputs(patch),CLOCK,'oc-test')
    def test_duplicates_missing_units_and_versions_fail_closed(self):
        for kind in ('duplicate','missing','unit','version','grain','count','numeric','denominator'):
            c=ready();e=FixtureAdapter().measure(c,CLOCK,'action-owner')
            if kind=='duplicate':e['rows'].append(copy.deepcopy(e['rows'][0]))
            elif kind=='missing':e['rows'].pop()
            elif kind in ('unit','version','grain'):e['rows'][0][kind]='wrong'
            elif kind=='count':e['rows'][0]['count']=0
            elif kind=='numeric':e['rows'][0]['value']=float('nan')
            else:e['rows'][0]['numerator']=-1
            with self.subTest(kind=kind):self.assertEqual(analyze(c,e,CLOCK)['status'],'inconclusive')
    def test_before_after_is_inconclusive(self):
        c=ready({'method':'before_after'});a=analyze(c,FixtureAdapter().measure(c,CLOCK,'action-owner'),CLOCK)
        self.assertEqual(a['status'],'inconclusive');self.assertEqual(a['attribution'],'associated_only')
    def test_unmatured_window(self):
        c=ready();early=plus(c['action']['completed_at'],4)
        self.assertEqual(analyze(c,FixtureAdapter().measure(c,early,'action-owner'),early)['reasons'],['window_not_mature'])
    def test_future_available_evidence_rejected(self):
        c=ready();e=FixtureAdapter().measure(c,CLOCK,'action-owner');e['available_at']=plus(CLOCK,1)
        self.assertIn('late_arriving_evidence',analyze(c,e,CLOCK)['reasons'])
    def test_confounders_and_composition(self):
        for scenario in ('confounded','composition_shift','stale','missing','low_count','metric_drift'):
            c=ready({'scenario':scenario});self.assertEqual(analyze(c,FixtureAdapter().measure(c,CLOCK,'action-owner'),CLOCK)['status'],'inconclusive')
    def test_budget_denied_without_rows_or_cost(self):
        c=ready({'max_bytes':100});e=FixtureAdapter().measure(c,CLOCK,'action-owner')
        self.assertEqual(e['bytes_processed'],0);self.assertEqual(e['rows'],[]);self.assertEqual(analyze(c,e,CLOCK)['status'],'denied')
    def test_acl_denied_before_measurement(self):
        e=FixtureAdapter().measure(ready(),CLOCK,'observer');self.assertEqual(e['denial'],'identity_forbidden');self.assertEqual(e['rows'],[])
    def test_adapter_deterministic(self):
        c=ready();self.assertEqual(FixtureAdapter().measure(c,CLOCK,'action-owner'),FixtureAdapter().measure(c,CLOCK,'action-owner'))
    def test_no_live_adapter(self):
        with self.assertRaises(NotImplementedError):BigQueryReadAdapter().measure(ready(),CLOCK,'action-owner')
    def test_utc_dst_and_timezone_required(self):
        self.assertEqual(plus('2026-11-01T01:30:00-04:00',1),'2026-11-02T05:30:00Z')
        self.assertEqual(timestamp('2026-11-01T01:30:00-05:00')-timestamp('2026-11-01T01:30:00-04:00'),timedelta(hours=1))
        with self.assertRaises(ValueError):timestamp('2026-11-01T01:30:00')
    def test_action_cannot_precede_armed_contract(self):
        c=ready();c['state']='armed'
        with self.assertRaises(ValueError):complete_action(c,plus(c['armed_at'],-1))
    def test_simpson_style_shift_not_pooled(self):
        c=ready();e=FixtureAdapter().measure(c,CLOCK,'action-owner');e['composition_shift']=True
        self.assertIn('cohort_composition_shift',analyze(c,e,CLOCK)['reasons'])


class LifecycleTests(unittest.TestCase):
    def setUp(self):self.s=seed_state()
    def run_command(self,cmd,data,actor='action-owner'):self.s=mutation(self.s,cmd,data,actor)
    def test_full_create_measure_review_learning_flow(self):
        self.run_command('create',contract_inputs({'action_id':'act-fresh','decision_id':'decision-fresh'}));cid=self.s['contracts'][-1]['id']
        for cmd in ('validate','arm','complete'):self.run_command(cmd,dict(id=cid,reason='Lifecycle test'))
        self.run_command('advance',{'days':23});self.run_command('measure',dict(id=cid,reason='Measure due outcome',supersedes=None))
        m=latest(self.s['contracts'][-1]);self.assertEqual(m['analysis']['status'],'improved')
        for actor in ('action-owner','metric-owner'):self.run_command('review',dict(id=cid,receipt_id=m['id'],reason='Checked evidence',decision='accept'),actor)
        self.assertEqual(lifecycle(self.s['contracts'][-1],self.s['clock']),'closed')
        self.run_command('propose',dict(id=cid,receipt_id=m['id'],reason='Keep this as a replay case',kind='regression_fixture'))
        self.assertEqual(latest(self.s['contracts'][-1])['proposals'][0]['state'],'proposed')
    def test_illegal_transition_and_early_measurement(self):
        with self.assertRaises(ValueError):self.run_command('complete',dict(id='oc-demo-009',reason='Invalid'))
        with self.assertRaises(ValueError):self.run_command('measure',dict(id='oc-demo-007',reason='Too early',supersedes=None))
    def test_double_completion_rejected(self):
        with self.assertRaises(ValueError):self.run_command('complete',dict(id='oc-demo-001',reason='Duplicate'))
    def test_observer_cannot_write(self):
        with self.assertRaisesRegex(ValueError,'read_only_identity'):self.run_command('advance',{'days':7},'observer')
    def test_review_requires_distinct_owners(self):
        c=self.s['contracts'][1];m=latest(c);payload=dict(id=c['id'],receipt_id=m['id'],reason='Checked evidence',decision='accept')
        self.run_command('review',payload);self.assertEqual(lifecycle(self.s['contracts'][1],self.s['clock']),'needs_review')
        with self.assertRaisesRegex(ValueError,'review_already_recorded'):self.run_command('review',payload)
    def test_dispute_blocks_learning(self):
        c=self.s['contracts'][1];m=latest(c)
        self.run_command('review',dict(id=c['id'],receipt_id=m['id'],reason='Evidence needs investigation',decision='dispute'))
        with self.assertRaisesRegex(ValueError,'dual_review_required'):self.run_command('propose',dict(id=c['id'],receipt_id=m['id'],reason='Cannot do this',kind='new_experiment'))
    def test_remeasurement_preserves_earlier_receipt(self):
        c=self.s['contracts'][5];old=copy.deepcopy(latest(c));self.run_command('advance',{'days':7})
        self.run_command('measure',dict(id=c['id'],reason='Late data arrived',supersedes=old['id']))
        c=self.s['contracts'][5];self.assertEqual(c['measurements'][0],old);self.assertEqual(latest(c)['analysis']['status'],'improved');self.assertEqual(latest(c)['reviews'],[])
        with self.assertRaisesRegex(ValueError,'stale_receipt'):self.run_command('review',dict(id=c['id'],receipt_id=old['id'],reason='Wrong receipt',decision='accept'))
    def test_closed_receipt_not_cancellable(self):
        with self.assertRaisesRegex(ValueError,'cannot_cancel_final_record'):self.run_command('cancel',dict(id='oc-demo-001',reason='No'))
    def test_cancelled_completed_action_stays_in_denominator(self):
        before=summary(self.s)['closure'];self.run_command('cancel',dict(id='oc-demo-002',reason='Cancelled follow-up'));self.assertEqual(summary(self.s)['closure']['denominator'],before['denominator'])
    def test_closure_exact_and_late_reviews_not_ontime(self):
        self.assertEqual(summary(self.s)['closure']['numerator'],2);self.assertEqual(summary(self.s)['closure']['denominator'],5)
        c=self.s['contracts'][1];m=latest(c)
        for actor in ('action-owner','metric-owner'):self.run_command('review',dict(id=c['id'],receipt_id=m['id'],reason='Late review',decision='accept'),actor)
        self.assertEqual(summary(self.s)['closure']['numerator'],2)
    def test_markdown_contains_limits_evidence_and_reviews(self):
        c=self.s['contracts'][0];m=latest(c);md=receipt_markdown(c,m)
        for text in ('SYNTHETIC DEMO',m['evidence_hash'],'action-owner','metric-owner','not statistical equivalence'):self.assertIn(text,md)


class StorageTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'test.sqlite';self.store=Store(self.path)
    def tearDown(self):self.tmp.cleanup()
    def req(self,key='key-1'):return dict(command='advance',data={'days':7},actor='action-owner',key=key,expected_version=self.store.read()[0])
    def test_future_database_version_is_not_overwritten(self):
        with sqlite3.connect(self.path) as db:db.execute('PRAGMA user_version=99')
        with self.assertRaisesRegex(ValueError,'unsupported_database_schema'):Store(self.path)
        with sqlite3.connect(self.path) as db:self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],99)
    def test_idempotent_retry_and_key_reuse(self):
        req=self.req();self.store.change(req);self.assertTrue(self.store.change(req)['replayed']);self.assertEqual(self.store.read()[0],2);req['data']['days']=8
        with self.assertRaises(Conflict):self.store.change(req)
    def test_stale_revision(self):
        req=self.req();self.store.change(req);req['key']='key-2'
        with self.assertRaises(Conflict):self.store.change(req)
    def test_concurrent_writes_one_wins(self):
        reqs=[self.req('key-'+str(i)) for i in range(2)]
        def write(r):
            try:return self.store.change(r)
            except Conflict:return 'conflict'
        with ThreadPoolExecutor(2) as pool:results=list(pool.map(write,reqs))
        self.assertEqual(results.count('conflict'),1);self.assertEqual(self.store.read()[0],2)
    def test_restart_and_deterministic_replay(self):
        self.store.change(self.req());s2=Store(self.path);self.assertEqual(s2.read(),self.store.read());self.assertEqual(s2.replay()['events'],2)
    def test_corrupt_artifact_fails_closed(self):
        next(self.store.artifacts.iterdir()).write_text('bad')
        with self.assertRaisesRegex(ValueError,'corrupt_evidence_artifact'):self.store.read()
    def test_missing_artifact_fails_closed(self):
        next(self.store.artifacts.iterdir()).unlink()
        with self.assertRaisesRegex(ValueError,'missing_evidence_artifact'):self.store.replay()
    def test_audit_tampering_detected(self):
        with sqlite3.connect(self.path) as db:db.execute("UPDATE events SET hash='broken' WHERE seq=1")
        with self.assertRaisesRegex(ValueError,'audit_hash_mismatch'):self.store.replay()
    def test_transaction_rolls_back_rejected_command(self):
        req=self.req();req['data']['days']=-1
        with self.assertRaises(ValueError):self.store.change(req)
        self.assertEqual(self.store.read()[0],1)


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.server=make_server(Path(cls.tmp.name)/'http.sqlite',0);cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start();cls.port=cls.server.server_port
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.thread.join();cls.tmp.cleanup()
    def request(self,path,method='GET',body=None,headers=None):
        conn=http.client.HTTPConnection('127.0.0.1',self.port,timeout=3);conn.request(method,path,body=body,headers=headers or {});r=conn.getresponse();raw=r.read();out=(r.status,dict(r.getheaders()),raw);conn.close();return out
    def test_pages_and_security_headers(self):
        for route in ('/','/app.js','/style.css'):
            status,headers,raw=self.request(route);self.assertEqual(status,200);self.assertIn("frame-ancestors 'none'",headers['Content-Security-Policy']);self.assertGreater(len(raw),100)
    def test_host_origin_and_token_checks(self):
        self.assertEqual(self.request('/api/state',headers={'Host':'evil.example'})[0],403);self.assertEqual(self.request('/api/command','POST','{}',{'Content-Type':'application/json'})[0],403)
        state=json.loads(self.request('/api/state')[2]);headers={'Content-Type':'application/json','X-Receipt-Token':state['token'],'Origin':'https://evil.example'};self.assertEqual(self.request('/api/command','POST','{}',headers)[0],403)
    def test_api_mutation_reload_export_replay(self):
        state=json.loads(self.request('/api/state')[2]);headers={'Content-Type':'application/json','X-Receipt-Token':state['token']};payload=dict(command='advance',data={'days':7},actor='action-owner',key='http-advance',expected_version=state['version'])
        self.assertEqual(self.request('/api/command','POST',json.dumps(payload),headers)[0],200);packet=json.loads(self.request('/api/export')[2]);self.assertEqual(packet['version'],state['version']+1);self.assertTrue(packet['replay']['verified'])
        rid=packet['state']['contracts'][0]['measurements'][0]['id'];status,headers,md=self.request('/api/receipt.md?id='+rid);self.assertEqual(status,200);self.assertIn('attachment',headers['Content-Disposition']);self.assertIn(b'SYNTHETIC',md)
    def test_traversal_and_unknown_routes(self):
        self.assertEqual(self.request('/../storage.py')[0],404);self.assertEqual(self.request('/api/receipt.md?id=unknown')[0],404)


if __name__=='__main__':unittest.main()
