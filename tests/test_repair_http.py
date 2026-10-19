import json,tempfile,threading,unittest,urllib.request,urllib.error
from unittest.mock import patch
import server
from shared.repair_workspace import RepairWorkspace

class RepairHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.w=RepairWorkspace(cls.tmp.name,start_worker=False);cls.override=patch.object(server,'get_repair_workspace',return_value=cls.w);cls.override.start()
        cls.s=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);cls.base=f'http://127.0.0.1:{cls.s.server_port}';cls.thread=threading.Thread(target=cls.s.serve_forever,daemon=True);cls.thread.start()
    @classmethod
    def tearDownClass(cls):cls.s.shutdown();cls.s.server_close();cls.thread.join();cls.override.stop();cls.w.close();cls.tmp.cleanup()
    def request(self,path,data=None,origin=None,method=None):
        headers={'Content-Type':'application/json'}
        if origin:headers['Origin']=origin
        return urllib.request.urlopen(urllib.request.Request(self.base+path,json.dumps(data).encode() if data is not None else None,headers,method=method))
    def test_create_run_review_and_export(self):
        with self.request('/api/repair-workspace/tasks',{'repository':'dedupe','candidate':'progressive'}) as r:self.assertEqual(r.status,202);tid=json.load(r)['task_id']
        self.w.process_one()
        with self.request('/api/repair-workspace/tasks/'+tid) as r:t=json.load(r);self.assertEqual(t['status'],'succeeded')
        with self.request('/api/repair-workspace/tasks/'+tid+'/reviews',{'revision':t['revision'],'attempt_sha256':t['attempts'][-1]['source_sha256'],'actor':'HTTP审查','comment':'核对顺序保持与空输入','decision':'approved'}) as r:self.assertEqual(r.status,200)
        with self.request('/api/repair-workspace/tasks/'+tid+'/export?format=patch&attempt=2') as r:self.assertIn('attachment',r.headers['Content-Disposition']);self.assertIn('dict.fromkeys',r.read().decode())
        with self.request('/api/repair-workspace/tasks/'+tid+'/events') as r:self.assertTrue(json.load(r)['events'])
        with self.request('/api/repair-workspace/workspace',method='HEAD') as r:self.assertEqual(r.status,200);self.assertEqual(r.read(),b'')
    def test_error_contract_and_same_origin(self):
        for path,data,status in [('/api/repair-workspace/tasks',{'repository':'x'},400),('/api/repair-workspace/tasks/unknown/reviews',{'actor':'x','comment':'不少于五个字说明','decision':'approved'},404),('/api/repair-workspace/unknown',{},404)]:
            with self.assertRaises(urllib.error.HTTPError) as err:self.request(path,data)
            self.assertEqual(err.exception.code,status)
        with self.assertRaises(urllib.error.HTTPError) as err:self.request('/api/repair-workspace/tasks',{'repository':'boundary'},'https://other.invalid')
        self.assertEqual(err.exception.code,403)
        for method in ('GET','HEAD'):
            with self.assertRaises(urllib.error.HTTPError) as err:self.request('/data/repair.sqlite3',method=method)
            self.assertEqual(err.exception.code,404)
