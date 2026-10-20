"""Runs inside a disposable, network-disabled container; receives public code only."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET


def main():
    shutil.copytree('/input/source', '/work/source', symlinks=False)
    config = json.loads(Path('/input/config.json').read_text())
    os.chdir('/work/source')
    sys.path.insert(0, os.getcwd())
    # Black's historical tests need a package marker; no application source change.
    if config['project'] == 'black':
        Path('tests/__init__.py').touch()
    results = {}
    for phase in ('trigger', 'regression'):
        start = time.monotonic()
        command = [sys.executable, '-m', 'pytest', '-q', '-o', 'addopts=',
                   '--junitxml=/work/' + phase + '.xml'] + config[phase]
        if config['project'] == 'httpie':
            command += ['-p', 'pytest_httpbin.plugin']
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
    print('LAB_EVALUATION_JSON=' + json.dumps(results))


if __name__ == '__main__':
    main()
