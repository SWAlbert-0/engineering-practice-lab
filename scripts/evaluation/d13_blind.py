"""Create model-identity-blinded review packs and summarize two submitted reviews.

Reviewers remain self-identified; this tool cannot authenticate independence or
turn model ratings into human expert judgements. It never fills ratings itself.
"""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import secrets

from .common import digest, load, write_new

FIELDS = ('item_id', 'prediction_sha256', 'reviewer', 'supported', 'coverage_0_2',
          'synthesis_0_2', 'seconds', 'comment')


def pack(data, runs, output):
    rows, mappings = [], []
    docs = {(p['dataset'], p['id']): p for p in data['documents']}
    cases = {c['id']: c for c in data['cases']}
    summaries = [load(run / 'summary.json') for run in runs]
    if any(s['dataset_sha256'] != digest(data) for s in summaries):
        raise ValueError('run dataset fingerprint mismatch')
    ids_by_run = []
    for run, summary in zip(runs, summaries):
        selected = []
        for file in sorted(run.glob('*.json')):
            row = load(file)
            if row.get('id') not in cases:
                continue
            selected.append(row['id'])
            case = cases[row['id']]
            document = docs[(case['dataset'], case['paper'])]
            identifier = secrets.token_hex(12)
            prediction = row.get('prediction') or ((row.get('calls') or [{}])[-1].get('output'))
            prediction_sha = digest({'status': row['status'], 'prediction': prediction})
            rows.append({'item_id': identifier, 'prediction_sha256': prediction_sha,
                         'question': case['question'], 'task': case['task'],
                         'source_title': document['title'], 'source_scope': document['scope'],
                         'source_units': document['units'], 'prediction': prediction,
                         'generation_status': row['status'],
                         'instruction': 'If no usable answer was produced, record that failure explicitly; do not invent an answer or omit this item.'})
            mappings.append({'item_id': identifier, 'case_id': case['id'], 'mode': summary['mode'],
                             'prediction_sha256': prediction_sha, 'run_summary_sha256': digest(summary)})
        ids_by_run.append(set(selected))
    if not rows or len(runs) < 2 or not ids_by_run[0] or any(ids != ids_by_run[0] for ids in ids_by_run[1:]):
        raise ValueError('at least two runs with identical recorded case sets are required; failures stay in the pack and missing cases cannot be silently dropped')
    secrets.SystemRandom().shuffle(rows)
    output.mkdir(parents=True, exist_ok=False)
    write_new(output / 'review-pack.json', {'schema': 1, 'instruction': 'Independently inspect source and prediction. supported=0/1; coverage and synthesis=0(poor)/1(partial)/2(good). Record actual review seconds and explain errors. Model identity and dataset gold labels are withheld. Do not share unblinding.json with reviewers.', 'items': rows})
    write_new(output / 'unblinding.json', {'schema': 1, 'dataset_sha256': digest(data), 'mapping': mappings})
    for reviewer in ('A', 'B'):
        with (output / ('reviewer-' + reviewer + '.csv')).open('x', encoding='utf-8-sig', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=FIELDS)
            writer.writeheader()
            for row in rows:
                writer.writerow({key: row[key] for key in ('item_id', 'prediction_sha256')})
    return len(rows)


def read_review(path, mapping):
    with path.open(encoding='utf-8-sig', newline='') as file:
        rows = list(csv.DictReader(file))
    if len(rows) != len(mapping) or len({r['item_id'] for r in rows}) != len(rows):
        raise ValueError('review set is incomplete or contains duplicate items')
    names = {r.get('reviewer', '').strip() for r in rows}
    if len(names) != 1 or not next(iter(names)):
        raise ValueError('each complete review requires one nonempty self-identified reviewer')
    for row in rows:
        if row['item_id'] not in mapping or row['prediction_sha256'] != mapping[row['item_id']]['prediction_sha256']:
            raise ValueError('review references stale or unknown output')
        if row['supported'] not in ('0', '1') or row['coverage_0_2'] not in ('0', '1', '2') or row['synthesis_0_2'] not in ('0', '1', '2'):
            raise ValueError('all ratings must be filled; no placeholder scores accepted')
        try:
            seconds = float(row['seconds'])
        except ValueError:
            raise ValueError('review time must be positive') from None
        if not 0 < seconds <= 86400:
            raise ValueError('review time must be finite and positive')
    return {r['item_id']: r for r in rows}, next(iter(names))


def summarize(key, review_a, review_b):
    mapping = {r['item_id']: r for r in key['mapping']}
    a, aname = read_review(review_a, mapping)
    b, bname = read_review(review_b, mapping)
    if aname == bname:
        raise ValueError('two different reviewer identifiers required; independence still requires external confirmation')
    scores = {}
    for mode in sorted({r['mode'] for r in mapping.values()}):
        ids = [id for id, row in mapping.items() if row['mode'] == mode]
        agreement = sum(a[id]['supported'] == b[id]['supported'] for id in ids) / len(ids)
        pa = sum(int(a[id]['supported']) for id in ids) / len(ids)
        pb = sum(int(b[id]['supported']) for id in ids) / len(ids)
        chance = pa * pb + (1 - pa) * (1 - pb)
        scores[mode] = {'items': len(ids), 'support_agreement': agreement,
                        'cohen_kappa': (agreement - chance) / (1 - chance) if chance < 1 else None,
                        'support_disagreements': [id for id in ids if a[id]['supported'] != b[id]['supported']],
                        'mean_ratings': {field: sum(int(r[id][field]) for r in (a, b) for id in ids) / (2 * len(ids)) for field in ('supported', 'coverage_0_2', 'synthesis_0_2')},
                        'total_review_seconds': sum(float(r[id]['seconds']) for r in (a, b) for id in ids)}
    return {'schema': 1, 'dataset_sha256': key['dataset_sha256'],
            'reviewers': ['reviewer-' + digest(name.encode())[:12] for name in (aname, bname)],
            'reviewer_identity': 'self-reported identifiers hashed; no authentication or expert qualification verification', 'modes': scores}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    build = sub.add_parser('pack')
    build.add_argument('--data', type=Path, required=True)
    build.add_argument('--run', type=Path, action='append', required=True)
    build.add_argument('--output', type=Path, required=True)
    report = sub.add_parser('score')
    report.add_argument('--key', type=Path, required=True)
    report.add_argument('--review-a', type=Path, required=True)
    report.add_argument('--review-b', type=Path, required=True)
    report.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'pack':
        print('blinded items:', pack(load(args.data), args.run, args.output))
    else:
        result = summarize(load(args.key), args.review_a, args.review_b)
        write_new(args.output, result)
        print(json.dumps(result))


if __name__ == '__main__':
    main()
