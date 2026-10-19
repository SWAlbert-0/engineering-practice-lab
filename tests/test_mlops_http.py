import json,tempfile,threading,unittest,urllib.request,urllib.error
from unittest.mock import patch
import server
from shared.mlops_workspace import MlopsWorkspace
class MlopsHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.w=MlopsWorkspace(cls.tmp.name,False);cls.override=patch.object(server,'get_mlops_workspace',return_value=cls.w);cls.override.start();cls.s=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);cls.base=f'http://127.0.0.1:{cls.s.server_port}';cls.thread=threading.Thread(target=cls.s.serve_forever,daemon=True);cls.thread.start()
    @classmethod
    def tearDownClass(cls):cls.s.shutdown();cls.s.server_close();cls.thread.join();cls.override.stop();cls.w.close();cls.tmp.cleanup()
    def request(self,path,body=None,origin=None,method=None):
        return urllib.request.urlopen(urllib.request.Request(self.base+path,json.dumps(body).encode() if body is not None else None,{'Content-Type':'application/json',**({'Origin':origin} if origin else {})},method=method))
    def test_real_upload_train_publish_predict_and_metrics(self):
        source='数值,标签\n'+'\n'.join(f'{i-40},{int(i>=40)}' for i in range(80))
        with self.request('/api/mlops-workspace/datasets',{'title':'接口验收','text':source,'label':'标签'}) as r:self.assertEqual(r.status,201);d=json.load(r)['dataset_id']
        with self.request('/api/mlops-workspace/training-jobs',{'dataset':d}) as r:self.assertEqual(r.status,202);j=json.load(r)['job_id']
        self.w.process_one();m=self.w.model(self.w.job(j)['result']['model_id'])
        with self.request('/api/mlops-workspace/models/'+m['id']+'/reviews',{'revision':0,'sha':m['sha'],'actor':'接口审核','comment':'核对固定切分','decision':'approved'}) as r:self.assertEqual(r.status,200)
        with self.request('/api/mlops-workspace/deployments',{'model':m['id'],'revision':0,'actor':'接口发布','comment':'实际预测验证'}) as r:self.assertEqual(r.status,202)
        self.w.process_one()
        with self.request('/api/mlops-workspace/predict',{'rows':[{'数值':10}]}) as r:result=json.load(r);self.assertEqual(result['model_id'],m['id']);self.assertEqual(result['deployment_revision'],1)
        with self.request('/api/mlops-workspace/metrics') as r:self.assertIn('version=0.0.4',r.headers['Content-Type']);self.assertIn('lab_mlops_requests_total 1.0',r.read().decode())
        with self.request('/api/mlops-workspace/models/'+m['id']+'/export') as r:self.assertIn('attachment',r.headers['Content-Disposition']);self.assertEqual(json.load(r)['artifact']['schema'],'lab-linear-v1')
    def test_invalid_input_origin_and_private_files(self):
        for path,body,status in [('/api/mlops-workspace/datasets',{'title':'bad','text':'x,label\n1,2'},400),('/api/mlops-workspace/jobs/unknown',None,404),('/api/mlops-workspace/unknown',None,404)]:
            with self.assertRaises(urllib.error.HTTPError) as e:self.request(path,body)
            self.assertEqual(e.exception.code,status)
        with self.assertRaises(urllib.error.HTTPError) as e:self.request('/api/mlops-workspace/samples',{},'https://foreign.invalid')
        self.assertEqual(e.exception.code,403)
        for method in ('GET','HEAD'):
            with self.assertRaises(urllib.error.HTTPError) as e:self.request('/data/mlops.sqlite3',method=method)
            self.assertEqual(e.exception.code,404)
    def test_sample_download_and_bad_profile(self):
        with self.request('/api/mlops-workspace/samples/training') as r:self.assertIn(b'feature_1',r.read());self.assertIn('attachment',r.headers['Content-Disposition'])
        with self.assertRaises(urllib.error.HTTPError) as e:self.request('/api/mlops-workspace/samples/unknown')
        self.assertEqual(e.exception.code,400)
