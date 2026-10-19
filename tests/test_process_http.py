"""D01 API status, binary downloads, privacy and input boundary contracts."""
import base64,json,tempfile,threading,unittest,urllib.error,urllib.request
from unittest.mock import patch
import server
from shared.process_workspace import Workspace

class ProcessHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.w=Workspace(cls.tmp.name);cls.override=patch.object(server,'get_workspace',return_value=cls.w);cls.override.start()
        cls.s=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);cls.base=f'http://127.0.0.1:{cls.s.server_port}'
        cls.thread=threading.Thread(target=cls.s.serve_forever,daemon=True);cls.thread.start()
    @classmethod
    def tearDownClass(cls):
        cls.s.shutdown();cls.s.server_close();cls.thread.join();cls.override.stop();cls.w.close();cls.tmp.cleanup()
    def request(self,path,body=None,headers=None,method=None):
        return urllib.request.urlopen(urllib.request.Request(self.base+path,json.dumps(body).encode() if body is not None else None,headers or ({'Content-Type':'application/json'} if body is not None else {}),method=method))
    def test_state_search_and_binary_source(self):
        with self.request('/api/process/workspace') as r:self.assertEqual(len(json.load(r)['documents']),8)
        with self.request('/api/process/search',{'query':'量具校准'}) as r:data=json.load(r)
        self.assertFalse(data['refused']);hit=data['hits'][0]
        with self.request('/api/process/documents/'+hit['document_id']+'/file?version='+hit['version_id']) as r:
            self.assertIn('attachment',r.headers['Content-Disposition']);self.assertIn('量具',r.read().decode())
    def test_hidden_data_config_and_head_never_served(self):
        for path in ['/data/process.sqlite3','/.env','/.git/config','/shared/../data/process.sqlite3','/docs/%2e%2e/.env']:
            for method in ['GET','HEAD']:
                with self.subTest(path=path,method=method):
                    with self.assertRaises(urllib.error.HTTPError) as e:self.request(path,method=method)
                    self.assertEqual(e.exception.code,404)
    def test_invalid_inputs_and_cross_origin(self):
        for path,body in [('/api/process/search',{'query':''}),('/api/process/documents',{'title':'x','filename':'a.exe','content_base64':'eA=='}),('/api/process/evaluate',{'cases':[]}),('/api/process/drafts',{'search_id':'none'})]:
            with self.assertRaises(urllib.error.HTTPError) as e:self.request(path,body)
            self.assertIn(e.exception.code,[400,404])
        with self.assertRaises(urllib.error.HTTPError) as e:self.request('/api/process/search',{'query':'量具'},{'Content-Type':'application/json','Origin':'https://elsewhere.invalid'})
        self.assertEqual(e.exception.code,403)
    def test_ui_cache_revalidation(self):
        for path in ['/demos/02-process-rag/index.html','/demos/02-process-rag/workspace.js?v=20261019-2','/demos/02-process-rag/workspace.css?v=20261019-2']:
            with self.subTest(path=path):
                with self.request(path) as response:
                    self.assertEqual(response.headers['Cache-Control'],'no-cache')
                    modified=response.headers['Last-Modified']
                with self.request(path,method='HEAD') as response:self.assertEqual(response.headers['Cache-Control'],'no-cache')
                with self.assertRaises(urllib.error.HTTPError) as error:
                    self.request(path,headers={'If-Modified-Since':modified})
                self.assertEqual(error.exception.code,304)
                self.assertEqual(error.exception.headers['Cache-Control'],'no-cache')
