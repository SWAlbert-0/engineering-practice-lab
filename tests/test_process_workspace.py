"""End-to-end domain contracts for persistent D01, isolated from user data."""
import base64,io,json,sqlite3,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from shared.process_workspace import Workspace,WorkspaceError


class ProcessWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.w=Workspace(self.tmp.name);self.addCleanup(self.w.close)
    def upload(self,content='钛合金专用超声探伤规范。使用已校准量具，检验后记录批次。',replace=None,name='fixture.txt'):
        return self.w.import_document({'title':'钛合金超声规范','material':'钛合金','filename':name,'content_base64':base64.b64encode(content.encode() if isinstance(content,str) else content).decode(),'replace_id':replace})
    def job(self,id):
        for _ in range(500):
            j=next(j for j in self.w.state()['jobs'] if j['id']==id)
            if j['status'] not in ('queued','running'):return j
            time.sleep(.01)
        self.fail('Job did not reach a terminal state')
    def ready(self,content=None):
        result=self.upload(content) if content is not None else self.upload()
        self.assertEqual(self.job(result['job_id'])['status'],'succeeded');return result
    def draft(self):
        self.ready();run=self.w.search({'query':'钛合金超声探伤规范','material':'钛合金'})
        result=self.job(self.w.generate({'search_id':run['id'],'mode':'offline'})['job_id'])
        self.assertEqual(result['status'],'succeeded');return self.w.draft(result['result']['draft_id'])
    def test_import_search_evidence_and_utf8(self):
        result=self.ready();r=self.w.search({'query':'钛合金超声探伤规范','material':'钛合金'})
        self.assertFalse(r['refused']);hit=r['hits'][0];self.assertEqual(hit['document_id'],result['document_id'])
        d=self.w.document(hit['document_id'],hit['version_id']);p=d['version']['pages'][0]['text']
        self.assertEqual(p[hit['start']:hit['end']],hit['text'])
        self.assertTrue(self.w.search({'query':'量子纠缠实验'})['refused'])
    def test_duplicate_does_not_add_document(self):
        first=self.ready();second=self.upload();self.assertTrue(second['duplicate']);self.assertEqual(first['document_id'],second['document_id']);self.assertEqual(len(self.w.state()['documents']),9)
    def test_failed_replacement_keeps_active_index_and_can_retry(self):
        first=self.ready();before=self.w.state()['index']['id']
        result=self.upload(b'%PDF-invalid',first['document_id'],'bad.pdf')
        self.assertEqual(self.job(result['job_id'])['status'],'failed');self.assertEqual(self.w.state()['index']['id'],before)
        self.assertFalse(self.w.search({'query':'钛合金超声探伤规范','material':'钛合金'})['refused'])
        retry=self.w.job_action(result['job_id'],'retry');self.assertEqual(self.job(retry['job_id'])['status'],'failed')
    def test_replacement_and_deletion_invalidate_approval(self):
        d=self.draft();source=d['data']['sources'][0]
        result=self.upload('钛合金新版本只执行包装检查，保留更新记录。',source['document_id'])
        self.assertEqual(self.job(result['job_id'])['status'],'succeeded')
        self.assertTrue(self.w.draft(d['id'])['stale'])
        with self.assertRaisesRegex(WorkspaceError,'来源已更新'):self.w.review(d['id'],{'version':1,'decision':'approved','actor':'reviewer','confirmed':[s['id'] for s in d['data']['steps']]})
        self.w.delete(source['document_id']);self.assertTrue(self.w.search({'query':'钛合金超声探伤规范','material':'钛合金'})['refused'])
        self.assertTrue(self.w.document(source['document_id'],source['version_id'])['document']['deleted'])
    def test_edit_conflict_review_gate_and_version_history(self):
        d=self.draft();id=d['id'];steps=d['data']['steps']
        with self.assertRaisesRegex(WorkspaceError,'逐工序'):self.w.review(id,{'version':1,'decision':'approved','actor':'记录人','confirmed':[]})
        self.w.review(id,{'version':1,'decision':'approved','actor':'记录人','comment':'已核查','confirmed':[s['id'] for s in steps]})
        self.w.save_draft(id,{'version':1,'steps':steps});self.assertEqual(self.w.draft(id)['version'],2)
        with self.assertRaisesRegex(WorkspaceError,'已被修改'):self.w.save_draft(id,{'version':1,'steps':steps})
        self.assertEqual(len(self.w.draft(id,1)['reviews']),1)
        with self.assertRaisesRegex(WorkspaceError,'版本已变化'):self.w.review(id,{'version':1,'decision':'approved','actor':'记录人','confirmed':[s['id'] for s in steps]})
    def test_unverified_numbers_and_parameter_substrings_require_manual_basis(self):
        d=self.draft();steps=d['data']['steps'];steps[0]['operation']='加工转速9999转每分钟'
        steps[0]['parameters']=[{'name':'速度','value':'20','unit':'mm','quote':'速度200mm','manual_basis':''}]
        self.w.save_draft(d['id'],{'version':1,'steps':steps});new=self.w.draft(d['id']);self.assertIn('9999',new['data']['steps'][0]['unsupported_numbers']);self.assertFalse(new['data']['steps'][0]['parameters'][0]['grounded'])
        with self.assertRaisesRegex(WorkspaceError,'人工确认'):self.w.review(d['id'],{'version':2,'decision':'approved','actor':'记录人','confirmed':[s['id'] for s in new['data']['steps']]})
        with self.assertRaisesRegex(WorkspaceError,'无来源数值'):self.w._validate_steps([{'operation':'转速9999','source_ids':[d['data']['sources'][0]['id']]}],d['data']['sources'],True)
    def test_model_failures_do_not_become_offline_success(self):
        self.ready();run=self.w.search({'query':'钛合金超声探伤规范','material':'钛合金'})
        with patch('shared.process_workspace.configured',return_value=True),patch('shared.process_workspace.ask_json',return_value={'steps':[{'operation':'转速9999','source_ids':[run['hits'][0]['id']]}]}):
            job=self.w.generate({'search_id':run['id'],'mode':'llm'});result=self.job(job['job_id'])
        self.assertEqual(result['status'],'failed');self.assertIn('无来源数值',result['error']);self.assertFalse(self.w.state()['drafts'])
    def test_valid_model_generation_and_export(self):
        self.ready();r=self.w.search({'query':'钛合金超声探伤规范','material':'钛合金'})
        with patch('shared.process_workspace.configured',return_value=True),patch('shared.process_workspace.ask_json',return_value={'steps':[{'operation':'检验后记录批次。','source_ids':[r['hits'][0]['id']],'parameters':[]}],'questions':['确认设备']}):
            j=self.job(self.w.generate({'search_id':r['id'],'mode':'llm'})['job_id'])
        self.assertEqual(j['status'],'succeeded');id=j['result']['draft_id'];raw,mime,name=self.w.export(id,'markdown');self.assertIn('来源',raw.decode());self.assertTrue(name.endswith('.md'))
        self.assertEqual(json.loads(self.w.export(id)[0])['data']['mode'],'llm')
    def test_persist_restart_backup_and_interrupted_job(self):
        d=self.draft();job=self.w.enqueue('rebuild',{'strategy':'lsa'});self.job(job['job_id']);self.w.close()
        with self.w.connect() as c:c.execute("UPDATE jobs SET status='running' WHERE id=?",(job['job_id'],))
        again=Workspace(self.tmp.name,start_worker=False);self.addCleanup(again.close)
        self.assertEqual(again.draft(d['id'])['id'],d['id']);self.assertEqual(next(j for j in again.state()['jobs'] if j['id']==job['job_id'])['status'],'interrupted')
        backup=Path(self.tmp.name)/'copy.sqlite3'
        with sqlite3.connect(again.db) as src,sqlite3.connect(backup) as dst:src.backup(dst)
        with sqlite3.connect(backup) as c:self.assertTrue(c.execute('SELECT 1 FROM drafts WHERE id=?',(d['id'],)).fetchone())
    def test_pdf_text_and_blank_pdf_errors(self):
        from pypdf import PdfWriter
        from pypdf.generic import NameObject,DictionaryObject,DecodedStreamObject
        writer=PdfWriter();page=writer.add_blank_page(width=200,height=200)
        font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
        page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):font})})
        stream=DecodedStreamObject();stream.set_data(b'BT /F1 12 Tf 10 100 Td (Titanium fixture inspection) Tj ET');page[NameObject('/Contents')]=writer._add_object(stream)
        out=io.BytesIO();writer.write(out);r=self.upload(out.getvalue(),name='fixture.pdf');self.assertEqual(self.job(r['job_id'])['status'],'succeeded')
        self.assertFalse(self.w.search({'query':'fixture inspection'})['refused'])
        blank=PdfWriter();blank.add_blank_page(width=100,height=100);out=io.BytesIO();blank.write(out);r=self.upload(out.getvalue(),name='blank.pdf');self.assertIn('可提取文本',self.job(r['job_id'])['error'])
    def test_embedding_index_and_configuration_mismatch(self):
        import numpy as np
        with patch('shared.process_workspace.embed_fingerprint',return_value='fixed'),patch('shared.process_workspace.embeddings',side_effect=lambda texts:np.tile([1.,0.],(len(texts),1))):
            result=self.job(self.w.enqueue('rebuild',{'strategy':'embedding'})['job_id']);self.assertEqual(result['status'],'succeeded')
            self.assertEqual(self.w.search({'query':'量具校准'})['strategy'],'embedding')
        with self.assertRaisesRegex(WorkspaceError,'配置已变化'):self.w.search({'query':'量具校准'})
        self.assertFalse(self.w.search({'query':'量具校准','mode':'bm25'})['refused'])
    def test_evaluation_uses_fixed_snapshot_and_real_metrics(self):
        cases=[{'query':'量具校准','expected_document_ids':['QA-01']},{'query':'量子纠缠实验','should_refuse':True}]
        result=self.job(self.w.evaluate({'cases':cases,'mode':'bm25'})['job_id'])
        self.assertEqual(result['status'],'succeeded');e=self.w.evaluation(result['result']['evaluation_id'])
        self.assertEqual(e['summary']['recall_at_5'],1);self.assertEqual(e['summary']['refusal_recall'],1)
        with self.assertRaises(WorkspaceError):self.w.evaluate({'cases':[{'query':'量具'}]})

    def test_mutation_during_build_does_not_resurrect_deleted_document(self):
        import threading
        started=threading.Event();release=threading.Event();original=self.w._build
        def blocking(*args):started.set();release.wait(3);return original(*args)
        with patch.object(self.w,'_build',side_effect=blocking):
            job=self.w.enqueue('rebuild',{'strategy':'lsa'});self.assertTrue(started.wait(2))
            self.w.delete('AL-01');release.set();result=self.job(job['job_id'])
        self.assertEqual(result['status'],'failed');self.assertIn('资料库发生变化',result['error'])
        self.assertFalse(any(h['document_id']=='AL-01' for h in self.w.search({'query':'铝合金零件加工'})['hits']))

    def test_cancellation_during_build_keeps_old_snapshot(self):
        import threading
        started=threading.Event();release=threading.Event();original=self.w._build;before=self.w.state()['index']['id']
        def blocking(*args):started.set();release.wait(3);return original(*args)
        with patch.object(self.w,'_build',side_effect=blocking):
            job=self.w.enqueue('rebuild',{'strategy':'lsa'});self.assertTrue(started.wait(2))
            self.w.job_action(job['job_id'],'cancel');release.set();result=self.job(job['job_id'])
        self.assertEqual(result['status'],'cancelled');self.assertEqual(self.w.state()['index']['id'],before)

    def test_inconsistent_embedding_batches_never_publish(self):
        import numpy as np
        self.w.close();idle=Workspace(self.tmp.name,start_worker=False);self.addCleanup(idle.close)
        before=idle.state()['index']['id'];job=idle.enqueue('rebuild',{'strategy':'embedding'})
        chunks=[{'text':'检索段落'} for _ in range(33)]
        with patch('shared.process_workspace.embed_fingerprint',return_value='fixed'),patch('shared.process_workspace.embeddings',side_effect=lambda values:np.ones((len(values),2 if len(values)==32 else 3))):
            with self.assertRaisesRegex(WorkspaceError,'不一致的维度'):idle._build(job['job_id'],chunks,'embedding')
        self.assertEqual(idle.state()['index']['id'],before)

    def test_cancel_queued_and_failed_build_does_not_publish(self):
        self.w.close();idle=Workspace(self.tmp.name,start_worker=False);self.addCleanup(idle.close)
        job=idle.enqueue('rebuild',{'strategy':'lsa'});idle.job_action(job['job_id'],'cancel')
        self.assertEqual(next(j for j in idle.state()['jobs'] if j['id']==job['job_id'])['status'],'cancelled')
        with self.assertRaisesRegex(WorkspaceError,'未知索引'):idle._build('unused',[],'wrong')


if __name__=='__main__':unittest.main()
