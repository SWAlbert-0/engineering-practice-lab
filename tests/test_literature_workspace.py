"""D13 evidence lineage, bounded tasks and publication gates; no paid model calls."""
import base64
import io
import copy
from concurrent.futures import ThreadPoolExecutor
import json
import os
import tempfile
import time
import unittest
from unittest.mock import patch
from shared.literature_workspace import LiteratureWorkspace,WorkspaceError,locate,validate_sections

class LiteratureTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.w=LiteratureWorkspace(self.temp.name,False)
        self.p=self.add('方法','原文😀第一句。结果第二句。局限第三句。')
        self.pr=self.w.save_project({'title':'来源冲突研究','question':'不同方法怎样处理来源冲突？','outline_confirmed':True})['project_id']
        self.w.screen(self.pr,self.p,{'decision':'included','reason':'主题相关'})
    def tearDown(self):self.w.close();self.temp.cleanup()
    def add(self,title,body,**kwargs):
        r=self.w.import_paper({'title':title,'scope':'notes','text':body,**kwargs});self.w.process_one();self.assertEqual(self.w.job(r['job_id'])['status'],'succeeded');return r['paper_id']
    def cells(self):
        j=self.w.enqueue(self.pr,'read',{})['job_id'];self.w.process_one();self.assertEqual(self.w.job(j)['status'],'succeeded')
        return self.w.evidence(self.pr)
    def ready(self):
        for e in self.cells():self.w.review_evidence(e['id'],{'revision':e['revision'],'actor':'研究者','comment':'阅读上下文确认','status':'confirmed'})
    def draft(self):
        self.ready();j=self.w.enqueue(self.pr,'write',{})['job_id'];self.w.process_one();self.assertEqual(self.w.job(j)['status'],'succeeded',self.w.job(j));return self.w.job(j)['result']['draft_id']
    def approve(self,d):
        v=self.w.draft(d);ids=[c['id'] for s in v['sections'] for c in s['claims']];self.w.review_draft(d,{'version':v['current'],'claim_ids':ids,'confirmed_count':len(ids),'actor':'研究者','comment':'逐条核对引文支持范围'});return v
    def test_utf8_and_codepoint_locations(self):
        p=self.w.paper(self.p);self.assertIn('😀',p['version']['pages'][0]['text']);self.assertEqual(locate(p['version']['pages'],1,'第一句')['start'],3)
    def test_duplicate_quote_requires_position(self):
        with self.assertRaises(WorkspaceError):locate([{'page':1,'text':'重复 重复'}],1,'重复')
        self.assertEqual(locate([{'page':1,'text':'重复 重复'}],1,'重复',3)['end'],5)
    def test_invalid_quote_rejected(self):
        for page,quote,start in [(9,'第一句',None),(1,'外部文献',None),(1,'第一句',1)]:
            with self.subTest(page=page,quote=quote):
                with self.assertRaises(WorkspaceError):self.w.save_evidence(self.pr,{'paper':self.p,'version':1,'field':'finding','page':page,'quote':quote,'start':start,'summary':'说明'})
    def test_content_dedup(self):
        r=self.w.import_paper({'title':'相同内容','text':'原文😀第一句。结果第二句。局限第三句。'});self.assertTrue(r['deduplicated']);self.assertEqual(r['paper_id'],self.p)
    def test_failed_revision_keeps_current(self):
        r=self.w.import_paper({'title':'坏版本','filename':'x.pdf','content_base64':'bm90IGEgcGRm','paper_id':self.p,'base_version':1});self.w.process_one();self.assertEqual(self.w.job(r['job_id'])['status'],'failed');self.assertEqual(self.w.paper(self.p)['paper']['current'],1)
    def test_revision_stales_evidence(self):
        self.ready();r=self.w.import_paper({'title':'修订','scope':'abstract','text':'修订原文。','paper_id':self.p,'base_version':1});self.w.process_one();self.assertTrue(all(e['stale'] for e in self.w.evidence(self.pr)));self.assertEqual(self.w.paper(self.p,1)['version']['metadata']['scope'],'notes')
        with self.assertRaises(WorkspaceError):self.w.enqueue(self.pr,'write',{})
    def test_delete_paper_preserves_original(self):
        self.cells();self.w.delete_paper(self.p,1);self.assertTrue(self.w.evidence(self.pr)[0]['stale']);self.assertIn('😀',self.w.raw_paper(self.p,1)[0].decode());self.assertEqual(len(self.w.state()['papers']),0)
    def test_screen_revision_conflict(self):
        with self.assertRaises(WorkspaceError):self.w.screen(self.pr,self.p,{'decision':'excluded','reason':'范围调整','revision':0})
        self.w.screen(self.pr,self.p,{'decision':'excluded','reason':'范围调整','revision':1});self.assertEqual(self.w.context(self.pr)['papers'],[])
    def test_six_paper_limit(self):
        for i in range(5):
            p=self.add('文献'+str(i),'研究内容'+str(i));self.w.screen(self.pr,p,{'decision':'included','reason':'相关'})
        p=self.add('第七篇','超出专题范围')
        with self.assertRaises(WorkspaceError):self.w.screen(self.pr,p,{'decision':'included','reason':'相关'})
    def test_outline_gate(self):
        self.ready();p=self.w.project(self.pr);self.w.save_project({**p,'outline':[s['title'] for s in p['outline']],'outline_confirmed':False},self.pr)
        with self.assertRaises(WorkspaceError):self.w.enqueue(self.pr,'write',{})
    def test_pending_conflict_gate_and_delete(self):
        e=self.cells()[0]
        with self.assertRaises(WorkspaceError):self.w.enqueue(self.pr,'write',{})
        self.w.review_evidence(e['id'],{'revision':1,'status':'conflict','actor':'研究者','comment':'不足以支持结论'})
        with self.assertRaises(WorkspaceError):self.w.delete_evidence(e['id'],{'revision':1})
        self.w.delete_evidence(e['id'],{'revision':2});self.assertNotIn(e['id'],[v['id'] for v in self.w.evidence(self.pr)])
    def test_evidence_edit_resets_review(self):
        self.ready();e=self.w.evidence(self.pr)[0];self.w.save_evidence(self.pr,{**e,'summary':'修订解释'},e['id']);self.assertEqual(self.w.evidence(self.pr)[0]['status'],'pending')
    def test_draft_optimistic_lock_and_new_version(self):
        d=self.draft();v=self.w.draft(d);sections=copy.deepcopy(v['sections']);sections[0]['claims'][0]['text']='人工修改后的论述';payload={'base_version':1,'draft_revision':0,'sections':sections};self.w.save_draft(d,payload)
        with self.assertRaises(WorkspaceError):self.w.save_draft(d,payload)
        self.w.commit(d,{'base_version':1,'draft_revision':1});self.assertEqual(self.w.draft(d)['current'],2);self.assertNotEqual(self.w.draft(d,1)['sections'][0]['claims'][0]['text'],'人工修改后的论述');self.assertEqual(self.w.draft(d)['reviews'],[])
    def test_review_is_version_and_claim_bound(self):
        d=self.draft()
        with self.assertRaises(WorkspaceError):self.w.review_draft(d,{'version':1,'actor':'记录人','comment':'检查','claim_ids':['foreign'],'confirmed_count':1})
        with self.assertRaises(WorkspaceError):self.w.publish(d,{'version':1,'actor':'记录人'})
        self.approve(d);self.assertTrue(self.w.publish(d,{'version':1,'actor':'记录人'})['release_id'])
    def test_release_immutable_after_sources_change(self):
        d=self.draft();self.approve(d);r=self.w.publish(d,{'version':1,'actor':'记录人'})['release_id'];before=self.w.export(r,'json',True)[0]
        self.w.delete_paper(self.p,1);self.assertTrue(self.w.draft(d)['stale']);self.assertEqual(before,self.w.export(r,'json',True)[0])
        with self.assertRaises(WorkspaceError):self.w.publish(d,{'version':1,'actor':'记录人'})
    def test_exports_do_not_include_autosave(self):
        d=self.draft();v=self.w.draft(d);s=copy.deepcopy(v['sections']);s[0]['claims'][0]['text']='UNCOMMITTED';self.w.save_draft(d,{'base_version':1,'draft_revision':0,'sections':s});self.assertNotIn(b'UNCOMMITTED',self.w.export(d)[0]);self.assertIn(b'@misc{',self.w.export(d,'bibtex')[0]);self.assertEqual(json.loads(self.w.export(d,'json')[0])['context']['papers'][0]['metadata']['scope'],'notes')
    def test_invalid_section_citation_rejected(self):
        d=self.draft();v=self.w.draft(d);v['sections'][0]['claims'][0]['evidence_ids']=['ev-foreign']
        with self.assertRaises(WorkspaceError):self.w.save_draft(d,{'base_version':1,'draft_revision':0,'sections':v['sections']})
    def test_discard_optimistic_revision(self):
        d=self.draft();v=self.w.draft(d);self.w.save_draft(d,{'base_version':1,'draft_revision':0,'sections':v['sections']})
        with self.assertRaises(WorkspaceError):self.w.discard_draft(d,{'base_version':1,'draft_revision':0})
        self.w.discard_draft(d,{'base_version':1,'draft_revision':1});self.assertIsNone(self.w.draft(d)['draft'])
    def test_cancel_import_and_explicit_retry(self):
        r=self.w.import_paper({'title':'取消测试','text':'等待解析。'});self.w.job_action(r['job_id'],'cancel');self.assertFalse(self.w.process_one());j=self.w.job_action(r['job_id'],'retry')['job_id'];self.w.process_one();self.assertEqual(self.w.job(j)['status'],'succeeded')
    def test_recover_interrupted_import(self):
        r=self.w.import_paper({'title':'中断测试','text':'等待恢复。'})
        with self.w.connect(True) as c:c.execute("UPDATE jobs SET status='running',heartbeat=?,owner='lost' WHERE id=?",(time.time()-60,r['job_id']))
        self.w.recover();self.assertEqual(self.w.job(r['job_id'])['status'],'interrupted');self.w.job_action(r['job_id'],'retry');self.w.process_one();self.assertEqual(self.w.paper(r['paper_id'])['paper']['current'],1)
    def test_model_not_configured_no_fallback(self):
        with patch('shared.literature_workspace.configured',return_value=False):
            with self.assertRaises(WorkspaceError):self.w.enqueue(self.pr,'read',{'mode':'multi'})
    def test_model_input_limit(self):
        p=self.add('长文','长'*24001);self.w.screen(self.pr,p,{'decision':'included','reason':'长文'})
        with patch('shared.literature_workspace.configured',return_value=True):
            with self.assertRaises(WorkspaceError):self.w.enqueue(self.pr,'read',{'mode':'single'})
    def test_multi_reader_checkpoint_retry_only_failed_node(self):
        p2=self.add('第二篇','不同研究原文。');self.w.screen(self.pr,p2,{'decision':'included','reason':'相关'});calls=[];broken=[True]
        def model(prompt,payload,**kwargs):
            p=payload['papers'][0];calls.append(p['id'])
            if p['id']==p2 and broken[0]:raise ValueError('模拟供应商失败')
            return {'evidence':[{'paper':p['id'],'field':'method','page':1,'quote':p['pages'][0]['text'],'summary':'输入材料的内容'}]}
        with patch('shared.literature_workspace.configured',return_value=True),patch('shared.literature_workspace.ask_json',side_effect=model):
            j=self.w.enqueue(self.pr,'read',{'mode':'multi'})['job_id'];self.w.process_one();self.assertEqual(self.w.job(j)['status'],'failed');self.assertEqual(self.w.evidence(self.pr),[])
            broken[0]=False;retry=self.w.job_action(j,'retry')['job_id'];self.w.process_one();self.assertEqual(self.w.job(retry)['status'],'succeeded');self.assertEqual(calls.count(self.p),1);self.assertEqual(calls.count(p2),2);self.assertTrue(any(n['reused_from']==j for n in self.w.job(retry)['nodes']))
    def test_model_switch_during_retry_keeps_checkpoint_identity(self):
        # Simulate a settings change exactly between retry validation and enqueue.
        with patch.dict(os.environ,{'LAB_LLM_BASE_URL':'http://localhost/v1','LAB_LLM_MODEL':'model-a','LAB_LLM_API_KEY':'protocol-key'}),patch('shared.literature_workspace.configured',return_value=True),patch('shared.literature_workspace.ask_json',side_effect=ValueError('protocol failure')) as model:
            job=self.w.enqueue(self.pr,'read',{'mode':'single'})['job_id'];self.w.process_one()
            self.assertEqual(self.w.job(job)['status'],'failed')
            original=self.w._enqueue
            def switch(*args,**kwargs):
                os.environ['LAB_LLM_MODEL']='model-b'
                return original(*args,**kwargs)
            with patch.object(self.w,'_enqueue',side_effect=switch):
                retry=self.w.job_action(job,'retry')['job_id']
            self.assertEqual(self.w.job(retry)['model'],'model-a')
            self.assertEqual(self.w.job(retry)['model_fp'],self.w.job(job)['model_fp'])
            self.w.process_one()
            self.assertEqual(model.call_count,1,'A changed provider must not reuse old checkpoints under its identity')
            self.assertIn('模型配置已变化',self.w.job(retry)['error'])

    def test_context_change_during_model_call_blocks_commit(self):
        def model(prompt,payload,**kwargs):
            p=self.w.project(self.pr);self.w.save_project({**p,'outline':[s['title'] for s in p['outline']],'question':'新问题'},self.pr);paper=payload['papers'][0];return {'evidence':[{'paper':paper['id'],'field':'method','page':1,'quote':'原文😀第一句。','summary':'说明'}]}
        with patch('shared.literature_workspace.configured',return_value=True),patch('shared.literature_workspace.ask_json',side_effect=model):
            j=self.w.enqueue(self.pr,'read',{'mode':'single'})['job_id'];self.w.process_one();self.assertEqual(self.w.job(j)['status'],'failed');self.assertEqual(self.w.evidence(self.pr),[])
            with self.assertRaises(WorkspaceError):self.w.job_action(j,'retry')
    def test_model_fabricated_quote_fails(self):
        with patch('shared.literature_workspace.configured',return_value=True),patch('shared.literature_workspace.ask_json',return_value={'evidence':[{'paper':self.p,'field':'finding','page':1,'quote':'伪造实验提高了99%','summary':'不能接受'}]}):
            j=self.w.enqueue(self.pr,'read',{'mode':'single'})['job_id'];self.w.process_one();self.assertEqual(self.w.job(j)['status'],'failed');self.assertEqual(self.w.evidence(self.pr),[])
    def test_two_writers_only_one_revision_wins(self):
        d=self.draft();v=self.w.draft(d)
        def save(i):
            try:self.w.save_draft(d,{'base_version':1,'draft_revision':0,'sections':v['sections']});return True
            except WorkspaceError:return False
        with ThreadPoolExecutor(max_workers=2) as pool:self.assertEqual(sum(pool.map(save,range(2))),1)
    def test_duplicate_active_task_reuses_job(self):
        first=self.w.enqueue(self.pr,'read',{})['job_id'];second=self.w.enqueue(self.pr,'read',{})['job_id'];self.assertEqual(first,second)
    def test_pending_import_content_dedup(self):
        a=self.w.import_paper({'title':'等待导入','text':'相同的等待文本。'});b=self.w.import_paper({'title':'重复','text':'相同的等待文本。'});self.assertEqual(a['paper_id'],b['paper_id']);self.assertTrue(b['deduplicated'])
    def test_text_pdf_and_blank_rejection(self):
        from pypdf import PdfWriter
        from pypdf.generic import NameObject,DictionaryObject,DecodedStreamObject
        writer=PdfWriter();page=writer.add_blank_page(width=200,height=200);font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')});page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):font})});stream=DecodedStreamObject();stream.set_data(b'BT /F1 12 Tf 10 100 Td (Literature evidence fixture) Tj ET');page[NameObject('/Contents')]=writer._add_object(stream)
        out=io.BytesIO();writer.write(out);r=self.w.import_paper({'title':'PDF','filename':'source.pdf','content_base64':base64.b64encode(out.getvalue()).decode()});self.w.process_one();self.assertEqual(self.w.job(r['job_id'])['status'],'succeeded');self.assertIn('Literature evidence',self.w.paper(r['paper_id'])['version']['pages'][0]['text'])
        blank=PdfWriter();blank.add_blank_page(width=100,height=100);out=io.BytesIO();blank.write(out);r=self.w.import_paper({'title':'空页','filename':'empty.pdf','content_base64':base64.b64encode(out.getvalue()).decode()});self.w.process_one();self.assertEqual(self.w.job(r['job_id'])['status'],'failed');self.assertIn('可提取文本',self.w.job(r['job_id'])['error'])
    def test_invalid_utf8_and_file_type(self):
        with self.assertRaises(WorkspaceError):self.w.import_paper({'title':'可执行文件','filename':'bad.exe','text':'拒绝'})
        r=self.w.import_paper({'title':'坏编码','filename':'bad.txt','content_base64':'//4='});self.w.process_one();self.assertEqual(self.w.job(r['job_id'])['status'],'failed')
    def test_multi_writer_uses_confirmed_evidence_only(self):
        self.ready();calls=[]
        def model(prompt,payload,**kwargs):
            calls.append(payload);return {'sections':[{'id':s['id'],'claims':[{'text':'依据当前教学材料，示范证据关系。','evidence_ids':[payload['evidence'][0]['id']]}]} for s in payload['outline']]}
        with patch('shared.literature_workspace.configured',return_value=True),patch('shared.literature_workspace.ask_json',side_effect=model):
            j=self.w.enqueue(self.pr,'write',{'mode':'multi'})['job_id'];self.w.process_one();self.assertEqual(self.w.job(j)['status'],'succeeded');self.assertEqual(len(calls),3);self.assertTrue(all(e['status']=='confirmed' for call in calls for e in call['evidence']));self.assertEqual(len(self.w.job(j)['nodes']),4)
    def test_model_cancel_keeps_paid_output_without_committing(self):
        def model(prompt,payload,**kwargs):
            self.w.job_action(j,'cancel');return {'evidence':[{'paper':self.p,'field':'method','page':1,'quote':'原文😀第一句。','summary':'说明'}]}
        with patch('shared.literature_workspace.configured',return_value=True),patch('shared.literature_workspace.ask_json',side_effect=model):
            j=self.w.enqueue(self.pr,'read',{'mode':'single'})['job_id'];self.w.process_one();value=self.w.job(j);self.assertEqual(value['status'],'cancelled');self.assertEqual(value['nodes'][0]['status'],'succeeded');self.assertEqual(self.w.evidence(self.pr),[])
    def test_repeated_retry_does_not_overwrite_existing_checkpoints(self):
        def model(prompt,payload,**kwargs):
            self.w.job_action(j,'cancel');return {'evidence':[{'paper':self.p,'field':'method','page':1,'quote':'原文😀第一句。','summary':'已付费阅读结果'}]}
        with patch('shared.literature_workspace.configured',return_value=True),patch('shared.literature_workspace.ask_json',side_effect=model) as call:
            j=self.w.enqueue(self.pr,'read',{'mode':'single'})['job_id'];self.w.process_one();first=self.w.job_action(j,'retry')['job_id'];again=self.w.job_action(j,'retry')['job_id'];self.assertEqual(first,again);self.w.process_one();self.assertEqual(self.w.job(first)['status'],'succeeded');self.assertEqual(call.call_count,1)
    def test_data_survives_new_connection(self):
        d=self.draft();other=LiteratureWorkspace(self.temp.name,False);self.assertEqual(other.draft(d)['context']['project']['title'],'来源冲突研究');other.close()

if __name__=='__main__':unittest.main()
