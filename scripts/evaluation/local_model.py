"""Verified optional Linux/x86_64 CPU model runtime; no Python packages installed."""
import argparse
import hashlib
import os
from pathlib import Path
import platform
import subprocess
import tarfile
import urllib.request

from .common import write_new

BINARY_URL = 'https://github.com/ggml-org/llama.cpp/releases/download/b11753/llama-b11753-bin-ubuntu-x64.tar.gz'
BINARY_SHA = 'af40d3acec2ebae7ca3c26cdfa012d4cb6d4ae598aa668194d27c5252a435b62'
MODEL_URL = 'https://huggingface.co/Qwen/Qwen3-0.6B-GGUF/resolve/23749fefcc72300e3a2ad315e1317431b06b590a/Qwen3-0.6B-Q8_0.gguf'
MODEL_SHA = '9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031'


def sha(path):
    with path.open('rb') as file:
        return hashlib.file_digest(file, 'sha256').hexdigest()


def download(url, path, expected, max_bytes):
    if path.exists() and sha(path) == expected:
        return
    temporary = path.with_suffix('.part')
    with urllib.request.urlopen(url, timeout=60) as response, temporary.open('wb') as file:
        count = 0
        while chunk := response.read(4 * 1024 * 1024):
            count += len(chunk)
            if count > max_bytes:
                raise ValueError('download exceeds pinned size limit')
            file.write(chunk)
    if sha(temporary) != expected:
        raise ValueError('download digest mismatch; runtime not executed')
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--serve', action='store_true')
    parser.add_argument('--port', type=int, default=8790)
    parser.add_argument('--threads', type=int, default=2)
    args = parser.parse_args()
    if platform.system() != 'Linux' or platform.machine() not in ('x86_64', 'AMD64'):
        parser.error('This pinned optional runtime requires Linux x86_64; use your own compatible service elsewhere.')
    if not 1024 <= args.port <= 65535 or not 1 <= args.threads <= 16:
        parser.error('invalid port/thread count')
    root = args.directory.resolve()
    root.mkdir(parents=True, exist_ok=True)
    archive, model = root / 'llama.tgz', root / 'model.gguf'
    download(BINARY_URL, archive, BINARY_SHA, 30 * 1024 * 1024)
    download(MODEL_URL, model, MODEL_SHA, 640 * 1024 * 1024)
    binary = root / 'llama-b11753/llama-server'
    if not binary.exists():
        with tarfile.open(archive) as package:
            package.extractall(root, filter='data')
    settings = {'model': 'Qwen/Qwen3-0.6B-GGUF', 'revision': '23749fefcc72300e3a2ad315e1317431b06b590a',
                'weight_sha256': MODEL_SHA, 'quantization': 'Q8_0', 'runtime': 'llama.cpp b11753',
                'binary_archive_sha256': BINARY_SHA, 'cpu_only': True, 'threads': args.threads,
                'context': 32768, 'thinking': False, 'seed': 0,
                'scope': 'Small-model diagnostic baseline; not a recommended production model or independent expert assessment',
                'model_source': MODEL_URL, 'runtime_source': BINARY_URL}
    provenance = root / 'provenance.json'
    if not provenance.exists():
        write_new(provenance, settings)
    if args.serve:
        argsv = [str(binary), '-m', str(model), '--host', '127.0.0.1', '--port', str(args.port),
                 '--alias', 'qwen3-0.6b-q8-eval', '-c', '32768', '-t', str(args.threads),
                 '-tb', str(args.threads), '-np', '1', '--jinja', '--seed', '0',
                 '--chat-template-kwargs', '{"enable_thinking":false}', '--reasoning-budget', '0',
                 '--reasoning-format', 'deepseek', '--no-webui']
        os.execv(str(binary), argsv)
    print(provenance)


if __name__ == '__main__':
    main()
