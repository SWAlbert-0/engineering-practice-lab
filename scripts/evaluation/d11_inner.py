"""Runs inside a disposable, network-disabled container; receives public code only."""
import json
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET


def prepare_source(config):
    os.chdir('/work')
    if Path('/work/source').exists():
        shutil.rmtree('/work/source')
    shutil.copytree('/input/source', '/work/source', symlinks=False)
    os.chdir('/work/source')
    # Black's historical tests need a package marker; no application source change.
    if config['project'] == 'black':
        Path('tests/__init__.py').touch()
        if not Path('_black_version.py').exists():
            Path('_black_version.py').write_text('version = "0+bugsinpy.' + config['commit'][:7] + '"\n')


def protected_test(path):
    # Formatter tests deliberately rewrite source fixtures under tests/data.
    # Freeze executable test modules; preserve fixture mutations as evidence.
    return path.suffix == '.py' and (path.name.startswith('test') or path.name in ('conftest.py', '__init__.py'))


def main():
    config = json.loads(Path('/input/config.json').read_text())
    if config['local_httpbin']:
        with open('/work/httpbin.log', 'w') as log:
            service = subprocess.Popen([sys.executable, '-c', 'from httpbin import app; from wsgiref.simple_server import make_server, ServerHandler; ServerHandler.http_version="1.1"; make_server("127.0.0.1",80,app).serve_forever()'], stdout=log, stderr=log, cwd='/tmp')
        for _ in range(100):
            try:
                urllib.request.urlopen('http://127.0.0.1/get', timeout=.2).close()
                break
            except OSError:
                time.sleep(.05)
        else:
            raise RuntimeError('local HTTPbin fixture did not become ready')
    results = {}
    for phase in ('trigger', 'regression'):
        # Both phases start from the same original bytes, including fixtures.
        prepare_source(config)
        files = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('.').rglob('*')
                 if p.is_file() and any(part in ('test', 'tests', 'testing') for part in p.parts)}
        protected = {p: sha for p, sha in files.items() if protected_test(p)}
        start = time.monotonic()
        command = [sys.executable, '-m', 'pytest', '-q', '-o', 'addopts=',
                   '--junitxml=/work/' + phase + '.xml'] + config[phase]
        if config['project'] == 'httpie' and not config['legacy_pytest']:
            command += ['-p', 'pytest_httpbin.plugin']
        if config['legacy_pytest']:
            command += ['--assert=plain']
        with open('/work/' + phase + '.log', 'w') as log:
            try:
                result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=150)
                code = result.returncode
            except subprocess.TimeoutExpired:
                code = 124
        tests = []
        xml = Path('/work/' + phase + '.xml')
        if xml.exists():
            root = ET.parse(xml).getroot()
            for case in root.iter('testcase'):
                state = next((tag for tag in ('failure', 'error', 'skipped') if case.find(tag) is not None), 'passed')
                tests.append({'id': case.get('classname', '') + '::' + case.get('name', ''), 'status': state})
        log = Path('/work/' + phase + '.log').read_text(errors='replace')
        results[phase] = {'returncode': code, 'seconds': time.monotonic() - start,
                          'tests': tests, 'log': log[-80000:], 'log_truncated': len(log) > 80000}
        results[phase]['test_files_unchanged'] = all(p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest() == sha for p, sha in protected.items())
        results[phase]['fixture_files_changed'] = [str(p) for p, sha in files.items() if p not in protected and (not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != sha)]
    print('LAB_EVALUATION_JSON=' + json.dumps(results))


if __name__ == '__main__':
    main()
