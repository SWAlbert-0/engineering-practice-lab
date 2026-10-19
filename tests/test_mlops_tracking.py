"""Optional REST bridge contracts with an isolated HTTP fixture; no remote MLflow required."""
import json,os,tempfile,threading,unittest
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from unittest.mock import patch
from shared.mlops_tracking import call,base_url,TrackingHTTPError
from shared.mlops_workspace import MlopsWorkspace,WorkspaceError
class MlflowBridgeTests(unittest.TestCase):
    def setUp(self):
        self.calls=[];self.mode='normal';self.created=False;self.run=False;owner=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):self.handle_call()
            def do_POST(self):self.handle_call()
            def handle_call(self):
                body=json.loads(self.rfile.read(int(self.headers.get('Content-Length',0))) or b'{}');owner.calls.append((self.path,body))
                status=200;result={}
                if owner.mode=='redirect':self.send_response(302);self.send_header('Location','http://never-follow.invalid/secret');self.end_headers();return
                if owner.mode=='failure':status=500;result={'message':'DO_NOT_ECHO_SECRET'}
                elif 'experiments/get-by-name' in self.path:
                    if not owner.created:status=404;result={'error_code':'RESOURCE_DOES_NOT_EXIST'}
                    else:result={'experiment':{'experiment_id':'7'}}
                elif self.path.endswith('/experiments/create'):owner.created=True;result={'experiment_id':'7'}
                elif self.path.endswith('/runs/search'):result={'runs':[{'info':{'run_id':'fixture-run'}}] if owner.run else []}
                elif self.path.endswith('/runs/create'):owner.run=True;result={'run':{'info':{'run_id':'fixture-run'}}}
                self.send_response(status);raw=json.dumps(result).encode();self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.env=patch.dict(os.environ,{'LAB_MLFLOW_URL':f'http://127.0.0.1:{self.server.server_port}','LAB_MLFLOW_TOKEN':'PRIVATE_TEST_TOKEN'});self.env.start()
    def tearDown(self):self.env.stop();self.server.shutdown();self.server.server_close();self.thread.join()
    def test_real_http_sync_is_optional_and_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            w=MlopsWorkspace(d,False);ds=w.create_sample({})['dataset_id'];j=w.train({'dataset':ds})['job_id'];w.process_one();e=w.job(j)['result']['experiment_id']
            for i in range(2):j=w.track(e)['job_id'];w.process_one();self.assertEqual(w.job(j)['status'],'succeeded',w.job(j))
            self.assertEqual(sum(path.endswith('/runs/create') for path,body in self.calls),1);self.assertEqual(w.experiment(e)['tracking']['remote_run'],'fixture-run');w.close()
    def test_remote_errors_never_echo_body_or_credentials(self):
        self.mode='failure'
        with self.assertRaises(TrackingHTTPError) as e:call('runs/search',{})
        self.assertNotIn('DO_NOT_ECHO_SECRET',str(e.exception));self.assertNotIn('PRIVATE_TEST_TOKEN',str(e.exception))
    def test_redirect_is_not_followed_with_credentials(self):
        self.mode='redirect'
        with self.assertRaises(TrackingHTTPError) as e:call('runs/search',{})
        self.assertEqual(e.exception.http_status,302);self.assertEqual(len(self.calls),1)
    def test_url_embedded_credentials_rejected(self):
        with patch.dict(os.environ,{'LAB_MLFLOW_URL':'http://user:secret@127.0.0.1'}):
            with self.assertRaises(WorkspaceError):base_url()
