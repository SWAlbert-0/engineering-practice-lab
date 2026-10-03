"""Deployment failure/reuse contracts; no package downloads in this test suite."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('launch', Path(__file__).resolve().parents[1] / 'launch.py')
launch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launch)


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='project setup 中文 ')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.patch = patch.object(launch, 'ROOT', self.root)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        (self.root / 'environment.yml').write_text('name: engineering-practice-lab\n', encoding='utf-8')
        (self.root / 'requirements.txt').write_text('numpy>=2.0,<3\n', encoding='utf-8')

    def test_requested_conda_never_falls_back_to_pip(self):
        with patch.object(launch, 'find_conda', return_value=None), patch.object(launch, 'prepare_venv') as venv:
            with self.assertRaisesRegex(launch.SetupError, 'no pip fallback'):
                launch.main(['--manager', 'conda', '--check'])
            venv.assert_not_called()

    def test_conda_creation_and_reuse_do_not_use_pip_or_activation(self):
        prefix = self.root / 'envs' / launch.ENV_NAME
        calls = []
        def run(args, **kwargs):
            args = list(map(str, args));calls.append(args)
            if args[1:4] == ['env', 'list', '--json']:
                return subprocess.CompletedProcess(args, 0, json.dumps({'envs':[str(prefix)] if prefix.exists() else []}))
            if args[1:3] == ['env', 'create']:
                prefix.mkdir(parents=True)
            return subprocess.CompletedProcess(args, 0, 'Ready', '')
        with patch.object(launch, 'execute', side_effect=run):
            launch.prepare_conda('/tools/conda')
            launch.prepare_conda('/tools/conda')
        self.assertEqual(sum(c[1:3] == ['env','create'] for c in calls), 1)
        self.assertFalse(any('update' in c for c in calls))
        self.assertFalse(any('pip' in c or 'activate' in c for c in calls))
        self.assertTrue(launch.stamped(prefix, self.root / 'environment.yml'))

    def test_manifest_change_updates_existing_conda_without_prune(self):
        prefix = self.root / launch.ENV_NAME;prefix.mkdir()
        manifest = self.root / 'environment.yml';launch.write_stamp(prefix, manifest)
        manifest.write_text('name: engineering-practice-lab\n# changed\n', encoding='utf-8')
        with patch.object(launch, 'conda_prefix', return_value=prefix), patch.object(launch, 'health'), patch.object(launch, 'execute') as run:
            launch.prepare_conda('conda')
        command = run.call_args.args[0]
        self.assertIn('update', command)
        self.assertNotIn('--prune', command)
        self.assertNotIn('--yes', command)  # env update does not accept this flag.

    def test_failed_update_removes_stamp_and_does_not_start_service(self):
        prefix = self.root / launch.ENV_NAME;prefix.mkdir()
        launch.write_stamp(prefix, self.root / 'environment.yml')
        with patch.object(launch, 'conda_prefix', return_value=prefix), patch.object(launch, 'health') as health, patch.object(launch, 'execute', side_effect=launch.SetupError('offline')):
            with self.assertRaises(launch.SetupError):launch.prepare_conda('conda', True)
        self.assertFalse((prefix / launch.STAMP).exists())
        health.assert_not_called()

    def test_no_success_stamp_after_health_failure(self):
        prefix = self.root / launch.ENV_NAME;prefix.mkdir()
        with patch.object(launch, 'conda_prefix', return_value=prefix), patch.object(launch, 'execute'), patch.object(launch, 'health', side_effect=launch.SetupError('import failed')):
            with self.assertRaises(launch.SetupError):launch.prepare_conda('conda')
        self.assertFalse((prefix / launch.STAMP).exists())

    def test_venv_install_uses_only_its_interpreter_and_reuses(self):
        prefix = self.root / '.venv';prefix.mkdir()
        (prefix / 'pyvenv.cfg').write_text('test', encoding='utf-8')
        python = launch.venv_python(prefix);python.parent.mkdir(exist_ok=True);python.touch()
        with patch.object(launch, 'health'), patch.object(launch, 'execute', return_value=subprocess.CompletedProcess([],0)) as run:
            launch.prepare_venv()
            launch.prepare_venv()
        installs = [c.args[0] for c in run.call_args_list if 'pip' in c.args[0]]
        self.assertEqual(len(installs), 1)
        self.assertEqual(installs[0][0], python)
        self.assertEqual(installs[0][1:3], ['-m','pip'])

    def test_invalid_existing_venv_is_never_overwritten(self):
        prefix=self.root / '.venv';prefix.mkdir();(prefix / 'important.txt').write_text('keep')
        with patch.object(launch, 'execute') as run:
            with self.assertRaisesRegex(launch.SetupError, 'not a valid'):launch.prepare_venv()
        run.assert_not_called();self.assertEqual((prefix / 'important.txt').read_text(),'keep')

    def test_busy_port_stops_before_install(self):
        with patch.object(launch, 'find_conda', return_value='conda'), patch.object(launch, 'check_port', side_effect=launch.SetupError('busy')), patch.object(launch, 'prepare_conda') as prepare:
            with self.assertRaises(launch.SetupError):launch.main([])
        prepare.assert_not_called()

    def test_runtime_manifest_ranges_match(self):
        root=Path(__file__).resolve().parents[1]
        conda=(root / 'environment.yml').read_text(encoding='utf-8')
        for line in (root / 'requirements.txt').read_text(encoding='utf-8').splitlines():
            if line and not line.startswith('#'):self.assertIn(line,conda)


if __name__ == '__main__':
    unittest.main()
