"""Append-only evidence, stable fingerprints and guarded external model calls."""
import hashlib
import json
import os
import time
from pathlib import Path


def digest(value):
    raw = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(raw).hexdigest()


def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as file:
        json.dump(value, file, ensure_ascii=False, indent=2, allow_nan=False)
        file.write('\n')


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def model_status():
    keys = ('LAB_LLM_BASE_URL', 'LAB_LLM_MODEL', 'LAB_LLM_API_KEY')
    missing = [key for key in keys if not os.environ.get(key, '').strip()]
    return {'available': not missing, 'missing': missing,
            'model': os.environ.get('LAB_LLM_MODEL') or None,
            'endpoint_sha256': digest(os.environ['LAB_LLM_BASE_URL'].rstrip('/').encode()) if os.environ.get('LAB_LLM_BASE_URL') else None}


def measured_call(system, payload, max_tokens, response_schema=None):
    """Use the actual production adapter. Never retry or substitute a fixture."""
    from shared.model_client import ask_json
    start = time.monotonic()
    telemetry = {}
    value = ask_json(system, payload, max_tokens=max_tokens, telemetry=telemetry, response_schema=response_schema)
    return {'output': value, 'seconds': time.monotonic() - start,
            'input_sha256': digest({'system': system, 'payload': payload}),
            'max_tokens': max_tokens, 'usage': telemetry.get('usage'), 'cost': None,
            'provider_model_sha256': telemetry.get('provider_model_sha256')}
