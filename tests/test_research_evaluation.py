import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
import os
import http.client
import re
import textwrap
from unittest.mock import patch
from scripts.evaluation.common import digest, write_new
from scripts.evaluation.d11 import extract_archive, targets, validate_candidate, valid_reproduction, plausible, model_summary
from scripts.evaluation.d13 import score, token_f1, validate, input_units
from scripts.evaluation.d13_blind import pack, summarize
from scripts.evaluation.d11_inner import protected_test


class RepairBenchmarkTests(unittest.TestCase):
    def test_test_code_is_protected_and_formatter_fixtures_are_separate(self):
        self.assertTrue(protected_test(Path('tests/test_black.py')))
        self.assertTrue(protected_test(Path('tqdm/tests/tests_tqdm.py')))
        self.assertTrue(protected_test(Path('tests/conftest.py')))
        self.assertFalse(protected_test(Path('tests/data/python37.py')))
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
                info.linkname = '../escape'
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
        compound = run(1, 'failure')
        compound['phases']['trigger']['tests'].append({'id': 'A', 'status': 'error'})
        self.assertTrue(valid_reproduction(compound, run(0, 'passed')))

    def test_candidate_cannot_pass_by_omitting_tests_or_modifying_them(self):
        def execution(ids, unchanged=True):
            return {'phases': {p: {'returncode': 0, 'test_files_unchanged': unchanged,
                                  'tests': [{'id': id, 'status': 'passed'} for id in ids]} for p in ('trigger', 'regression')}}
        reference = execution(['A', 'B'])
        self.assertTrue(plausible(execution(['A', 'B']), reference))
        self.assertFalse(plausible(execution(['A']), reference))
        self.assertFalse(plausible(execution(['A', 'B'], False), reference))
        rows = [{'status': 'reproduced', 'upstream_repair': reference,
                 'model': {'attempts': [{'status': 'executed', 'execution': reference}]}}]
        self.assertEqual(model_summary(rows, True, True)['bounded_loop_test_plausible'], 1)
        self.assertIsNone(model_summary(rows, False, False)['bounded_loop_test_plausible'])

    def test_result_cannot_be_silently_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'result.json'
            write_new(path, {'x': 1})
            with self.assertRaises(FileExistsError):
                write_new(path, {'x': 2})
        self.assertEqual(digest({'a': 1, 'b': 2}), digest({'b': 2, 'a': 1}))

    def test_internal_archive_link_materialized(self):
        raw = io.BytesIO()
        with tarfile.open(fileobj=raw, mode='w') as archive:
            info = tarfile.TarInfo('README'); info.size = 4
            archive.addfile(info, io.BytesIO(b'text'))
            info = tarfile.TarInfo('docs/readme'); info.type = tarfile.SYMTYPE; info.linkname = '../README'
            archive.addfile(info)
        with tempfile.TemporaryDirectory() as directory:
            extract_archive(raw.getvalue(), Path(directory))
            self.assertFalse((Path(directory) / 'docs/readme').is_symlink())
            self.assertEqual((Path(directory) / 'docs/readme').read_bytes(), b'text')


class LiteratureBenchmarkTests(unittest.TestCase):
    def test_inline_research_workflows_compile(self):
        for path in Path('.github/workflows').glob('*evaluation.yml'):
            for code in re.findall(r"python3 - <<'PY'\n(.*?)\n          PY", path.read_text(), re.S):
                compile(textwrap.dedent(code), str(path), 'exec')

    def test_retrieval_keeps_original_indices_and_excludes_gold(self):
        case = {'question': 'rare method', 'gold': {'secret': 'not for the model'}}
        doc = {'units': ['noise', 'rare method tested', 'another', 'other', 'irrelevant']}
        rows = input_units(case, doc, 'lexical-top4')
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[1], {'index': 1, 'text': 'rare method tested'})
        self.assertNotIn('secret', json.dumps(rows))

    def test_remote_disconnect_is_sanitized_without_retry(self):
        from shared.model_client import ask_json
        with patch.dict(os.environ, {'LAB_LLM_BASE_URL': 'http://localhost/v1', 'LAB_LLM_MODEL': 'fixture', 'LAB_LLM_API_KEY': 'private-test-key'}):
            with patch('urllib.request.urlopen', side_effect=http.client.RemoteDisconnected('private upstream details')) as request:
                with self.assertRaises(ValueError) as result:
                    ask_json('fixture', {})
                self.assertNotIn('private', str(result.exception))
                self.assertEqual(request.call_count, 1)

    def test_model_telemetry_preserves_json_and_redacts_endpoint(self):
        from shared.model_client import ask_json
        raw = {'choices': [{'message': {'content': '{"answer":"ok"}'}}], 'model': 'fixture-model',
               'usage': {'prompt_tokens': 12, 'completion_tokens': 3, 'total_tokens': 15}}
        with patch.dict(os.environ, {'LAB_LLM_BASE_URL': 'https://private.example/v1', 'LAB_LLM_MODEL': 'fixture', 'LAB_LLM_API_KEY': 'private-test-key'}):
            with patch('urllib.request.urlopen') as open_url:
                open_url.return_value.__enter__.return_value = io.StringIO(json.dumps(raw))
                telemetry = {}
                self.assertEqual(ask_json('fixture', {}, telemetry=telemetry), {'answer': 'ok'})
        self.assertEqual(telemetry['usage']['total_tokens'], 15)
        self.assertNotIn('private', json.dumps(telemetry))

    def test_annotation_population_and_no_committed_paper_text(self):
        m = json.loads(Path('evaluations/d13/manifest.json').read_text())
        self.assertEqual(len(m['documents']), 20)
        self.assertEqual(len(m['cases']), 60)
        self.assertEqual({c['domain'] for c in m['cases']}, {'biomedicine', 'nlp'})
        self.assertTrue(all('gold' not in c for c in m['cases']))

    def test_evidence_validation_and_distinct_metric_types(self):
        doc = {'units': ['first', 'second']}
        for evidence in ([True], [-1], [2], [0, 0]):
            with self.assertRaises(ValueError):
                validate({'answer': 'yes', 'label': 'SUPPORT', 'evidence': evidence}, doc, 'claim_verification')
        prediction = validate({'answer': 'The result.', 'label': 'SUPPORT', 'evidence': [0]}, doc, 'claim_verification')
        self.assertEqual(score(prediction, {'task': 'claim_verification', 'gold': {'label': 'SUPPORT', 'rationales': [[0]]}}), {'evidence_f1': 1, 'label_correct': 1})
        self.assertEqual(token_f1('The result.', 'result'), 1)

    def test_blinding_and_unfilled_reviews_rejected(self):
        data = {'documents': [{'dataset': 'test', 'id': 'p', 'title': 'Teaching fixture', 'scope': 'fixture', 'units': ['text']}],
                'cases': [{'id': 'c', 'paper': 'p', 'dataset': 'test', 'question': 'question', 'task': 'paper_qa', 'gold': {'answer': 'hidden'}}]}
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            runs = []
            for mode in ('single', 'staged'):
                run = base / mode; run.mkdir(); runs.append(run)
                write_new(run / 'summary.json', {'dataset_sha256': digest(data), 'mode': mode})
                write_new(run / 'c.json', {'id': 'c', 'status': 'completed', 'prediction': {'answer': 'text', 'evidence': [0]}})
            output = base / 'pack'
            self.assertEqual(pack(data, runs, output), 2)
            text = (output / 'review-pack.json').read_text()
            for secret in ('"mode"', 'single', 'staged', 'hidden'):
                self.assertNotIn(secret, text)
            with self.assertRaises(ValueError):
                summarize(json.loads((output / 'unblinding.json').read_text()), output / 'reviewer-A.csv', output / 'reviewer-B.csv')
