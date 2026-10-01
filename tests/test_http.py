import json,threading,unittest,urllib.request,urllib.error
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server
class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);cls.base=f'http://127.0.0.1:{cls.s.server_port}'
        cls.thread=threading.Thread(target=cls.s.serve_forever,daemon=True);cls.thread.start()
    @classmethod
    def tearDownClass(cls):cls.s.shutdown();cls.s.server_close();cls.thread.join()
    def request(self,path,data,origin=None):
        headers={'Content-Type':'application/json'}
        if origin:headers['Origin']=origin
        return urllib.request.urlopen(urllib.request.Request(self.base+path,json.dumps(data).encode(),headers))
    def test_three_endpoints_return_computed_results(self):
        for path,data,key in [('/api/repair',{'case':'empty'},'accepted'),('/api/rag',{'query':'量具校准'},'hits'),('/api/mlops',{'noise':.65,'labels':True},'rollback')]:
            with self.subTest(path=path):
                with self.request(path,data) as r:self.assertTrue(json.load(r)[key])
    def test_invalid_inputs_rejected(self):
        for path,data in [('/api/rag',{'query':''}),('/api/mlops',{'noise':2}),('/api/repair',{'case':'arbitrary'}),('/api/mlops',{'noise':float('nan')})]:
            with self.subTest(path=path,data=data):
                with self.assertRaises(urllib.error.HTTPError) as c:self.request(path,data)
                self.assertEqual(c.exception.code,400)
    def test_cross_origin_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as c:self.request('/api/repair',{},'https://example.com')
        self.assertEqual(c.exception.code,403)
    def test_pages_and_assets_exist(self):
        for path in ['/','/report/index.html','/shared/style.css','/demos/01-repair-agent/','/demos/02-process-rag/','/demos/03-mlops/','/demos/04-tower-defense/']:
            with self.subTest(path=path):
                with urllib.request.urlopen(self.base+path) as r:self.assertEqual(r.status,200);self.assertGreater(len(r.read()),100)
