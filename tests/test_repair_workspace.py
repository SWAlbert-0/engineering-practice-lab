import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from shared.process_workspace import WorkspaceError
from shared.repair_fixtures import CASES,snapshot,validate_proposal,validate_source
from shared.repair_judge import evaluate
from shared.repair_workspace import RepairWorkspace
from shared.repair_runner import RunnerError,RunnerTimeout,container_config,verify_container,decode_logs

class FakeRunner:
    def __init__(self):self.sources=[]
    def run(self,key,source,task,stopped=lambda:False):
        self.sources.append(source);result=evaluate(key,source,stopped);result['environment']={'kind':'docker','image_id':'sha256:fixture'};return result

class RepairWorkspaceTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.w=RepairWorkspace(self.tmp.name,start_worker=False)
    def tearDown(self):self.w.close();self.tmp.cleanup()
    def task(self,**kwargs):return self.w.create({'repository':'boundary',**kwargs})['task_id']
    def docker(self):
        self.w.close();self.w=RepairWorkspace(self.tmp.name,start_worker=False,mode='docker');self.w.heartbeat_worker({'ready':True});return FakeRunner()
    def review(self,t,decision='approved',**values):return self.w.review(t['id'],{'revision':t['revision'],'attempt_sha256':t['attempts'][-1].get('source_sha256','') if t['attempts'] else '',
        'actor':'审查者','comment':'核对回归、边界与独立验收','decision':decision,**values})
    def test_all_snapshots_have_working_baselines_and_independent_gates(self):
        for key,case in CASES.items():
            with self.subTest(key=key):
                before=evaluate(key,case['before']);good=evaluate(key,case['correct']);bad=evaluate(key,case['wrong'])
                self.assertTrue(any(not r['passed'] for r in before['tests']));self.assertTrue(all(r['passed'] for r in good['tests']));self.assertFalse(all(r['passed'] for r in bad['tests']))
                self.assertEqual(len(snapshot(key)['tests']),7)
    def test_progressive_attempts_diff_and_provenance(self):
        tid=self.task(candidate='progressive',max_attempts=2);self.w.process_one();t=self.w.task(tid)
        self.assertEqual(t['status'],'succeeded');self.assertEqual([a['passed'] for a in t['attempts']],[False,True]);self.assertTrue(all(t['gates'].values()))
        self.assertIn('+    return 0 if total >= 100',t['attempts'][-1]['diff']);self.assertTrue(any(not r['passed'] for r in t['baseline']['tests']))
        self.assertEqual(t['snapshot'],snapshot('boundary'));self.assertEqual(len(t['attempts'][-1]['result']['tests']),7)
    def test_failure_never_approves_and_review_is_atomic(self):
        tid=self.task(candidate='wrong');self.w.process_one();t=self.w.task(tid);self.assertEqual(t['status'],'failed')
        with self.assertRaises(WorkspaceError):self.review(t)
        self.assertEqual(self.w.task(tid)['reviews'],[]);self.review(t,'rejected');self.assertEqual(self.w.task(tid)['reviews'][0]['decision'],'rejected')
    def test_review_revision_and_hash_conflicts(self):
        tid=self.task();self.w.process_one();t=self.w.task(tid)
        with self.assertRaises(WorkspaceError):self.review(t,attempt_sha256='other')
        self.review(t)
        with self.assertRaises(WorkspaceError):self.review(t)
        self.assertEqual(len(self.w.task(tid)['reviews']),1)
    def test_retry_is_new_task_without_reviews(self):
        tid=self.task();self.w.process_one();self.review(self.w.task(tid));new=self.w.action(tid,'retry')['task_id'];t=self.w.task(new)
        self.assertNotEqual(new,tid);self.assertEqual(t['parent_id'],tid);self.assertEqual(t['reviews'],[]);self.assertEqual(t['attempts'],[])
    def test_trusted_mode_rejects_free_code_and_model(self):
        for mode in ('manual','llm'):
            with self.subTest(mode=mode),self.assertRaises(WorkspaceError) as err:self.task(mode=mode,source=CASES['boundary']['correct'],path=CASES['boundary']['path'])
            self.assertEqual(err.exception.status,503)
    def test_path_test_tampering_signature_and_io_rejected(self):
        runner=self.docker()
        for path in ('../../server.py','tests/test_shipping.py','/tmp/x.py','src/shipping.py/../other'):
            with self.subTest(path=path),self.assertRaises(WorkspaceError):self.task(mode='manual',path=path,source=CASES['boundary']['correct'])
        for source in ('import os\ndef shipping(total):\n return 0\n','def shipping(total):\n return open("/data/repair.sqlite3").read()\n','def shipping(total):\n return total.__class__\n','def shipping(other=1):\n return 0\n'):
            with self.subTest(source=source),self.assertRaises(ValueError):validate_source(source,'boundary')
        self.assertEqual(runner.sources,[])
    def test_manual_revision_keeps_parent_and_rejects_different_snapshot(self):
        runner=self.docker();tid=self.task(candidate='wrong');self.w.process_one(runner)
        child=self.w.create({'repository':'boundary','mode':'manual','path':'src/shipping.py','source':CASES['boundary']['correct'],'parent_id':tid})['task_id']
        self.w.process_one(runner);t=self.w.task(child);self.assertEqual(t['parent_id'],tid);self.assertEqual(t['status'],'succeeded');self.assertEqual(t['reviews'],[])
        with self.assertRaises(WorkspaceError):self.w.create({'repository':'empty','parent_id':tid})
    def test_valid_manual_patch_uses_runner(self):
        runner=self.docker();tid=self.task(mode='manual',path='src/shipping.py',source=CASES['boundary']['correct']);self.w.process_one(runner)
        self.assertEqual(self.w.task(tid)['status'],'succeeded');self.assertEqual(len(runner.sources),2)
    @patch('shared.repair_workspace.configured',return_value=True)
    def test_model_revision_and_invalid_patch_budget(self,_):
        runner=self.docker();bad={'files':[{'path':'tests/test_shipping.py','content':'x'}],'summary':'修改测试'};good={'files':[{'path':'src/shipping.py','content':CASES['boundary']['correct']}],'summary':'包含临界金额'}
        with patch('shared.repair_workspace.ask_json',side_effect=[bad,good]) as model:
            tid=self.task(mode='llm',max_attempts=2);self.w.process_one(runner)
        t=self.w.task(tid);self.assertEqual(t['status'],'succeeded');self.assertEqual(t['attempts'][0]['status'],'invalid_patch');self.assertEqual(model.call_count,2);self.assertEqual(len(runner.sources),2)
        self.assertIsNone(t['cost']);self.assertIsNone(t['usage']);self.assertTrue(t['attempts'][1]['metadata']['input_sha256'])
    @patch('shared.repair_workspace.configured',return_value=True)
    def test_model_error_is_not_retried_or_offline_success(self,_):
        runner=self.docker()
        with patch('shared.repair_workspace.ask_json',side_effect=ValueError('模型接口超时')) as model:
            tid=self.task(mode='llm',max_attempts=3);self.w.process_one(runner)
        t=self.w.task(tid);self.assertEqual(t['status'],'failed');self.assertEqual(t['reason'],'model_error');self.assertEqual(model.call_count,1);self.assertEqual(len(runner.sources),1)
    def test_cancel_queued_never_executes(self):
        tid=self.task();self.w.action(tid,'cancel');self.assertFalse(self.w.process_one());self.assertEqual(self.w.task(tid)['status'],'cancelled')
    def test_cancel_running_does_not_publish(self):
        runner=self.docker();started=threading.Event()
        def run(key,source,tid,stopped):
            started.set()
            while not stopped():time.sleep(.01)
            raise InterruptedError('cancel')
        runner.run=run;tid=self.task();thread=threading.Thread(target=self.w.process_one,args=(runner,));thread.start();self.assertTrue(started.wait(2));self.w.action(tid,'cancel');thread.join(3)
        self.assertFalse(thread.is_alive());self.assertEqual(self.w.task(tid)['status'],'cancelled');self.assertFalse(self.w.task(tid)['gates']['regression'])
    def test_timeout_and_environment_mismatch_are_failures(self):
        runner=self.docker()
        for error,status in [(RunnerTimeout('timeout'),'timed_out'),(RunnerError('image changed'),'failed')]:
            tid=self.task();runner.run=lambda *args,e=error:(_ for _ in ()).throw(e);self.w.process_one(runner);self.assertEqual(self.w.task(tid)['status'],status)
    def test_missing_or_mismatched_test_evidence_is_rejected(self):
        runner=self.docker();original=runner.run
        for field in ('tests_sha256','tests'):
            def broken(*args):
                result=original(*args);result[field]='invalid' if field!='tests' else result['tests'][:1];return result
            runner.run=broken;tid=self.task();self.w.process_one(runner);self.assertEqual(self.w.task(tid)['status'],'failed')
    def test_restart_persistence_and_stale_lease(self):
        tid=self.task();self.w.process_one();t=self.w.task(tid);self.review(t);self.w.close();self.w=RepairWorkspace(self.tmp.name,start_worker=False)
        self.assertEqual(len(self.w.task(tid)['reviews']),1)
        pending=self.task()
        with self.w.connect(True) as c:c.execute("UPDATE tasks SET status='running',owner='dead',heartbeat=? WHERE id=?",(time.time()-30,pending))
        self.assertEqual(self.w.recover(),[pending]);self.assertEqual(self.w.task(pending)['status'],'interrupted');self.assertFalse(self.w.process_one())
    def test_claim_is_exclusive_and_unknown_is_404(self):
        tid=self.task();other=RepairWorkspace(self.tmp.name,start_worker=False)
        self.assertEqual(self.w._claim(),tid);self.assertIsNone(other._claim());other.close()
        with self.assertRaises(WorkspaceError) as err:self.w.task('missing')
        self.assertEqual(err.exception.status,404)
    def test_exports_bind_full_evidence_and_round(self):
        tid=self.task(candidate='progressive');self.w.process_one();bundle=json.loads(self.w.export(tid)[0]);self.assertEqual(len(bundle['task']['attempts']),2)
        patch=self.w.export(tid,'patch',1);self.assertIn('a/src/shipping.py',patch[0].decode());self.assertTrue(patch[2].endswith('-attempt-1.patch'))
        with self.assertRaises(WorkspaceError):self.w.export(tid,'patch',999)
    def test_input_and_runner_readiness_boundaries(self):
        for value in ({'repository':'unknown'},{'repository':'boundary','max_attempts':True},{'repository':'boundary','max_attempts':4},{'repository':'boundary','mode':'shell'}):
            with self.assertRaises(WorkspaceError):self.w.create(value)
        self.w.close();self.w=RepairWorkspace(self.tmp.name,start_worker=False,mode='docker')
        with self.assertRaises(WorkspaceError) as err:self.task()
        self.assertEqual(err.exception.status,503)
    def test_container_policy_has_no_host_mounts_or_credentials(self):
        config=container_config('sha256:fixture','ws','task',{'source':'x'});host=config['HostConfig'];info={'Image':'sha256:fixture','Config':config,'HostConfig':host,'Mounts':[]}
        self.assertTrue(verify_container(info,'sha256:fixture'));self.assertEqual(host['NetworkMode'],'none');self.assertEqual(host['PidsLimit'],32)
        self.assertNotIn('LAB_LLM_',str(config));host['Binds']=['/data:/data']
        with self.assertRaises(RunnerError):verify_container(info,'sha256:fixture')
