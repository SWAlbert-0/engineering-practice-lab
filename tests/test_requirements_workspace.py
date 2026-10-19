"""D09 domain contracts, independent of user data and paid model services."""
import copy
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from shared.requirements_workspace import RequirementsWorkspace, WorkspaceError, paragraphs, generate, rule_analysis

SOURCE='用户只能查看本人订单。\n用户提交订单时数量必须在 1 至 10 之间，同一请求不得重复提交。'
class RequirementsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.w=RequirementsWorkspace(self.tmp.name,start_worker=False)
        self.doc=self.w.import_document({'title':'订单验收','text':SOURCE,'filename':'order.md'})['document_id']
    def tearDown(self):self.w.close();self.tmp.cleanup()
    def suite(self):
        self.w.analyze(self.doc,{'version':1});self.w.process_one();return self.w.suite(self.w.state()['jobs'][0]['result']['set_id'])
    def commit(self,s,cases):
        revision=self.w.save_draft(s['set']['id'],{'base_version':s['set']['current'],'draft_revision':s['draft']['revision'] if s['draft'] else 0,'cases':cases})
        self.w.commit(s['set']['id'],revision);return self.w.suite(s['set']['id'])
    def ready(self,s):
        cases=copy.deepcopy(s['cases'])
        for case in cases:
            case.update(precondition='使用已开通权限的隔离测试账户',questions=[])
            case['steps']=[{'action':'按验收条件发起对应请求','input':'记录明确的测试账户、订单和数量','expected':'逐项检查原文约定的访问范围及数量约束'}]
        return self.commit(s,cases)
    def review(self,s,ids=None,**extra):
        return self.w.review(s['set']['id'],{'version':s['version'],'case_ids':ids or [c['id'] for c in s['cases']], 'confirmed_count':len(ids or s['cases']),'actor':'验收记录人','comment':'已核对原文约束、测试输入与预期结果','decision':'approved',**extra})
    def test_paragraph_offsets_and_immutable_source(self):
        raw='  用户查看订单。\r\n\n  😀管理员核对日志。  '
        ps=paragraphs(raw)
        for p in ps:self.assertEqual(raw[p['start']:p['end']],p['text'])
        self.w.revise(self.doc,{'base_version':1,'text':SOURCE+'\n系统保留审计记录。'})
        self.assertEqual(self.w.document(self.doc,1)['version']['text'],SOURCE)
        with self.assertRaises(WorkspaceError) as e:self.w.revise(self.doc,{'base_version':1,'text':'旧页面提交'})
        self.assertEqual(e.exception.status,409)
    def test_import_limits(self):
        for data in [{'title':'x','text':'x','filename':'x.pdf'},{'title':'x','text':'x\n'*41},{'title':'x','text':'a'*20001},{'title':'x','text':'\x00bad'}]:
            with self.subTest(data=str(data)[:50]),self.assertRaises(WorkspaceError):self.w.import_document(data)
    def test_rules_generate_applicable_kinds_and_anchored_acceptance(self):
        s=self.suite();self.assertEqual({c['kind'] for c in s['cases']},{'正向','异常','边界','权限'})
        for r in s['analysis']['data']['requirements']:
            source=next(p['text'] for p in s['source']['paragraphs'] if p['id']==r['paragraph_id'])
            for a in r['criteria']:self.assertIn(a['quote'],source)
        self.assertTrue(all(c['questions'] for c in s['cases']))
    def test_autosave_conflicts_and_no_lost_update(self):
        s=self.suite();id=s['set']['id'];cases=copy.deepcopy(s['cases']);cases[0]['title']='浏览器 A 的修改'
        self.w.save_draft(id,{'base_version':1,'draft_revision':0,'cases':cases})
        with self.assertRaises(WorkspaceError) as e:self.w.save_draft(id,{'base_version':1,'draft_revision':0,'cases':s['cases']})
        self.assertEqual(e.exception.status,409);self.assertEqual(self.w.suite(id)['draft']['cases'][0]['title'],'浏览器 A 的修改')
        reopened=RequirementsWorkspace(self.tmp.name,start_worker=False)
        try:self.assertEqual(reopened.suite(id)['draft']['revision'],1)
        finally:reopened.close()
    def test_new_version_clears_reviews_and_preserves_history(self):
        s=self.ready(self.suite());self.review(s);cases=copy.deepcopy(s['cases']);cases[0]['title']='新版本标题'
        new=self.commit(s,cases)
        self.assertFalse(new['reviews']);self.assertTrue(self.w.suite(s['set']['id'],s['version'])['reviews'])
        self.assertNotEqual(new['cases'][0]['title'],self.w.suite(s['set']['id'],s['version'])['cases'][0]['title'])
        self.assertIn('human',new['cases'][0]['origin'])
    def test_review_gates_and_batch_is_atomic(self):
        s=self.suite()
        with self.assertRaisesRegex(WorkspaceError,'待确认'):self.review(s)
        s=self.ready(s)
        with self.assertRaisesRegex(WorkspaceError,'数量'):self.review(s,confirmed_count=999)
        with self.assertRaisesRegex(WorkspaceError,'说明'):self.review(s,comment='')
        cases=copy.deepcopy(s['cases']);cases[-1]['questions']=['仍需确认'];s=self.commit(s,cases)
        with self.assertRaisesRegex(WorkspaceError,'待确认'):self.review(s)
        self.assertFalse(self.w.suite(s['set']['id'])['reviews'])
    def test_source_impact_does_not_mark_unchanged_paragraph(self):
        s=self.ready(self.suite());self.w.revise(self.doc,{'base_version':1,'text':SOURCE.replace('1 至 10','2 至 20')})
        new=self.w.suite(s['set']['id']);self.assertEqual(new['affected_requirement_ids'],['REQ-002'])
        first=[c['id'] for c in new['cases'] if c['requirement_id']=='REQ-001'];self.review(new,first)
        affected=[c['id'] for c in new['cases'] if c['requirement_id']=='REQ-002']
        with self.assertRaises(WorkspaceError) as e:self.review(new,affected)
        self.assertEqual(e.exception.status,409)
        with self.assertRaises(WorkspaceError):self.w.publish(s['set']['id'],{'version':s['version'],'actor':'发布人'})
    def test_release_is_frozen_and_json_roundtrip_resets_reviews(self):
        s=self.ready(self.suite());self.review(s);release=self.w.publish(s['set']['id'],{'version':s['version'],'actor':'发布人'})
        raw,_,_=self.w.export(release['release_id'],release=True);bundle=json.loads(raw)
        self.assertEqual(bundle['status'],'released');self.assertEqual(bundle['analysis']['usage'],None)
        restored=self.w.import_bundle({'bundle':bundle});other=self.w.suite(restored['set_id'])
        self.assertEqual(other['cases'],s['cases']);self.assertFalse(other['reviews']);self.assertTrue(other['analysis']['data']['archived_reviews'])
        cases=copy.deepcopy(s['cases']);cases[0]['title']='后续修改';self.commit(s,cases)
        self.assertEqual(raw,self.w.export(release['release_id'],release=True)[0])
        bundle['cases'][0]['title']='篡改发布内容'
        with self.assertRaisesRegex(WorkspaceError,'校验失败'):self.w.import_bundle({'bundle':bundle})
    def test_publish_checks_review_draft_and_criteria_coverage(self):
        s=self.ready(self.suite())
        with self.assertRaisesRegex(WorkspaceError,'核对通过'):self.w.publish(s['set']['id'],{'version':s['version'],'actor':'a'})
        self.review(s)
        cases=copy.deepcopy(s['cases']);cases[0]['title']='未提交草稿';self.w.save_draft(s['set']['id'],{'base_version':s['version'],'draft_revision':0,'cases':cases})
        with self.assertRaises(WorkspaceError):self.w.publish(s['set']['id'],{'version':s['version'],'actor':'a'})
    def test_exports_include_provenance_and_escape_csv_formula(self):
        s=self.suite();cases=copy.deepcopy(s['cases']);cases[0]['title']='=1+1';s=self.commit(s,cases)
        raw,mime,_=self.w.export(s['set']['id'],'csv');self.assertIn("'=1+1",raw.decode('utf-8-sig'));self.assertIn('text/csv',mime)
        md=self.w.export(s['set']['id'],'markdown')[0].decode();self.assertIn('P001',md);self.assertIn('REQ-001',md);self.assertIn('需求 v1',md)
    def test_cancel_retry_and_restart(self):
        job=self.w.analyze(self.doc,{'version':1})['job_id'];self.w.job_action(job,'cancel');self.assertFalse(self.w.process_one())
        retry=self.w.job_action(job,'retry')['job_id'];self.w.process_one();self.assertTrue(next(j for j in self.w.state()['jobs'] if j['id']==retry)['result'])
        job=self.w.analyze(self.doc,{'version':1})['job_id']
        with self.w.connect() as c:c.execute("UPDATE jobs SET status='running' WHERE id=?",(job,))
        other=RequirementsWorkspace(self.tmp.name,start_worker=False)
        try:self.assertEqual(next(j for j in other.state()['jobs'] if j['id']==job)['status'],'interrupted')
        finally:other.close()
    def test_bad_case_links_and_duplicate_ids_rejected(self):
        s=self.suite()
        for mutate in (lambda cs:cs[0].update(criterion_ids=['AC-999']),lambda cs:cs[1].update(id=cs[0]['id'])):
            cases=copy.deepcopy(s['cases']);mutate(cases)
            with self.assertRaises(WorkspaceError):self.w.save_draft(s['set']['id'],{'base_version':1,'draft_revision':0,'cases':cases})
    def test_invalid_model_results_never_create_suite(self):
        with patch('shared.requirements_workspace.configured',return_value=True),patch('shared.requirements_workspace.ask_json',return_value={'requirements':[],'cases':[]}):
            self.w.analyze(self.doc,{'version':1,'mode':'llm'});self.w.process_one()
        self.assertEqual(self.w.state()['jobs'][0]['status'],'failed');self.assertFalse(self.w.state()['sets'])
    def model_payload(self):
        ps=paragraphs(SOURCE);base=rule_analysis(ps);reqs=base['requirements'];mapping={r['id']:r for r in reqs}
        cases=[{**c,'paragraph_id':mapping[c['requirement_id']]['paragraph_id'],'criterion_indexes':list(range(len(mapping[c['requirement_id']]['criteria'])))} for c in base['cases']]
        return {'requirements':reqs,'cases':cases}
    def test_model_generates_actual_steps_and_rejects_wrong_quote(self):
        payload=self.model_payload();payload['cases'][0]['steps'][0]['action']='模型生成的特定操作'
        with patch('shared.requirements_workspace.ask_json',return_value=payload) as call:
            result=generate(paragraphs(SOURCE),'llm')
        self.assertEqual(result['cases'][0]['steps'][0]['action'],'模型生成的特定操作');self.assertEqual(result['cases'][0]['origin'],'llm');self.assertEqual(call.call_args.kwargs['max_tokens'],6000)
        payload['requirements'][0]['criteria'][0]['quote']='原文不存在的阈值'
        with patch('shared.requirements_workspace.ask_json',return_value=payload),self.assertRaisesRegex(WorkspaceError,'引用不在'):generate(paragraphs(SOURCE),'llm')
    def test_discard_draft_requires_matching_revision(self):
        s=self.suite();id=s['set']['id'];cases=copy.deepcopy(s['cases']);cases[0]['title']='临时修改'
        r=self.w.save_draft(id,{'base_version':1,'draft_revision':0,'cases':cases})
        with self.assertRaises(WorkspaceError):self.w.discard_draft(id,{'base_version':1,'draft_revision':0})
        self.w.discard_draft(id,r);self.assertIsNone(self.w.suite(id)['draft']);self.assertNotEqual(self.w.suite(id)['cases'][0]['title'],'临时修改')
    def test_d09_consistent_backup_and_existing_file_refusal(self):
        s=self.suite();target=Path(self.tmp.name)/'backup.sqlite3'
        command=[sys.executable,str(Path(__file__).resolve().parents[1]/'scripts/backup_process_data.py'),'--project','requirements','--output',str(target)]
        env={**os.environ,'LAB_DATA_DIR':self.tmp.name};first=subprocess.run(command,env=env,capture_output=True,text=True)
        self.assertEqual(first.returncode,0,first.stderr)
        with sqlite3.connect(target) as c:self.assertEqual(c.execute('SELECT id FROM sets').fetchone()[0],s['set']['id'])
        self.assertNotEqual(subprocess.run(command,env=env,capture_output=True).returncode,0)
