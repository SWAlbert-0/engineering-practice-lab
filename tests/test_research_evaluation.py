import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from scripts.evaluation.common import digest, write_new
from scripts.evaluation.d11 import extract_archive, targets, validate_candidate, valid_reproduction


class RepairBenchmarkTests(unittest.TestCase):
    def test_fixed_population_and_commands(self):
        manifest = json.loads(Path('evaluations/d11/manifest.json').read_text())
        self.assertEqual(len(manifest['cases']), 30)
        self.assertEqual(len({c['project'] for c in manifest['cases']}), 5)
        self.assertEqual(len({c['id'] for c in manifest['cases']}), 30)
        for case in manifest['cases']:
            self.assertTrue(targets(case))
            self.assertRegex(case['fixed_commit'], r'^[0-9a-f]{40}$')

    def test_archive_links_and_traversal_rejected(self):
        for name, kind in [('../escape', tarfile.REGTYPE), ('link', tarfile.SYMTYPE)]:
            raw = io.BytesIO()
            with tarfile.open(fileobj=raw, mode='w') as archive:
                info = tarfile.TarInfo(name)
                info.type = kind
                archive.addfile(info)
            with tempfile.TemporaryDirectory() as directory:
                with self.assertRaises(ValueError):
                    extract_archive(raw.getvalue(), Path(directory))

    def test_patch_cannot_modify_tests_or_escape(self):
        for name in ('tests/test_a.py', '../a.py', '/tmp/a.py', '.github/step.py'):
            with self.assertRaises(ValueError):
                validate_candidate({'files': [{'path': name, 'content': 'x=1'}]}, ['src/a.py'])
        self.assertEqual(validate_candidate({'files': [{'path': 'src/a.py', 'content': 'x=1'}]}, ['src/a.py']), {'src/a.py': b'x=1'})

    def test_collection_errors_are_not_bug_reproduction(self):
        def run(code, status, id='A'):
            return {'phases': {'trigger': {'returncode': code, 'tests': [{'id': id, 'status': status}]}}}
        self.assertTrue(valid_reproduction(run(1, 'failure'), run(0, 'passed')))
        self.assertFalse(valid_reproduction(run(1, 'error'), run(0, 'passed')))
        self.assertFalse(valid_reproduction(run(1, 'failure'), run(0, 'passed', 'B')))

    def test_result_cannot_be_silently_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'result.json'
            write_new(path, {'x': 1})
            with self.assertRaises(FileExistsError):
                write_new(path, {'x': 2})
        self.assertEqual(digest({'a': 1, 'b': 2}), digest({'b': 2, 'a': 1}))
