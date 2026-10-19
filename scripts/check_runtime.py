"""Smoke-check the selected interpreter before writing a successful setup stamp."""
import argparse
import importlib.metadata
from pathlib import Path
import re
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manager', choices=['conda', 'venv'], required=True)
    args = parser.parse_args()
    version = sys.version_info[:2]
    if args.manager == 'conda' and version != (3, 12):
        raise RuntimeError('Conda environment must use Python 3.12.')
    if not (3, 10) <= version < (3, 14):
        raise RuntimeError('Supported Python range: 3.10-3.13; Python 3.12 recommended.')
    for package, lower, upper in [('numpy', (2, 0), (3, 0)), ('scikit-learn', (1, 5), (2, 0)), ('pypdf', (6, 10), (7, 0))]:
        raw = importlib.metadata.version(package)
        match = re.match(r'^(\d+)\.(\d+)', raw)
        if not match or not lower <= tuple(map(int, match.groups())) < upper:
            raise RuntimeError('Unsupported {} version: {}'.format(package, raw))
    if args.manager == 'conda':
        node = subprocess.check_output(['node', '--version'], text=True).strip()
        if not node.startswith('v22.'):
            raise RuntimeError('The shared Conda environment must include Node.js 22.')
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import server  # Loads all six Python engines and the UTF-8 corpora; does not listen.
    if not server.rag.DOCS:
        raise RuntimeError('Bundled corpus is empty; inspect the checkout.')
    print('Ready: Python {}.{} / NumPy {} / scikit-learn {}'.format(
        *version, importlib.metadata.version('numpy'), importlib.metadata.version('scikit-learn')))


if __name__ == '__main__':
    main()
