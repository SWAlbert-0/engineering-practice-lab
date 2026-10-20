import copy
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from shared.literature_workspace import LiteratureWorkspace, WorkspaceError


class LiteratureReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.w = LiteratureWorkspace(self.tmp.name, False)
        self.pr = self.w.save_project({'title': '教学证据对照（虚构）', 'question': '如何说明不同实验条件？', 'outline_confirmed': True})['project_id']
        self.ids = []
        for i in range(2):
            r = self.w.import_paper({'title': f'教学文献{i}', 'text': f'原文😀方法{i}。发现{i}。局限{i}。', 'scope': 'notes'})
            self.w.process_one(); pid = r['paper_id']; self.ids.append(pid)
            self.w.screen(self.pr, pid, {'decision': 'included', 'reason': '教学对照'})
            self.w.save_evidence(self.pr, {'paper': pid, 'version': 1, 'field': 'finding', 'quote': f'发现{i}。', 'page': 1, 'summary': f'不同条件下的教学发现{i}'})
        self.confirm()

    def tearDown(self): self.w.close(); self.tmp.cleanup()

    def confirm(self):
        for e in self.w.evidence(self.pr):
            if e['status'] != 'confirmed': self.w.review_evidence(e['id'], {'revision': e['revision'], 'status': 'confirmed', 'actor': '教学审核', 'comment': '仅检查逐字引用与输入范围'})

    def body(self, **values):
        a, b = self.w.evidence(self.pr)
        return {'left': a['id'], 'right': b['id'], 'kind': 'contrasts', 'actor': '教学记录人', 'note': '两个研究条件不同，不能据此比较效果。', 'source_revisions': {a['id']: a['revision'], b['id']: b['revision']}, **values}

    def relation(self): return self.w.save_relation(self.pr, self.body())['relation_id']

    def draft(self):
        j = self.w.enqueue(self.pr, 'write', {})['job_id']; self.w.process_one()
        self.assertEqual(self.w.job(j)['status'], 'succeeded', self.w.job(j))
        return self.w.job(j)['result']['draft_id']

    def test_relation_roundtrip_fingerprint_restart_and_exports(self):
        before = self.w.context(self.pr)['fingerprint']; rid = self.relation()
        self.assertNotEqual(before, self.w.context(self.pr)['fingerprint'])
        a = self.w.audit(self.pr)
        self.assertTrue(a['ready_for_writing']); self.assertTrue(a['warnings'])
        self.assertEqual(a['relations'][0]['id'], rid)
        self.assertFalse(a['relations'][0]['stale'])
        self.assertEqual(len(a['papers']), 2)
        self.assertTrue(self.w.export_audit(self.pr, 'csv')[0].startswith(b'\xef\xbb\xbf'))
        self.assertIn('两个研究条件', self.w.export_audit(self.pr, 'markdown')[0].decode())
        self.w.close(); self.w = LiteratureWorkspace(self.tmp.name, False)
        self.assertEqual(self.w.relations(self.pr)[0]['id'], rid)

    def test_old_draft_without_relations_stays_valid_until_change(self):
        d = self.draft(); self.assertFalse(self.w.draft(d)['stale'])
        self.relation(); self.assertTrue(self.w.draft(d)['stale'])
        with self.assertRaises(WorkspaceError): self.w.publish(d, {'version': 1, 'actor': '记录人'})
        fresh = self.draft()
        self.assertFalse(self.w.draft(fresh)['stale'])
        self.assertEqual(len(self.w.draft(fresh)['context']['relations']), 1)

    def test_source_edit_review_and_relation_reconfirmation(self):
        rid = self.relation(); e = self.w.evidence(self.pr)[0]
        self.w.save_evidence(self.pr, {**e, 'summary': '改变解释与条件'}, e['id']); self.confirm()
        self.assertTrue(self.w.relations(self.pr)[0]['stale'])
        self.assertFalse(self.w.audit(self.pr)['ready_for_writing'])
        with self.assertRaises(WorkspaceError): self.w.enqueue(self.pr, 'write', {})
        self.w.save_relation(self.pr, self.body(revision=1), rid)
        r = self.w.relations(self.pr)[0]
        self.assertFalse(r['stale']); self.assertEqual(r['revision'], 2); self.assertEqual(len(r['history']), 2)
        self.assertTrue(self.w.audit(self.pr)['ready_for_writing'])

    def test_duplicate_self_foreign_and_unconfirmed_endpoints(self):
        self.relation()
        for b in [self.body(), self.body(left='missing'), self.body(kind='invented'), self.body(source_revisions={})]:
            with self.assertRaises(WorkspaceError): self.w.save_relation(self.pr, b)
        a = self.w.evidence(self.pr)[0]
        with self.assertRaises(WorkspaceError): self.w.save_relation(self.pr, self.body(right=a['id']))
        another = self.w.save_project({'title': '其他专题', 'question': '其他问题'})['project_id']
        with self.assertRaises(WorkspaceError): self.w.save_relation(another, self.body())
        self.w.review_evidence(a['id'], {'revision': a['revision'], 'status': 'conflict', 'actor': '记录人', 'comment': '此证据有分歧'})
        with self.assertRaises(WorkspaceError): self.w.save_relation(self.pr, self.body(revision=1), self.w.relations(self.pr)[0]['id'])

    def test_delete_endpoint_cannot_leave_writing_ready(self):
        rid = self.relation(); e = self.w.evidence(self.pr)[0]
        self.w.delete_evidence(e['id'], {'revision': e['revision']})
        self.assertTrue(self.w.relations(self.pr)[0]['stale'])
        self.assertTrue(any(i['code'] == 'relation' for i in self.w.audit(self.pr)['blocking']))
        with self.assertRaises(WorkspaceError): self.w.delete_relation(self.pr, rid, {'revision': 0})
        self.w.delete_relation(self.pr, rid, {'revision': 1}); self.assertEqual(self.w.relations(self.pr), [])

    def test_concurrent_relation_revision_prevents_lost_update(self):
        rid = self.relation(); body = self.body(revision=1)
        def write(_):
            try: self.w.save_relation(self.pr, body, rid); return True
            except WorkspaceError as e: self.assertEqual(e.status, 409); return False
        with ThreadPoolExecutor(max_workers=2) as pool: result = list(pool.map(write, range(2)))
        self.assertEqual(sum(result), 1)
        self.assertEqual(len(self.w.relations(self.pr)[0]['history']), 2)

    def test_audit_matches_write_gate_and_advisories_do_not_block(self):
        self.assertTrue(self.w.audit(self.pr)['ready_for_writing'])
        p = self.w.project(self.pr)
        self.w.save_project({**p, 'outline': [s['title'] for s in p['outline']], 'outline_confirmed': False}, self.pr)
        self.assertFalse(self.w.audit(self.pr)['ready_for_writing'])
        with self.assertRaises(WorkspaceError): self.w.enqueue(self.pr, 'write', {})
        self.assertTrue(any(i['code'] == 'outline' for i in self.w.audit(self.pr)['blocking']))

    def test_release_with_relationship_snapshot_remains_immutable(self):
        rid = self.relation(); d = self.draft(); doc = self.w.draft(d)
        ids = [c['id'] for s in doc['sections'] for c in s['claims']]
        self.w.review_draft(d, {'version': 1, 'claim_ids': ids, 'confirmed_count': len(ids), 'decision': 'approved', 'actor': '审核', 'comment': '仅教学流程验收'})
        rel = self.w.publish(d, {'version': 1, 'actor': '发布'})['release_id']; raw = self.w.export(rel, 'json', True)[0]
        self.w.save_relation(self.pr, self.body(revision=1, kind='complements'), rid)
        self.assertEqual(raw, self.w.export(rel, 'json', True)[0]); self.assertTrue(self.w.draft(d)['stale'])

    def test_formula_and_html_safe_downloads(self):
        e = self.w.evidence(self.pr)[0]
        self.w.save_evidence(self.pr, {**e, 'summary': '=SUM(1,2)<script>'}, e['id'])
        self.assertIn("'=SUM", self.w.export_audit(self.pr, 'csv')[0].decode('utf-8-sig'))
        self.assertNotIn('<script>', self.w.export_audit(self.pr, 'markdown')[0].decode())
        with self.assertRaises(WorkspaceError): self.w.export_audit(self.pr, 'html')
