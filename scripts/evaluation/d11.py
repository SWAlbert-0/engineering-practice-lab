"""Fixed BugsInPy subset: reproduce, verify upstream repairs, optionally test models.

Run as `python -m scripts.evaluation.d11 --help` from the repository root.
No downloaded program or setup.py executes on the host. Dependency installation is
confined to an evaluation image, separate from the shared application environment.
"""
import argparse
import io
import json
import os
import posixpath
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import subprocess
import tarfile
import tempfile
import time
import uuid

from .common import digest, load, measured_call, model_status, write_new

ROOT = Path(__file__).resolve().parents[2]
PROJECTS = ('black', 'httpie', 'tornado', 'tqdm', 'youtube-dl')
DEPENDENCIES = {
    'black': ['click==7.1.2', 'regex==2020.11.13', 'typed-ast==1.4.3', 'toml==0.10.2',
              'appdirs==1.4.4', 'pathspec==0.8.1', 'mypy-extensions==0.4.3',
              'aiohttp==3.7.4.post0', 'aiohttp-cors==0.7.0', 'typing-extensions==3.10.0.2'],
    'httpie': ['requests==2.25.1', 'urllib3==1.26.18', 'Pygments==2.8.1',
               'requests-toolbelt==0.9.1', 'responses==0.13.3', 'pytest-httpbin==1.0.0',
               'httpbin==0.7.0', 'Flask==1.1.4', 'Werkzeug==1.0.1', 'Jinja2==2.11.3',
               'MarkupSafe==1.1.1', 'itsdangerous==1.1.0', 'mock==4.0.3', 'six==1.16.0'],
    'tornado': ['mock==4.0.3'],
    'tqdm': ['nose==1.3.7', 'six==1.16.0'],
    'youtube-dl': [],
}


def command(args, cwd=None, timeout=300, binary=False):
    result = subprocess.run(args, cwd=cwd, capture_output=True, timeout=timeout)
    if result.returncode:
        # Commands contain public repository refs only, never model credentials.
        raise RuntimeError('command failed: ' + ' '.join(args[:4]) + '\n' + result.stderr.decode(errors='replace')[-4000:])
    return result.stdout if binary else result.stdout.decode('utf-8', errors='replace').strip()


def safe_path(name):
    path = PurePosixPath(name)
    if not name or path.is_absolute() or '..' in path.parts or '\\' in name or path.parts[0] == '.git':
        raise ValueError('unsafe repository path')
    return path


def extract_archive(raw, destination):
    """Materialize safe internal file links; never create host filesystem links."""
    omitted = []
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        def regular(member, seen=()):
            if member.name in seen or len(seen) >= 8:
                raise ValueError('cyclic archive link')
            if member.isfile():
                return archive.extractfile(member).read()
            if member.isdir():
                raise IsADirectoryError(member.name)
            if member.issym():
                target = posixpath.normpath(posixpath.join(posixpath.dirname(member.name), member.linkname))
                safe_path(target)
                return regular(archive.getmember(target), (*seen, member.name))
            raise ValueError('repository archive contains a special file')
        for member in archive:
            path = safe_path(member.name)
            target = destination.joinpath(*path.parts)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            elif member.isfile() or member.issym():
                target.parent.mkdir(parents=True, exist_ok=True)
                try:
                    content = regular(member)
                except (KeyError, IsADirectoryError):
                    if not member.name.startswith(('docs/', 'maint/test/appengine/')):
                        raise ValueError('missing non-documentation link target') from None
                    omitted.append(member.name)
                    continue
                target.write_bytes(content)
            else:
                raise ValueError('repository archive contains a link or special file')
    return omitted


def is_test(path):
    return any(p in ('test', 'tests', 'testing') for p in PurePosixPath(path).parts)


def targets(case):
    result = []
    for line in case['test_commands']:
        words = shlex.split(line)
        if words[:3] in (['python', '-m', 'unittest'], ['python3', '-m', 'unittest']):
            for word in words[3:]:
                if word.startswith('-'):
                    continue
                found = False
                for file in case['test_files']:
                    module = file.removesuffix('.py').replace('/', '.')
                    if word == module or word.startswith(module + '.'):
                        suffix = word[len(module):].strip('.').replace('.', '::')
                        result.append(file + ('::' + suffix if suffix else ''))
                        found = True
                        break
                if not found:
                    raise ValueError('test module not declared in metadata')
        elif words[0] == 'pytest' or words[:3] in (['python', '-m', 'pytest'], ['python3', '-m', 'pytest']):
            arguments = words[1:] if words[0] == 'pytest' else words[3:]
            result.extend(word for word in arguments if not word.startswith('-'))
        else:
            raise ValueError('unsupported test command; shell execution prohibited')
    for target in result:
        safe_path(target.split('::')[0])
        if target.split('::')[0] not in case['test_files']:
            raise ValueError('undeclared target')
    if not result:
        raise ValueError('empty test selection')
    return list(dict.fromkeys(result))


def prepare(case, cache, destination):
    repo = cache / case['project']
    if not repo.exists():
        command(['git', 'clone', '--bare', '--filter=blob:none', case['repository'], str(repo)], timeout=600)
    for key in ('buggy_commit', 'fixed_commit'):
        if not re.fullmatch('[0-9a-f]{40}', case[key]):
            raise ValueError('commit must be fixed SHA')
        command(['git', 'cat-file', '-e', case[key] + '^{commit}'], repo)
    source = destination / 'source'
    source.mkdir()
    omitted = extract_archive(command(['git', 'archive', case['buggy_commit']], repo, binary=True), source)
    # Follow BugsInPy's checkout semantics: the fix commit's changed files, not
    # an unrestricted diff across potentially distant buggy/fixed commits.
    changed = command(['git', 'diff-tree', '--no-commit-id', '--name-only', '-r', case['fixed_commit']], repo).splitlines()
    tests = set(case['test_files']) | {p for p in changed if is_test(p)}
    frozen = {}
    for name in sorted(tests):
        safe_path(name)
        try:
            raw = command(['git', 'show', case['fixed_commit'] + ':' + name], repo, binary=True)
        except RuntimeError:
            # A removed test is removed from both versions.
            (source / name).unlink(missing_ok=True)
            frozen[name] = None
            continue
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        frozen[name] = digest(raw)
    production = [p for p in changed if p not in tests and not is_test(p)]
    gold = {}
    for name in production:
        safe_path(name)
        try:
            gold[name] = command(['git', 'show', case['fixed_commit'] + ':' + name], repo, binary=True)
        except RuntimeError:
            gold[name] = None
    config = {'project': case['project'], 'trigger': targets(case),
              'regression': sorted({t.split('::')[0] for t in targets(case)})}
    config['legacy_pytest'] = case['project'] == 'httpie' and case['bug_id'] == 1
    config['local_httpbin'] = case['project'] == 'httpie' and case['bug_id'] == 4
    config['commit'] = case['buggy_commit']
    (destination / 'config.json').write_text(json.dumps(config))
    (destination / 'source-preparation.json').write_text(json.dumps({'omitted_non_runtime_links': omitted,
        'safe_internal_links': 'materialized as regular files; no host symlinks created',
        'httpbin_fixture': 'httpbin.org mapped to loopback HTTPbin 0.7.0 port 80; no external network' if config['local_httpbin'] else None,
        'base_snapshot_sha256': digest({str(p.relative_to(source)): digest(p.read_bytes()) for p in sorted(source.rglob('*')) if p.is_file()})}))
    return gold, frozen


def build_image(project, directory, profile='default'):
    packages = ['pytest==6.2.5', 'setuptools==57.5.0', 'wheel==0.37.1'] + DEPENDENCIES[project]
    if profile.startswith('httpie-legacy'):
        packages = [p for p in packages if not p.startswith(('requests==', 'requests-toolbelt=='))]
        packages.append('requests==2.0.0')
    if profile == 'httpie-legacy-fixtures':
        packages = ['pytest==3.2.1' if p.startswith('pytest==') else p for p in packages]
    dockerfile = 'FROM python:3.8.20-slim-bullseye\nRUN python -m pip install --no-cache-dir ' + ' '.join(packages) + '\nUSER 10001:10001\n'
    (directory / 'Dockerfile').write_text(dockerfile)
    tag = 'lab-eval-' + project.lower() + ':' + digest(dockerfile.encode())[:12]
    command(['docker', 'build', '-t', tag, str(directory)], timeout=600)
    return command(['docker', 'image', 'inspect', '--format={{.Id}}', tag])


def execute(directory, image):
    name = 'lab-eval-' + uuid.uuid4().hex
    start = time.monotonic()
    args = ['docker', 'run', '--name', name, '--network=none', '--read-only',
            '--cap-drop=ALL', '--security-opt=no-new-privileges', '--user=10001:10001',
            '--memory=768m', '--memory-swap=768m', '--cpus=1', '--pids-limit=128',
            '--tmpfs=/work:rw,nosuid,size=256m,mode=1777', '--tmpfs=/tmp:rw,nosuid,size=64m,mode=1777',
            '-e', 'PYTHONDONTWRITEBYTECODE=1', '-e', 'PYTEST_DISABLE_PLUGIN_AUTOLOAD=1',
            '-e', 'PYTHONPATH=/work/source', '-e', 'HOME=/tmp',
            '--mount', 'type=bind,src=' + str(directory.resolve()) + ',dst=/input,readonly',
            '--mount', 'type=bind,src=' + str((ROOT / 'scripts/evaluation/d11_inner.py').resolve()) + ',dst=/runner.py,readonly',
            image, 'python', '/runner.py']
    if load(directory / 'config.json')['local_httpbin']:
        args[2:2] = ['--add-host=httpbin.org:127.0.0.1', '--sysctl=net.ipv4.ip_unprivileged_port_start=0']
    try:
        raw = command(args, timeout=340)
        line = next((x for x in raw.splitlines() if x.startswith('LAB_EVALUATION_JSON=')), None)
        if not line:
            raise RuntimeError('test runner produced no result')
        return {'environment_image_id': image, 'seconds': time.monotonic() - start,
                'phases': json.loads(line.split('=', 1)[1])}
    finally:
        subprocess.run(['docker', 'rm', '-f', name], capture_output=True)


def valid_reproduction(buggy, fixed):
    before, after = buggy['phases']['trigger'], fixed['phases']['trigger']
    b = {t['id'] for t in before['tests']}
    a = {t['id']: t['status'] for t in after['tests']}
    failures = {t['id'] for t in before['tests'] if t['status'] == 'failure'}
    errors = {t['id'] for t in before['tests'] if t['status'] == 'error'}
    return (before['returncode'] == 1 and after['returncode'] == 0 and b == a.keys()
            and bool(failures) and all(v == 'passed' for v in a.values())
            and not errors.difference(failures)
            and before.get('test_files_unchanged', True) and after.get('test_files_unchanged', True))


def plausible(execution, reference):
    for phase in ('trigger', 'regression'):
        value = execution['phases'][phase]
        expected = {t['id'] for t in reference['phases'][phase]['tests']}
        actual = {t['id'] for t in value['tests']}
        skipped = {t['id'] for t in reference['phases'][phase]['tests'] if t['status'] == 'skipped'}
        if (not expected or expected != actual or value['returncode'] != 0
                or not value.get('test_files_unchanged', False)
                or any(t['status'] != 'passed' and not (t['status'] == 'skipped' and t['id'] in skipped) for t in value['tests'])):
            return False
    return True


def model_summary(results, requested, available):
    measured = requested and available
    eligible = [r for r in results if r['status'] == 'reproduced']
    attempts = [a for r in eligible for a in (r.get('model') or {}).get('attempts', [])]
    first, final = 0, 0
    for row in eligible:
        tries = (row.get('model') or {}).get('attempts', [])
        if tries and tries[0].get('execution') and plausible(tries[0]['execution'], row['upstream_repair']):
            first += 1
        if any(a.get('execution') and plausible(a['execution'], row['upstream_repair']) for a in tries):
            final += 1
    return {'eligible_reproduced': len(eligible), 'single_round_test_plausible': first if measured else None,
            'bounded_loop_test_plausible': final if measured else None,
            'bounded_loop_rate_all_selected': final / len(results) if measured and results else None,
            'bounded_loop_rate_reproduced': final / len(eligible) if measured and eligible else None,
            'rejected_candidate_count': sum(a['status'] == 'rejected' for a in attempts) if measured else None,
            'actual_recorded_calls': len(attempts), 'usage': None, 'cost': None,
            'interpretation': 'Test-plausible on public trigger and relevant-module tests; no hidden correctness or contamination-free claim'}


def validate_candidate(value, allowed):
    files = value.get('files')
    if not isinstance(files, list) or not files or len(files) > len(allowed):
        raise ValueError('candidate files must be nonempty and bounded')
    result = {}
    for row in files:
        name, content = row.get('path'), row.get('content')
        safe_path(name)
        if name not in allowed or is_test(name) or not name.endswith('.py') or name in result:
            raise ValueError('candidate path not allowed')
        if not isinstance(content, str) or not 1 <= len(content.encode()) <= 80000:
            raise ValueError('candidate file size invalid')
        compile(content, name, 'exec')
        result[name] = content.encode()
    return result


def model_attempts(case, directory, gold, image, baseline, reference, budget):
    allowed = sorted(p for p in gold if p.endswith('.py') and not is_test(p))
    originals = {p: (directory / 'source' / p).read_text() for p in allowed if (directory / 'source' / p).exists()}
    if not originals or sum(map(len, originals.values())) > 100000:
        return {'status': 'input_out_of_scope', 'attempts': []}
    prompt = ('Repair the supplied Python files. Return {"files":[{"path":"allowed path","content":"complete file"}]}. '
              'Do not change tests or use external services. This is an oracle-file-localized public benchmark; '
              'only listed files may change. Preserve APIs and behavior beyond the failing tests.')
    feedback = baseline['phases']['trigger']['log'][-12000:]
    attempts = []
    for iteration in range(budget):
        try:
            call = measured_call(prompt, {'files': originals, 'allowed_paths': allowed, 'feedback': feedback}, 6000)
        except ValueError as error:
            return {'status': 'model_error', 'attempts': attempts, 'error': str(error)}
        attempt = {'number': iteration + 1, **call}
        attempts.append(attempt)
        try:
            candidate = validate_candidate(call['output'], allowed)
        except (ValueError, SyntaxError, TypeError, AttributeError) as error:
            attempt['status'] = 'rejected'
            feedback = str(error)
            continue
        for path, content in candidate.items():
            (directory / 'source' / path).write_bytes(content)
        attempt['status'] = 'executed'
        attempt['execution'] = execute(directory, image)
        # Entire relevant module regression, not an independent hidden holdout.
        if plausible(attempt['execution'], reference):
            return {'status': 'test_plausible', 'attempts': attempts}
        originals = {p: (directory / 'source' / p).read_text() for p in originals}
        feedback = attempt['execution']['phases']['trigger']['log'][-12000:]
    return {'status': 'budget_exhausted', 'attempts': attempts}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=ROOT / 'evaluations/d11/manifest.json')
    parser.add_argument('--project', choices=PROJECTS, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cache', type=Path, default=Path('/tmp/lab-evaluation-git'))
    parser.add_argument('--model', action='store_true', help='Explicitly authorize up to 3 paid calls per reproducible case')
    args = parser.parse_args()
    manifest = load(args.manifest)
    cases = [c for c in manifest['cases'] if c['project'] == args.project]
    args.output.mkdir(parents=True, exist_ok=False)
    args.cache.mkdir(parents=True, exist_ok=True)
    status = model_status()
    header = {'schema': 1, 'project': args.project, 'manifest_sha256': digest(manifest),
              'model': status, 'model_requested': args.model, 'source': manifest['dataset'],
              'protocol': 'BugsInPy upstream-repair reproduction; optional oracle-file-localized model repair; public relevant-module tests, no hidden holdout',
              'python_adaptation': 'All cases use Python 3.8.20 and documented project dependencies; original versions retained in manifest',
              'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    write_new(args.output / 'run.json', header)
    results = []
    try:
        if not shutil.which('docker'):
            raise RuntimeError('Docker unavailable; external programs are not executed on the host')
        with tempfile.TemporaryDirectory() as tmp:
            image = build_image(args.project, Path(tmp))
    except (RuntimeError, subprocess.TimeoutExpired) as error:
        for case in cases:
            row = {'id': case['id'], 'status': 'environment_error', 'error': str(error), 'model': None}
            results.append(row)
            write_new(args.output / (case['id'] + '.json'), row)
    else:
        images = {'default': image}
        for case in cases:
            row = {'id': case['id'], 'status': 'started', 'model': None}
            try:
                with tempfile.TemporaryDirectory() as tmp:
                    directory = Path(tmp)
                    directory.chmod(0o755)
                    profile = 'httpie-legacy-fixtures' if case['project'] == 'httpie' and case['bug_id'] == 1 else ('httpie-legacy' if case['project'] == 'httpie' and case['bug_id'] in (4, 5) else 'default')
                    if profile not in images:
                        with tempfile.TemporaryDirectory() as build:
                            images[profile] = build_image(args.project, Path(build), profile)
                    image = images[profile]
                    row['dependency_profile'] = profile
                    gold, tests = prepare(case, args.cache, directory)
                    row['source_preparation'] = load(directory / 'source-preparation.json')
                    row['frozen_test_sha256'] = tests
                    row['production_files'] = sorted(gold)
                    row['buggy'] = execute(directory, image)
                    originals = {p: (directory / 'source' / p).read_bytes() if (directory / 'source' / p).exists() else None for p in gold}
                    for p, content in gold.items():
                        target = directory / 'source' / p
                        if content is None:
                            target.unlink(missing_ok=True)
                        else:
                            target.parent.mkdir(parents=True, exist_ok=True)
                            target.write_bytes(content)
                    row['upstream_repair'] = execute(directory, image)
                    row['status'] = 'reproduced' if valid_reproduction(row['buggy'], row['upstream_repair']) else 'not_reproduced'
                    for p, content in originals.items():
                        target = directory / 'source' / p
                        if content is None:
                            target.unlink(missing_ok=True)
                        else:
                            target.write_bytes(content)
                    if args.model and row['status'] == 'reproduced':
                        row['model'] = model_attempts(case, directory, gold, image, row['buggy'], row['upstream_repair'], 3) if status['available'] else {'status': 'blocked_missing_model', 'attempts': []}
            except (RuntimeError, ValueError, OSError, subprocess.TimeoutExpired) as error:
                row['status'], row['error'] = 'execution_error', str(error)[:4000]
            results.append(row)
            write_new(args.output / (case['id'] + '.json'), row)
            print(case['id'], row['status'], flush=True)
    summary = {**header, 'selected': len(cases), 'reproduced': sum(r['status'] == 'reproduced' for r in results),
               'statuses': {s: sum(r['status'] == s for r in results) for s in sorted({r['status'] for r in results})},
            'model_repair_rate': None, 'model_comparison': model_summary(results, args.model, status['available']), 'results': results}
    write_new(args.output / 'summary.json', summary)
    print(json.dumps({'project': args.project, 'selected': len(cases), 'reproduced': summary['reproduced'], 'statuses': summary['statuses']}))


if __name__ == '__main__':
    main()
