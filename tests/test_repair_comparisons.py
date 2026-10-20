import json
import tempfile
import unittest
from shared.repair_workspace import RepairWorkspace, WorkspaceError
from shared.repair_fixtures import canonical


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.w = RepairWorkspace(self.tmp.name, False, 'trusted')

    def tearDown(self):
        self.w.close(); self.tmp.cleanup()

    def run_task(self, candidate='correct', repository='boundary'):
        tid = self.w.create({'repository': repository, 'candidate': candidate, 'title': candidate, 'max_attempts': 2})['task_id']
        self.w.process_one()
        return tid

    def report(self, *ids):
        return self.w.create_comparison({'title': '实际运行对照', 'task_ids': list(ids)})['comparison_id']

    def test_actual_test_deltas_sources_and_snapshot_immutability(self):
        wrong, right = self.run_task('wrong'), self.run_task('progressive')
        rid = self.report(wrong, right)
        r = self.w.comparison(rid)
        self.assertEqual(len(r['tests']), 7)
        self.assertEqual(r['columns'][0]['broken'], ['ACC-01', 'ACC-02', 'REG-01', 'REG-02'])
        self.assertEqual(r['columns'][1]['fixed'], ['REG-03'])
        self.assertEqual(r['columns'][1]['passed'], 7)
        self.assertEqual(r['columns'][1]['attempt_count'], 2)
        self.assertIn('>= 100', r['candidate_diffs'][0]['diff'])
        before = self.w.export_comparison(rid)[0]
        t = self.w.task(right)
        self.w.review(right, {'actor': '审核', 'comment': '核对完整测试与需求', 'decision': 'approved', 'revision': t['revision'], 'attempt_sha256': t['attempts'][-1]['source_sha256']})
        self.assertEqual(before, self.w.export_comparison(rid)[0])
        self.assertIsNone(r['columns'][1]['review'])
        self.assertIn('用例对照', self.w.export_comparison(rid, 'markdown')[0].decode())
        self.w.close(); self.w = RepairWorkspace(self.tmp.name, False, 'trusted')
        self.assertEqual(before, self.w.export_comparison(rid)[0])
        self.assertEqual(self.w.state()['comparisons'][0]['id'], rid)

    def test_invalid_ids_unfinished_and_missing_baseline(self):
        tid = self.w.create({'repository': 'boundary'})['task_id']
        for ids in ([], [tid], [tid, tid], [tid, []], [tid]*5):
            with self.assertRaises(WorkspaceError): self.w.create_comparison({'title': '无效', 'task_ids': ids})
        right = self.run_task()
        with self.assertRaises(WorkspaceError): self.report(tid, right)
        self.w.action(tid, 'cancel')
        with self.assertRaises(WorkspaceError): self.report(tid, right)
        with self.assertRaises(WorkspaceError): self.w.comparison('missing')
        with self.assertRaises(WorkspaceError): self.report('missing', right)

    def test_mixed_snapshots_rejected(self):
        a, b = self.run_task(), self.run_task(repository='empty')
        with self.assertRaises(WorkspaceError) as e: self.report(a, b)
        self.assertEqual(e.exception.status, 409)
        self.assertEqual(self.w.comparisons(), [])

    def mutate(self, tid, fn):
        with self.w.connect(True) as c:
            row = self.w._row(c, tid)
            data = json.loads(row['data']); fn(data)
            c.execute('UPDATE tasks SET data=? WHERE id=?', (canonical(data), tid))

    def test_container_ids_do_not_prevent_same_image_comparison(self):
        a, b = self.run_task(), self.run_task('wrong')
        for tid in (a, b):
            def mutate(data):
                data['baseline']['environment'] = {'kind': 'trusted', 'python': '3.12.0', 'container_id': tid+'base'}
                for attempt in data['attempts']:
                    attempt['result']['environment'] = {'kind': 'trusted', 'python': '3.12.0', 'container_id': tid+'candidate'}
            self.mutate(tid, mutate)
        self.assertTrue(self.report(a, b))
        self.mutate(b, lambda data: data['baseline']['environment'].update(python='3.11.0'))
        with self.assertRaises(WorkspaceError): self.report(a, b)

    def test_missing_test_and_environment_tampering_rejected(self):
        a, b = self.run_task(), self.run_task()
        self.mutate(b, lambda data: data['attempts'][0]['result']['tests'].pop())
        with self.assertRaises(WorkspaceError): self.report(a, b)
        c = self.run_task()
        self.mutate(c, lambda data: data['attempts'][0]['result']['environment'].update(python='changed'))
        with self.assertRaises(WorkspaceError): self.report(a, c)

    def test_failed_task_without_candidate_is_not_counted_as_pass(self):
        a, b = self.run_task(), self.run_task('wrong')
        self.mutate(b, lambda data: data.update(attempts=[]))
        r = self.w.comparison(self.report(a, b))
        self.assertIsNone(r['columns'][1]['passed'])
        self.assertTrue(all(x['outcomes'][1]['passed'] is None for x in r['tests']))
        with self.assertRaises(WorkspaceError): self.w.export_comparison(r['id'], 'html')
