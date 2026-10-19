import json,tempfile,threading,unittest,urllib.request,urllib.error
from unittest.mock import patch
import server
from shared.requirements_workspace import RequirementsWorkspace
class RequirementsHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.w=RequirementsWorkspace(cls.tmp.name,start_worker=False);cls.override=patch.object(server,'get_requirements_workspace',return_value=cls.w);cls.override.start()
        cls.s=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);cls.base=f'http://127.0.0.1:{cls.s.server_port}';cls.thread=threading.Thread(target=cls.s.serve_forever,daemon=True);cls.thread.start()
    @classmethod
    def tearDownClass(cls):cls.s.shutdown();cls.s.server_close();cls.thread.join();cls.override.stop();cls.w.close();cls.tmp.cleanup()
    def request(self,path,data=None,origin=None,method=None):
        headers={'Content-Type':'application/json'}
        if origin:headers['Origin']=origin
        return urllib.request.urlopen(urllib.request.Request(self.base+path,json.dumps(data).encode() if data is not None else None,headers,method=method))
    def test_real_import_analyze_export(self):
        with self.request('/api/requirements-workspace/documents',{'title':'HTTP 验收','text':'用户只能查看本人订单。'}) as r:self.assertEqual(r.status,201);doc=json.load(r)['document_id']
        with self.request('/api/requirements-workspace/documents/'+doc+'/analyses',{'version':1}) as r:self.assertEqual(r.status,202)
        self.w.process_one();setid=self.w.state()['sets'][0]['id']
        with self.request('/api/requirements-workspace/sets/'+setid) as r:self.assertTrue(json.load(r)['cases'])
        with self.request('/api/requirements-workspace/sets/'+setid+'/export?format=csv') as r:self.assertIn('attachment',r.headers['Content-Disposition']);self.assertIn('用例编号',r.read().decode('utf-8-sig'))
        with self.request('/api/requirements-workspace/documents/'+doc+'/changes?before=1&after=1') as r:self.assertEqual(json.load(r)['changes'],[])
    def test_invalid_input_cross_origin_and_private_files(self):
        for path,data,status in [('/api/requirements-workspace/documents',{'title':'x','text':''},400),('/api/requirements-workspace/imports',{'bundle':{}},400),('/api/requirements-workspace/sets/unknown/draft',{'base_version':1,'draft_revision':0,'cases':[]},404)]:
            with self.assertRaises(urllib.error.HTTPError) as e:self.request(path,data)
            self.assertEqual(e.exception.code,status)
        with self.assertRaises(urllib.error.HTTPError) as e:self.request('/api/requirements-workspace/documents',{'title':'x','text':'正文'},'https://elsewhere.invalid')
        self.assertEqual(e.exception.code,403)
        for method in ('GET','HEAD'):
            with self.assertRaises(urllib.error.HTTPError) as e:self.request('/data/requirements.sqlite3',method=method)
            self.assertEqual(e.exception.code,404)
