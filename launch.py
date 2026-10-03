"""Prepare one shared environment and run the local project. Standard library only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
ENV_NAME = 'engineering-practice-lab'
STAMP = '.engineering-practice-lab-deps.json'


class SetupError(RuntimeError):
    pass


def execute(args, capture=False, check=True):
    # No shell interpolation; spaces and non-ASCII paths remain single arguments.
    env = os.environ.copy()
    env.update(PYTHONUTF8='1', PYTHONIOENCODING='utf-8', PYTHONUNBUFFERED='1')
    result = subprocess.run([str(a) for a in args], cwd=ROOT, env=env,
                            capture_output=capture, text=True, encoding='utf-8')
    if check and result.returncode:
        if capture:
            print(result.stderr or result.stdout, file=sys.stderr)
        raise SetupError('Command failed (exit {}). Fix the error above and retry; '
                         'the server was not started.'.format(result.returncode))
    return result


def find_conda():
    value = os.environ.get('CONDA_EXE')
    if value and Path(value).is_file():
        return value
    return shutil.which('conda')


def digest(path):
    # Normalize checkout line endings, so Windows/Linux clones share the same key.
    return hashlib.sha256(path.read_text(encoding='utf-8').encode('utf-8')).hexdigest()


def stamped(prefix, manifest):
    try:
        data = json.loads((prefix / STAMP).read_text(encoding='utf-8'))
        return data == {'manifest': manifest.name, 'sha256': digest(manifest)}
    except (OSError, ValueError):
        return False


def write_stamp(prefix, manifest):
    path = prefix / STAMP
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps({'manifest': manifest.name, 'sha256': digest(manifest)}), encoding='utf-8')
    tmp.replace(path)


def conda_prefix(conda):
    info = json.loads(execute([conda, 'env', 'list', '--json'], capture=True).stdout)
    matches = list(dict.fromkeys(str(Path(p).resolve()) for p in info['envs']
                                if Path(p).name == ENV_NAME))
    if len(matches) > 1:
        raise SetupError('Multiple environments named {} were found. Use one Conda installation '
                         'with an unambiguous project environment.'.format(ENV_NAME))
    return Path(matches[0]) if matches else None


def health(runner, manager):
    result = execute(runner + [ROOT / 'scripts' / 'check_runtime.py', '--manager', manager],
                     capture=True, check=False)
    if result.returncode:
        print(result.stderr or result.stdout, file=sys.stderr)
        raise SetupError('Environment check failed. Retry with --update (PowerShell: -Update). '
                         'If Python is incompatible, see docs/DEPLOYMENT.md.')
    print(result.stdout.strip(), flush=True)


def prepare_conda(conda, update=False):
    manifest = ROOT / 'environment.yml'
    prefix = conda_prefix(conda)
    if prefix is None:
        print('[1/3] Creating shared Conda environment: ' + ENV_NAME, flush=True)
        execute([conda, 'env', 'create', '--name', ENV_NAME, '--file', manifest, '--yes'])
        prefix = conda_prefix(conda)
        if prefix is None:
            raise SetupError('Conda finished without registering the project environment.')
    elif update or not stamped(prefix, manifest):
        print('[1/3] Synchronizing Conda environment from environment.yml', flush=True)
        (prefix / STAMP).unlink(missing_ok=True)
        # No prune: do not remove unrelated developer tools from the shared env.
        execute([conda, 'env', 'update', '--prefix', prefix, '--file', manifest])
    else:
        print('[1/3] Reusing Conda environment (dependencies unchanged)', flush=True)
    runner = [conda, 'run', '--no-capture-output', '--prefix', prefix, 'python']
    print('[2/3] Checking Python, dependencies and project imports', flush=True)
    health(runner, 'conda')
    write_stamp(prefix, manifest)
    return runner


def venv_python(prefix):
    return prefix / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')


def prepare_venv(update=False):
    prefix = ROOT / '.venv'
    python = venv_python(prefix)
    manifest = ROOT / 'requirements.txt'
    created = False
    if not (prefix / 'pyvenv.cfg').is_file():
        if prefix.exists():
            raise SetupError('.venv exists but is not a valid virtual environment. '
                             'Move it aside before retrying; it will not be deleted automatically.')
        if not (3, 10) <= sys.version_info[:2] < (3, 14):
            raise SetupError('The no-Conda route needs Python 3.10-3.13 (3.12 recommended). '
                             'Run launch.py with that interpreter, or use Conda.')
        print('[1/3] Creating shared virtual environment: ' + str(prefix), flush=True)
        execute([sys.executable, '-m', 'venv', prefix])
        created = True
    if not python.is_file():
        raise SetupError('.venv has no Python executable. Move this incomplete environment '
                         'aside and retry; see docs/DEPLOYMENT.md.')
    # Check before installing; never invoke the global interpreter's pip.
    compatible = execute([python, '-c',
                          'import sys,pathlib; sys.exit(not ((3,10)<=sys.version_info[:2]<(3,14) '
                          'and sys.prefix!=sys.base_prefix '
                          'and pathlib.Path(sys.prefix).resolve()==pathlib.Path(sys.argv[1]).resolve()))',
                          prefix],
                         check=False, capture=True)
    if compatible.returncode:
        raise SetupError('Existing .venv needs Python 3.10-3.13. Move it aside and recreate with Python 3.12.')
    if created or update or not stamped(prefix, manifest):
        print('[1/3] Installing runtime dependencies inside .venv only', flush=True)
        (prefix / STAMP).unlink(missing_ok=True)
        execute([python, '-m', 'pip', 'install', '--disable-pip-version-check', '-r', manifest])
    else:
        print('[1/3] Reusing .venv (dependencies unchanged)', flush=True)
    print('[2/3] Checking Python, dependencies and project imports', flush=True)
    health([python], 'venv')
    write_stamp(prefix, manifest)
    return [python]


def check_port(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(('127.0.0.1', port))
        except OSError as error:
            raise SetupError('Cannot use 127.0.0.1:{}. Stop the existing service or use '
                             '--port 8766 (PowerShell: -Port 8766). {}'.format(port, error)) from error


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manager', choices=['auto', 'conda', 'venv'], default='auto')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--update', action='store_true', help='synchronize dependencies even if unchanged')
    parser.add_argument('--check', action='store_true', help='prepare and check environment, then exit')
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error('--port must be between 1 and 65535')
    conda = find_conda()
    manager = ('conda' if conda else 'venv') if args.manager == 'auto' else args.manager
    if manager == 'conda' and not conda:
        raise SetupError('Conda was requested but is not available. Use Anaconda Prompt '
                         'or initialize Conda in this terminal; no pip fallback was attempted.')
    if not args.check:
        check_port(args.port)
    print('Project: {}\nEnvironment manager: {}'.format(ROOT, manager), flush=True)
    runner = prepare_conda(conda, args.update) if manager == 'conda' else prepare_venv(args.update)
    if args.check:
        print('[3/3] Environment ready. Run the same command without --check to start.', flush=True)
        return 0
    check_port(args.port)
    print('[3/3] Starting http://127.0.0.1:{} (Ctrl+C to stop)'.format(args.port), flush=True)
    # The child inherits the console/process group, so Ctrl+C reaches the server.
    return execute(runner + [ROOT / 'server.py', '--port', str(args.port)], check=False).returncode


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print('\nStopped.')
        sys.exit(130)
    except (SetupError, OSError, ValueError) as error:
        print('\nStartup failed: {}'.format(error), file=sys.stderr)
        sys.exit(1)
