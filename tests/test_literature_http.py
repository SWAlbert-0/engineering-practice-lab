import json,tempfile,threading,unittest,urllib.error,urllib.request
from unittest.mock import patch
import server
from shared.literature_workspace import LiteratureWorkspace

class LiteratureHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.w=LiteratureWorkspace(cls.tmp.name,False);cls.override=patch.object(server,'get_literature_workspace',return_value=cls.w);cls.override.start();cls.s=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);cls.base=f'http://127.0.0.1:{cls.s.server_port}';cls.thread=threading.Thread(target=cls.s.serve_forever,daemon=True);cls.thread.start()
    @classmethod
    def tearDownClass(cls):cls.s.shutdown();cls.s.server_close();cls.thread.join();cls.override.stop();cls.w.close();cls.tmp.cleanup()
    def request(self,path,body=None,origin=None,method=None):
        return urllib.request.urlopen(urllib.request.Request(self.base+path,json.dumps(body).encode() if body is not None else None,{'Content-Type':'application/json',**({'Origin':origin} if origin else {})},method=method))
    def test_import_read_and_revision_conflict(self):
        with self.request('/api/literature-workspace/papers',{'title':'HTTP 原文','text':'原文😀可以定位。','scope':'notes'}) as r:self.assertEqual(r.status,202);p=json.load(r)['paper_id']
        self.w.process_one()
        with self.request('/api/literature-workspace/papers/'+p) as r:self.assertEqual(json.load(r)['version']['pages'][0]['text'],'原文😀可以定位。')
        with self.request('/api/literature-workspace/papers/'+p+'/file') as r:self.assertIn('attachment',r.headers['Content-Disposition']);self.assertIn('😀',r.read().decode())
        with self.request('/api/literature-workspace/projects',{'title':'API 专题','question':'如何核对？'}) as r:self.assertEqual(r.status,201);pr=json.load(r)['project_id']
        with self.request('/api/literature-workspace/projects/'+pr+'/screen/'+p,{'decision':'included','reason':'相关'}) as r:self.assertEqual(r.status,200)
        with self.request('/api/literature-workspace/projects/'+pr+'/read',{}) as r:self.assertEqual(r.status,202);j=json.load(r)['job_id']
        self.w.process_one()
        with self.request('/api/literature-workspace/jobs/'+j) as r:self.assertEqual(json.load(r)['status'],'succeeded')
        with self.assertRaises(urllib.error.HTTPError) as e:self.request('/api/literature-workspace/projects/'+pr,{'title':'旧版本','question':'问题','revision':0})
        self.assertEqual(e.exception.code,409)
    def test_errors_privacy_and_origin(self):
        for path,body,status in [('/api/literature-workspace/papers',{'title':'无内容'},400),('/api/literature-workspace/jobs/absent',None,404),('/api/literature-workspace/drafts/absent/publish',{'actor':'核对'},404)]:
            with self.assertRaises(urllib.error.HTTPError) as e:self.request(path,body)
            self.assertEqual(e.exception.code,status)
        with self.assertRaises(urllib.error.HTTPError) as e:self.request('/api/literature-workspace/papers',{'title':'x','text':'正文'},'https://elsewhere.invalid')
        self.assertEqual(e.exception.code,403)
        for method in ('GET','HEAD'):
            with self.assertRaises(urllib.error.HTTPError) as e:self.request('/data/literature.sqlite3',method=method)
            self.assertEqual(e.exception.code,404)
    def test_large_text_post_allowed(self):
        with self.request('/api/literature-workspace/papers',{'title':'大文本导入','text':'内容'*100000}) as r:self.assertEqual(r.status,202)
    def test_relation_audit_and_exports(self):
        root='/api/literature-workspace/'
        pr=self.w.save_project({'title':'HTTP关系','question':'测试证据','outline_confirmed':True})['project_id']
        for n in range(2):
            x=self.w.import_paper({'title':'关系材料'+str(n),'text':'用于接口核对的摘记'+str(n),'scope':'notes'});p=x['paper_id']
            while self.w.job(x['job_id'])['status'] in ('queued','running'):self.w.process_one()
            self.w.screen(pr,p,{'decision':'included','reason':'接口测试'})
            self.w.save_evidence(pr,{'paper':p,'version':1,'page':1,'field':'method','quote':'用于接口核对','summary':'接口协议，非科研结论'})
        for e in self.w.evidence(pr):self.w.review_evidence(e['id'],{'revision':e['revision'],'status':'confirmed','actor':'接口审核','comment':'核对原文位置'})
        a,b=self.w.evidence(pr);value={'left':a['id'],'right':b['id'],'source_revisions':{a['id']:a['revision'],b['id']:b['revision']},'kind':'complements','actor':'接口记录','note':'仅测试关系协议'}
        with self.request(root+'projects/'+pr+'/relations',value) as r:self.assertEqual(r.status,201);rid=json.load(r)['relation_id']
        with self.request(root+'projects/'+pr+'/audit') as r:self.assertTrue(json.load(r)['ready_for_writing'])
        with self.request(root+'projects/'+pr+'/relations') as r:self.assertFalse(json.load(r)['relations'][0]['stale'])
        with self.request(root+'projects/'+pr+'/audit/export?format=csv') as r:self.assertIn('attachment',r.headers['Content-Disposition']);self.assertTrue(r.read().startswith(b'\xef\xbb\xbf'))
        with self.request(root+'projects/'+pr+'/audit/export?format=json',method='HEAD') as r:self.assertEqual(r.read(),b'')
        with self.assertRaises(urllib.error.HTTPError) as e:self.request(root+'projects/'+pr+'/relations/'+rid+'/delete',{'revision':0})
        self.assertEqual(e.exception.code,409)
        with self.request(root+'projects/'+pr+'/relations/'+rid+'/delete',{'revision':1}) as r:self.assertTrue(json.load(r)['deleted'])
