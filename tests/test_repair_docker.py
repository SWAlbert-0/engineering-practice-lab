"""Real Docker boundary tests, opt-in in CI; never use a fake runner here."""
import json,os,tempfile,threading,time,unittest
from unittest.mock import patch
from shared.repair_fixtures import CASES
from shared.repair_workspace import RepairWorkspace,FINAL
from shared.repair_runner import DockerRunner,POLICY,container_config,verify_container,decode_logs

@unittest.skipUnless(os.environ.get('LAB_REPAIR_DOCKER_TEST')=='1','Requires a dedicated Docker test job')
class RepairDockerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.w=RepairWorkspace(self.tmp.name,start_worker=False,mode='docker');self.runner=DockerRunner(self.w.workspace_id);info=self.runner.prepare();self.w.heartbeat_worker({**info,'ready':True})
    def tearDown(self):
        self.runner.reap(lambda _:True);self.w.close();self.tmp.cleanup()
    def manual(self,source):return self.w.create({'repository':'boundary','mode':'manual','path':'src/shipping.py','source':source})['task_id']
    def test_actual_constraints_and_no_host_credentials(self):
        body=container_config(self.runner.image_id,self.w.workspace_id,'isolation-probe',{'repository':'boundary','source':CASES['boundary']['correct']})
        probe='''import json,os,socket
checks={"uid":os.getuid()==65534,"socket_absent":not os.path.exists("/var/run/docker.sock"),"database_absent":not os.path.exists("/data/repair.sqlite3"),"keys_absent":not any(k.startswith(("LAB_LLM_","LAB_EMBED_")) for k in os.environ)}
try:
 open("/opt/repair/write-probe","w").write("unexpected")
 checks["readonly"]=False
except OSError:checks["readonly"]=True
try:
 socket.create_connection(("1.1.1.1",80),timeout=1).close()
 checks["network_none"]=False
except OSError:checks["network_none"]=True
print(json.dumps(checks))
'''
        body['Cmd']=['python','-I','-S','-c',probe];cid=self.runner.request('POST','/containers/create',body)['Id']
        try:
            verify_container(self.runner.request('GET','/containers/'+cid+'/json'),self.runner.image_id);self.runner.request('POST','/containers/'+cid+'/start')
            for _ in range(100):
                if not self.runner.request('GET','/containers/'+cid+'/json')['State']['Running']:break
                time.sleep(.1)
            result=json.loads(decode_logs(self.runner.request('GET','/containers/'+cid+'/logs?stdout=1&stderr=1',raw=True)));self.assertTrue(all(result.values()),result)
            print('ISOLATION EVIDENCE',json.dumps(result,sort_keys=True))
        finally:self.runner.request('DELETE','/containers/'+cid+'?force=1',missing_ok=True)
    def test_real_manual_candidates_and_failed_patch_gate(self):
        for candidate,expected in [('correct','succeeded'),('wrong','failed')]:
            tid=self.manual(CASES['boundary'][candidate]);self.w.process_one(self.runner);t=self.w.task(tid);self.assertEqual(t['status'],expected,t['events']);self.assertTrue(t['environment']['image_id'].startswith('sha256:'));self.assertEqual(t['environment']['policy']['network'],'none')
            if expected=='failed':self.assertFalse(t['gates']['regression'])
        self.runner.reap(lambda _:False)
    def test_running_cancel_reclaims_container(self):
        tid=self.manual('def shipping(total):\n    while True:\n        pass\n');thread=threading.Thread(target=self.w.process_one,args=(self.runner,));thread.start()
        for _ in range(150):
            t=self.w.task(tid)
            if t['phase']=='test':break
            time.sleep(.1)
        self.assertEqual(t['phase'],'test',t['events']);time.sleep(.3);self.w.action(tid,'cancel');thread.join(15);self.assertFalse(thread.is_alive());self.assertEqual(self.w.task(tid)['status'],'cancelled')
        self.assertEqual(self.runner.request('GET','/containers/json?all=1&filters='+__import__('urllib.parse',fromlist=['quote']).quote(json.dumps({'label':['repair.lab.workspace='+self.w.workspace_id]}))),[])
    def test_wall_timeout_reclaims_container(self):
        tid=self.manual('def shipping(total):\n    while True:\n        pass\n');original=self.runner.run
        def execute(key,source,task,stopped):
            if source==CASES[key]['before']:return original(key,source,task,stopped)
            with patch.dict(POLICY,{'wall_seconds':1}):return original(key,source,task,stopped)
        with patch.object(self.runner,'run',side_effect=execute):self.w.process_one(self.runner)
        t=self.w.task(tid);self.assertEqual(t['status'],'timed_out',t['events']);self.assertFalse(t['gates']['acceptance'])
    def test_orphan_recovered_after_lease_expiry(self):
        tid=self.w.create({'repository':'boundary'})['task_id'];self.w._claim()
        cid=self.runner.request('POST','/containers/create',container_config(self.runner.image_id,self.w.workspace_id,tid,{'repository':'boundary','source':CASES['boundary']['correct']}))['Id']
        with self.w.connect(True) as c:c.execute('UPDATE tasks SET heartbeat=? WHERE id=?',(time.time()-30,tid))
        self.w.recover();self.assertEqual(self.w.task(tid)['status'],'interrupted');self.runner.reap(lambda task:self.w.task(task)['status'] in FINAL)
        self.assertIsNone(self.runner.request('GET','/containers/'+cid+'/json',missing_ok=True))
