"""Build a read-only, reproducible public view of the committed D11 evidence.

Run with python -m scripts.evaluation.d11_web. No model or repository execution.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATE = '2026-10-20'


def build(root=ROOT):
    sources = {}

    def read(relative):
        # Git checkouts may use CRLF on Windows; hash the canonical LF content.
        raw = (root / relative).read_bytes().replace(b'\r\n', b'\n')
        sources[relative] = hashlib.sha256(raw).hexdigest()
        return json.loads(raw)

    base = f'evaluations/d11/results/{DATE}'
    manifest = read('evaluations/d11/manifest.json')
    summary = read(f'{base}/summary.json')
    result = {}
    rows = []
    for project in sorted({c['project'] for c in manifest['cases']}):
        slug = 'youtube' if project == 'youtube-dl' else project
        reproduction = read(f'{base}/repro-{slug}.json')
        run = read(f'{base}/model-{slug}-raw/run.json')
        records = reproduction['records']
        for case in (c for c in manifest['cases'] if c['project'] == project):
            cid = case['id']
            record = next(r['data'] for r in records
                          if r['marker'] == 'LAB_BENCHMARK_CASE' and r['data']['id'] == cid)
            variants = {r['data']['variant']: r['data'] for r in records
                        if r['marker'] == 'LAB_BENCHMARK_TESTS' and r['data']['id'] == cid}
            raw = read(f'{base}/model-{slug}-raw/{cid}.json')
            model = raw.get('model') or {'status': 'not_eligible_not_reproduced'}
            row = {**case, 'status': record['status'], 'model_status': model['status']}
            rows.append(row)
            result[f'{cid}.json'] = {
                'schema': 1, 'case': row, 'reproduction': record, 'variants': variants,
                'reproduction_run': {k: reproduction[k] for k in ('run_id', 'job_url', 'head_sha')},
                'model': model, 'model_run': run,
                'model_run_id': summary['model_diagnostic']['run_id'],
                'model_source': f'{base}/model-{slug}-raw/{cid}.json',
            }
    result['index.json'] = {
        'schema': 1, 'date': DATE, 'dataset': manifest['dataset'],
        'selection': manifest['selection'], 'cases': rows,
        'summary': {k: summary[k] for k in ('reproduction', 'model_diagnostic')},
        'source_hash_format': 'UTF-8 with LF line endings', 'source_sha256': sources,
    }
    return {name: (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
            for name, data in result.items()}


if __name__ == '__main__':
    destination = ROOT / 'demos/01-repair-agent/research-data'
    destination.mkdir(exist_ok=True)
    for name, content in build().items():
        (destination / name).write_bytes(content)
    print('Published 30 cases and the source-hashed index.')
