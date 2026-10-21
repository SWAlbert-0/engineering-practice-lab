"""Real local HTTP protocol/configuration checks; no provider inference claimed."""
import concurrent.futures
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from shared import model_settings as settings
from shared.model_client import ask_json
import server


class ModelSettingsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.environment = patch.dict(os.environ, {'LAB_DATA_DIR': self.directory.name, 'LAB_LLM_BASE_URL':'', 'LAB_LLM_MODEL':'', 'LAB_LLM_API_KEY':''})
        self.environment.start()
        self.calls = []
        owner = self
        class Upstream(BaseHTTPRequestHandler):
            def log_message(self, *_): pass
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                owner.calls.append({'path': self.path, 'authorization': self.headers.get('Authorization'), 'body':body})
                if self.path.startswith('/redirect'):
                    self.send_response(302);self.send_header('Location', '/must-not-follow');self.end_headers();return
                raw = json.dumps({'model':body['model'], 'choices':[{'message':{'content':'{"ok":true}'}}], 'usage':{'prompt_tokens':3,'completion_tokens':2,'total_tokens':5}}).encode()
                self.send_response(200);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        self.upstream = ThreadingHTTPServer(('127.0.0.1',0),Upstream)
        self.upstream_thread = threading.Thread(target=self.upstream.serve_forever, daemon=True);self.upstream_thread.start()
        self.base = f'http://127.0.0.1:{self.upstream.server_port}/v1'
        self.http = ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        self.http_thread = threading.Thread(target=self.http.serve_forever,daemon=True);self.http_thread.start()
        self.app = f'http://127.0.0.1:{self.http.server_port}'

    def tearDown(self):
        for service, thread in [(self.http,self.http_thread),(self.upstream,self.upstream_thread)]:
            service.shutdown();service.server_close();thread.join()
        self.environment.stop();self.directory.cleanup()

    def request(self, path='', data=None, origin=None):
        headers = {'Content-Type':'application/json'}
        if origin: headers['Origin'] = origin
        request = urllib.request.Request(self.app+'/api/model-settings'+path, None if data is None else json.dumps(data).encode(), headers)
        with urllib.request.urlopen(request) as response: return json.load(response)

    def configure(self, **changes):
        return self.request(data={'base_url':self.base,'model':'shared-text','vision_model':'shared-vision','api_key':'fixture-private-key',**changes})

    def test_save_read_redaction_permissions_and_independent_worker(self):
        value = self.configure()
        self.assertTrue(value['configured']);self.assertTrue(value['key_present'])
        self.assertNotIn('fixture-private-key',json.dumps(value));self.assertNotIn('api_key',self.request())
        self.assertEqual(self.calls,[], 'Saving or reading settings must not call a model')
        if os.name != 'nt':self.assertEqual(settings.settings_path().stat().st_mode & 0o777,0o600)
        process = subprocess.run([sys.executable,'-c','from shared.model_settings import model_name;print(model_name())'],capture_output=True,text=True,check=True)
        self.assertEqual(process.stdout.strip(),'shared-text')
        with self.assertRaises(urllib.error.HTTPError) as result:urllib.request.urlopen(self.app+'/data/model-settings.json')
        self.assertEqual(result.exception.code,404)

    def test_empty_key_preserves_only_same_endpoint_and_clear_restores_environment(self):
        self.configure();self.configure(api_key='',model='renamed')
        self.assertEqual(settings.resolve()['api_key'],'fixture-private-key')
        with self.assertRaises(urllib.error.HTTPError):self.configure(api_key='',base_url=self.base+'/other')
        self.assertEqual(settings.resolve()['base_url'],self.base)
        with patch.dict(os.environ,{'LAB_LLM_BASE_URL':self.base,'LAB_LLM_MODEL':'environment','LAB_LLM_API_KEY':'env-secret'}):
            self.request('/clear',{});self.assertEqual(settings.model_name(),'environment')
            self.assertNotIn('env-secret',json.dumps(self.request()))
        self.assertFalse(settings.settings_path().exists())

    def test_invalid_configuration_and_cross_origin_rejected(self):
        for value in [{'base_url':'file:///tmp/key'},{'base_url':'https://user:password@example.org/v1'},{'base_url':'https://example.org/v1?api_key=secret'},{'base_url':self.base+'/chat/completions'},{'model':'bad\nmodel'},{'api_key':'x\r\nAuthorization: bad'}]:
            with self.subTest(value=value),self.assertRaises(urllib.error.HTTPError) as result:self.configure(**value)
            self.assertEqual(result.exception.code,400)
        with self.assertRaises(urllib.error.HTTPError) as result:self.request(data={'base_url':self.base},origin='https://other.example')
        self.assertEqual(result.exception.code,403)
        self.assertEqual(self.calls,[])

    def test_probe_requires_explicit_confirmation_and_checks_real_http(self):
        self.configure()
        with self.assertRaises(urllib.error.HTTPError):self.request('/test',{})
        self.assertEqual(self.calls,[])
        self.assertTrue(self.request('/test',{'confirm_call':True})['ok'])
        self.assertEqual(len(self.calls),1)
        self.assertEqual(self.calls[0]['authorization'],'Bearer fixture-private-key')
        self.assertEqual(self.calls[0]['body']['model'],'shared-text')

    def test_all_five_project_adapters_use_saved_settings_and_vision_override(self):
        self.configure()
        from shared import process_workspace,requirements_workspace,repair_workspace,literature_workspace,video_workspace
        for module in [process_workspace,requirements_workspace,repair_workspace,literature_workspace]:
            self.assertEqual(module.ask_json('Protocol fixture',{}),{'ok':True})
        self.assertEqual(video_workspace.ask_json('Protocol fixture',{},images=[{'time':0,'image':'data:image/jpeg;base64,AA=='}]),{'ok':True})
        self.assertEqual([r['body']['model'] for r in self.calls],['shared-text']*4+['shared-vision'])
        self.assertTrue(all(r['path']=='/v1/chat/completions' for r in self.calls))
        self.assertEqual(settings.model_name(vision=True),'shared-vision')

    def test_running_session_and_parallel_nodes_keep_original_configuration(self):
        self.configure()
        @settings.model_session
        def task():
            settings.save({'base_url':self.base,'model':'new-model','api_key':'new-key'})
            with concurrent.futures.ThreadPoolExecutor(2) as pool:
                return list(pool.map(settings.contextual(lambda _:ask_json('Protocol fixture',{})),range(2)))
        self.assertEqual(task(),[{'ok':True}]*2)
        self.assertEqual([r['body']['model'] for r in self.calls],['shared-text']*2)
        self.assertEqual(settings.model_name(),'new-model')
        ask_json('Protocol fixture',{})
        self.assertEqual(self.calls[-1]['authorization'],'Bearer new-key')

    def test_redirect_does_not_forward_bearer_and_corrupt_file_does_not_fallback(self):
        self.configure(base_url=self.base.replace('/v1','/redirect'))
        with self.assertRaisesRegex(ValueError,'HTTP 302'):ask_json('Protocol fixture',{})
        self.assertEqual(len(self.calls),1)
        settings.settings_path().write_text('invalid')
        with patch.dict(os.environ,{'LAB_LLM_BASE_URL':self.base,'LAB_LLM_MODEL':'environment','LAB_LLM_API_KEY':'env-secret'}):
            self.assertFalse(settings.configured());self.assertEqual(self.request()['source'],'invalid')


class ModelClientProtocolTests(unittest.TestCase):
    def call(self, response, *, base='https://api.deepseek.com/v1', model='deepseek-flash', **kwargs):
        config = {'base_url': base, 'model': model, 'api_key': 'private-test-key'}
        with patch('shared.model_client.resolve', return_value=config), patch('shared.model_client.configured', return_value=True), patch('shared.model_client.open_model_request') as request:
            request.return_value.__enter__.return_value = io.StringIO(json.dumps(response))
            result = ask_json('Return JSON', {}, **kwargs)
            return result, json.loads(request.call_args.args[0].data)

    def test_deepseek_probe_uses_answer_budget_and_json_mode(self):
        response = {'choices': [{'finish_reason': 'stop', 'message': {'content': '{"ok":true}'}}]}
        for model in ('deepseek-flash', 'deepseek-v4-pro'):
            with self.subTest(model=model):
                result, body = self.call(response, model=model, max_tokens=32)
                self.assertEqual(result, {'ok': True})
                self.assertEqual(body['thinking'], {'type': 'disabled'})
                self.assertEqual(body['response_format'], {'type': 'json_object'})
                self.assertEqual(body['max_tokens'], 32)
        _, body = self.call(response, base='https://compatible.example/v1')
        self.assertNotIn('thinking', body)
        self.assertNotIn('response_format', body)
        _, body = self.call(response, response_schema={'type': 'object'})
        self.assertEqual(body['response_format']['type'], 'json_schema')

    def test_truncated_reasoning_and_json_report_output_limit(self):
        for content in ('', '{"ok":', '{"ok":true}'):
            response = {'choices': [{'finish_reason': 'length', 'message': {'content': content, 'reasoning_content': 'private reasoning'}}]}
            with self.subTest(content=content), self.assertRaisesRegex(ValueError, 'token 上限') as result:
                self.call(response)
            self.assertNotIn('private', str(result.exception))

    def test_auth_balance_and_rate_errors_are_specific_and_redacted(self):
        for code, hint in ((401, '认证失败'), (402, '余额不足'), (429, '配额')):
            error = urllib.error.HTTPError('https://private.example', code, 'private-test-key', {}, io.BytesIO(b'private upstream body'))
            with patch('shared.model_client.resolve', return_value={'base_url': 'https://api.deepseek.com/v1', 'model': 'deepseek-flash', 'api_key': 'private-test-key'}), patch('shared.model_client.configured', return_value=True), patch('shared.model_client.open_model_request', side_effect=error) as request:
                with self.assertRaisesRegex(ValueError, hint) as result:
                    ask_json('Return JSON', {})
                self.assertNotIn('private', str(result.exception))
                self.assertEqual(request.call_count, 1)


class OpenExampleTests(unittest.TestCase):
    def test_catalog_assets_and_all_project_paths(self):
        import hashlib
        root=Path(__file__).resolve().parents[1]
        catalog=json.loads((root/'shared/examples/catalog.json').read_text(encoding='utf-8'))['cases']
        self.assertEqual({row['project'] for row in catalog},{'D01','D02','D09','D11','D12','D13'})
        for row in catalog:
            self.assertTrue(row['license']);self.assertTrue(row['source_url'].startswith('https://'))
            if row.get('file'):
                content=(root/row['file'].lstrip('/')).read_bytes()
                # Text digests use canonical LF, matching the guided importer
                # when a Windows checkout converts source assets to CRLF.
                if Path(row['file']).suffix in {'.txt','.md','.csv'}:
                    content=content.replace(b'\r\n',b'\n')
                self.assertEqual(hashlib.sha256(content).hexdigest(),row['sha256'])
        from shared.mlops_workspace import parse_csv
        iris=parse_csv((root/'shared/examples/iris-binary.csv').read_bytes(),'training','label')
        self.assertEqual(len(iris['rows']),100);self.assertEqual(len(iris['features']),4)
        for kind in ['clean','shift','unlabeled']:
            data=parse_csv((root/('shared/examples/iris-monitor-'+kind+'.csv')).read_bytes(),'monitoring','' if kind=='unlabeled' else 'label')
            self.assertEqual(data['features'],iris['features']);self.assertEqual(len(data['rows']),100)
        self.assertLess(sum(len((root/'shared/examples'/name).read_text(encoding='utf-8')) for name in ['seaborn-paper.txt','arviz-paper.txt']),24000)

    def test_open_algorithm_mutation_has_real_failure_and_correct_candidate(self):
        from shared.repair_fixtures import CASES,snapshot
        from shared.repair_judge import evaluate
        case=CASES['opensource-mean']
        self.assertTrue(any(not t['passed'] for t in evaluate('opensource-mean',case['before'])['tests']))
        self.assertTrue(all(t['passed'] for t in evaluate('opensource-mean',case['correct'])['tests']))
        self.assertEqual(snapshot('opensource-mean')['provenance']['license'],'MIT')
