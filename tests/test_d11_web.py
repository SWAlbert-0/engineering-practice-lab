import json
import unittest
from collections import Counter
from scripts.evaluation.d11_web import ROOT, build


class ResearchPublicationTests(unittest.TestCase):
    def test_publication_matches_all_committed_sources(self):
        generated = build()
        destination = ROOT / 'demos/01-repair-agent/research-data'
        self.assertEqual(set(generated), {p.name for p in destination.glob('*.json')})
        for name, content in generated.items():
            self.assertEqual((destination / name).read_bytes().replace(b'\r\n', b'\n'), content, name)
        index = json.loads(generated['index.json'])
        cases = index['cases']
        self.assertEqual(len(cases), 30)
        self.assertEqual(len({c['project'] for c in cases}), 5)
        self.assertEqual(sum(c['status'] == 'reproduced' for c in cases), 29)
        self.assertEqual(Counter(c['model_status'] for c in cases),
                         index['summary']['model_diagnostic']['statuses'])
        self.assertIsNone(index['summary']['model_diagnostic']['semantic_repair_rate'])
        self.assertIsNone(index['summary']['model_diagnostic']['complete_usage'])

    def test_unreproduced_case_and_duplicate_test_events_are_preserved(self):
        generated = build()
        case = json.loads(generated['tornado-3.json'])
        self.assertEqual(case['case']['status'], 'not_reproduced')
        self.assertEqual(case['variants']['buggy']['phases']['trigger']['returncode'], 0)
        case = json.loads(generated['tqdm-1.json'])
        tests = case['variants']['buggy']['phases']['trigger']['tests']
        self.assertEqual([t['status'] for t in tests], ['failure', 'error'])
        self.assertEqual(tests[0]['id'], tests[1]['id'])
        self.assertEqual(len(case['model']['attempts']), 3)


if __name__ == '__main__':
    unittest.main()
