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
    def test_readiness_does_not_expose_configuration(self):
        with urllib.request.urlopen(self.base+'/healthz') as response:
            self.assertEqual(json.load(response),{'status':'ok','projects':6})

    def test_invalid_inputs_rejected(self):
        for path,data in [('/api/rag',{'query':''}),('/api/mlops',{'noise':2}),('/api/repair',{'case':'arbitrary'}),('/api/mlops',{'noise':float('nan')})]:
            with self.subTest(path=path,data=data):
                with self.assertRaises(urllib.error.HTTPError) as c:self.request(path,data)
                self.assertEqual(c.exception.code,400)
    def test_cross_origin_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as c:self.request('/api/repair',{},'https://example.com')
        self.assertEqual(c.exception.code,403)
    def test_new_project_endpoints_and_input_errors(self):
        with self.request('/api/requirements',{'text':'用户可以查看本人订单。'}) as r:
            self.assertTrue(json.load(r)['cases'])
        with self.request('/api/requirements/compare',{'before':'用户查看订单。','after':'用户只能查看本人订单。'}) as r:
            self.assertTrue(json.load(r)['changes'])
        with self.request('/api/literature',{'topic':'外部反馈','ids':['REACT-2022']}) as r:
            self.assertEqual(json.load(r)['model_calls'],0)
        for path,data in [('/api/requirements',{'text':''}),('/api/literature',{'topic':'问题','ids':['unknown']}),('/api/video',{'question':'问题','frames':[],'duration':4})]:
            with self.subTest(path=path):
                with self.assertRaises(urllib.error.HTTPError) as e:self.request(path,data)
                self.assertEqual(e.exception.code,400)
        with urllib.request.urlopen(self.base+'/api/capabilities') as r:
            self.assertEqual(set(json.load(r)),{'llm'})
        with self.assertRaises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(self.base+'/demos/04-tower-defense/')
        self.assertEqual(e.exception.code,404)
    def test_pages_and_assets_exist(self):
        for path in ['/','/report/index.html','/shared/style.css','/demos/01-repair-agent/','/demos/02-process-rag/','/demos/03-mlops/','/demos/04-video-understanding/','/demos/05-requirements/','/demos/06-literature/','/shared/product/core.js','/shared/product/style.css'] + [f'/demos/{name}/{file}' for name in ['01-repair-agent','02-process-rag','03-mlops','04-video-understanding','05-requirements','06-literature'] for file in ['workbench.html','workspace.js' if name in ('02-process-rag','05-requirements') else 'product.js']]:
            with self.subTest(path=path):
                with urllib.request.urlopen(self.base+path) as r:self.assertEqual(r.status,200);self.assertGreater(len(r.read()),100)
