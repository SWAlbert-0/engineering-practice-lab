"""Acceptance checks for actual demo behavior; run with unittest discovery."""
import importlib.util,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));import server
class RepairTests(unittest.TestCase):
    def test_three_correct_candidates_pass_independent_tests(self):
        for key in server.repair.CASES:
            with self.subTest(key=key):
                r=server.repair.run(key,'correct');self.assertTrue(r['accepted']);self.assertTrue(any(not x['pass'] for x in r['before']));self.assertTrue(all(x['pass'] for x in r['holdout']))
    def test_three_wrong_candidates_rejected(self):
        for key in server.repair.CASES:
            with self.subTest(key=key):self.assertFalse(server.repair.run(key,'wrong')['accepted'])
    def test_unknown_fixture_never_executes(self):
        with self.assertRaises(ValueError):server.repair.run('../../server.py')
class RagTests(unittest.TestCase):
    def test_material_filter_and_page_citations(self):
        r=server.rag.search('铝合金薄壁精加工','铝合金');self.assertFalse(r['refused']);self.assertEqual(r['hits'][0]['id'],'AL-02');self.assertTrue(all(d['material'] in ['铝合金','通用'] for d in r['hits']));self.assertIn('第2页',r['draft'])
    def test_out_of_domain_refused(self):self.assertTrue(server.rag.search('量子纠缠实验','全部')['refused'])
    def test_bm25_switch_and_invalid_mode(self):
        self.assertEqual(server.rag.search('量具校准','全部','bm25')['hits'][0]['id'],'QA-01')
        with self.assertRaises(ValueError):server.rag.search('量具','全部','fake')
class MlopsTests(unittest.TestCase):
    def test_bad_candidate_rolls_back_and_serves_stable(self):
        r=server.mlops.run(.65,0,True);self.assertTrue(r['rollback']);self.assertEqual(r['active_version'],'v1');self.assertGreater(r['drop'],.08)
    def test_clean_candidate_stays(self):self.assertFalse(server.mlops.run(0,0,True)['rollback'])
    def test_no_labels_never_fabricates_accuracy(self):
        r=server.mlops.run(.65,0,False);self.assertIsNone(r['v1_accuracy']);self.assertIsNone(r['v2_accuracy']);self.assertIsNone(r['drop']);self.assertFalse(r['rollback'])
    def test_drift_alone_does_not_trigger_rollback(self):
        r=server.mlops.run(0,2,True);self.assertTrue(r['drift']);self.assertFalse(r['rollback'])
    def test_reproducible_data_and_predictions(self):
        a=server.mlops.run();b=server.mlops.run();self.assertEqual(a['data_hash'],b['data_hash']);self.assertEqual(a['samples'],b['samples'])
if __name__=='__main__':unittest.main()
