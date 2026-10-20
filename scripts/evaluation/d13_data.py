"""Rebuild a frozen, annotated biomedical/NLP subset from original releases."""
import argparse
from collections import defaultdict
import io
import json
from pathlib import Path
import tarfile
import urllib.request

from .common import digest, load, write_new

ROOT = Path(__file__).resolve().parents[2]
SOURCES = {
    'scifact': {'url': 'https://scifact.s3-us-west-2.amazonaws.com/release/latest/data.tar.gz',
                'sha256': '11c621288d41ac144d29b13b0f8503b3820b7d6e8b1f6ff24dff335c196d76be',
                'license': 'Claims/evidence: CC BY 4.0; abstracts: ODC-By 1.0 (S2ORC)',
                'citation': 'Wadden et al. (2020), Fact or Fiction: Verifying Scientific Claims',
                'license_url': 'https://github.com/allenai/scifact/blob/master/LICENSE.md'},
    'qasper': {'url': 'https://qasper-dataset.s3.us-west-2.amazonaws.com/qasper-train-dev-v0.3.tgz',
               'sha256': 'a28fdf966db827bcee3d873107d6b6669864fb7ca8fbf73a192f5e39191bdb5a',
               'license': 'QASPER annotations: CC BY 4.0; paper text extracted from S2ORC, underlying paper rights retained',
               'citation': 'Dasigi et al. (2021), A Dataset of Information-Seeking Questions and Answers Anchored in Research Papers',
               'license_url': 'https://allenai.org/data/qasper'}
}


def archive(name, cache):
    source = SOURCES[name]
    path = cache / (name + '.tgz')
    if not path.exists():
        with urllib.request.urlopen(source['url'], timeout=60) as response:
            raw = response.read(32 * 1024 * 1024 + 1)
        if len(raw) > 32 * 1024 * 1024 or digest(raw) != source['sha256']:
            raise ValueError('dataset download hash/size mismatch')
        path.write_bytes(raw)
    raw = path.read_bytes()
    if digest(raw) != source['sha256']:
        raise ValueError('cached dataset hash mismatch')
    return tarfile.open(fileobj=io.BytesIO(raw))


def scifact(cache):
    with archive('scifact', cache) as data:
        papers = {str(p['doc_id']): p for p in map(json.loads, data.extractfile('data/corpus.jsonl'))}
        claims = list(map(json.loads, data.extractfile('data/claims_dev.jsonl')))
    grouped = defaultdict(list)
    for claim in sorted(claims, key=lambda c: c['id']):
        for doc in claim['cited_doc_ids']:
            grouped[str(doc)].append(claim)
    selected = sorted((p for p in grouped if len(grouped[p]) >= 3), key=int)[:10]
    result, documents = [], []
    for paper in selected:
        p = papers[paper]
        documents.append({'domain': 'biomedicine', 'dataset': 'scifact', 'id': paper,
                          'title': p['title'], 'scope': 'abstract', 'units': p['abstract']})
        for claim in grouped[paper][:3]:
            annotations = claim['evidence'].get(paper, [])
            labels = {a['label'] for a in annotations}
            if len(labels) > 1:
                raise ValueError('conflicting source labels')
            result.append({'id': 'scifact-' + str(claim['id']) + '-' + paper,
                           'domain': 'biomedicine', 'dataset': 'scifact', 'paper': paper,
                           'question': claim['claim'], 'task': 'claim_verification',
                           'gold': {'label': next(iter(labels)) if labels else 'NOT_ENOUGH_INFO',
                                    'rationales': [a['sentences'] for a in annotations] or [[]]}})
    return documents, result


def qasper(cache):
    with archive('qasper', cache) as data:
        papers = json.load(data.extractfile('qasper-dev-v0.3.json'))
    result, documents = [], []
    for paper, p in sorted(papers.items()):
        units = [para for section in p['full_text'] for para in section['paragraphs']]
        if sum(map(len, units)) > 24000:
            continue
        eligible = []
        for q in sorted(p['qas'], key=lambda q: q['question_id']):
            answers = [a['answer'] for a in q['answers']
                       if not a['answer']['unanswerable'] and a['answer']['evidence']
                       and all(e in units for e in a['answer']['evidence'])]
            if answers:
                eligible.append((q, answers))
        if len(eligible) < 3:
            continue
        documents.append({'domain': 'nlp', 'dataset': 'qasper', 'id': paper, 'title': p['title'],
                          'scope': 'extracted_text_without_tables_or_images', 'units': units,
                          'url': 'https://arxiv.org/abs/' + paper})
        for q, answers in eligible[:3]:
            gold_answers, rationales = [], []
            for a in answers:
                answer = ('yes' if a['yes_no'] else 'no') if a['yes_no'] is not None else (', '.join(a['extractive_spans']) or a['free_form_answer'])
                gold_answers.append(answer)
                # Preserve all matching positions for duplicated paragraphs.
                rationales.append([i for i, unit in enumerate(units) if unit in a['evidence']])
            result.append({'id': 'qasper-' + q['question_id'], 'domain': 'nlp', 'dataset': 'qasper',
                           'paper': paper, 'question': q['question'], 'task': 'paper_qa',
                           'gold': {'answers': gold_answers, 'rationales': rationales}})
        if len(documents) == 10:
            break
    return documents, result


def prepare(cache):
    cache.mkdir(parents=True, exist_ok=True)
    documents, cases = [], []
    for builder in (scifact, qasper):
        docs, rows = builder(cache)
        documents += docs
        cases += rows
    if len(documents) != 20 or len(cases) != 60:
        raise ValueError('fixed population cannot be built')
    by_doc = {(d['dataset'], d['id']): d for d in documents}
    for case in cases:
        case['document_sha256'] = digest(by_doc[(case['dataset'], case['paper'])])
    return {'schema': 1, 'sources': SOURCES, 'documents': documents, 'cases': cases}


def manifest(data):
    return {'schema': 1, 'sources': SOURCES,
            'selection': 'Original development splits only. SciFact: first 10 numeric document IDs with >=3 cited claims, first 3 claim IDs each. QASPER: first 10 lexicographic paper IDs with <=24000 extracted characters and >=3 answerable questions whose annotated evidence exactly matches provided paragraphs, first 3 question IDs each. Selection before model calls; not a hidden holdout.',
            'dataset_sha256': digest(data),
            'documents': [{k: v for k, v in d.items() if k != 'units'} | {'sha256': digest(d), 'units': len(d['units'])} for d in data['documents']],
            'cases': [{k: v for k, v in c.items() if k != 'gold'} | {'annotation_sha256': digest(c['gold'])} for c in data['cases']]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, default=ROOT / 'evaluations/d13/manifest.json')
    parser.add_argument('--freeze-manifest', action='store_true')
    args = parser.parse_args()
    data = prepare(args.cache)
    expected = manifest(data)
    if args.freeze_manifest:
        write_new(args.manifest, expected)
    elif expected != load(args.manifest):
        raise ValueError('rebuilt data differs from frozen manifest')
    write_new(args.output, data)
    print(json.dumps({'documents': len(data['documents']), 'cases': len(data['cases']), 'dataset_sha256': digest(data)}))


if __name__ == '__main__':
    main()
