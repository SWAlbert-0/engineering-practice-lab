"""Immutable comparisons of recorded D11 executions, never a repair benchmark."""
import difflib
from shared.repair_fixtures import digest
from shared.process_workspace import WorkspaceError

BOUNDARY = ('同一教学快照下的已记录运行对照，不是跨仓库解决率或模型质量评测。'
            '测试通过不证明普遍正确；耗时仅来自记录的测试执行，不含排队、模型或网络。实际token和费用未知。')


def build_comparison(tasks):
    reference = tasks[0]
    snap = reference['snapshot']
    expected = {(x['group'], x['id']) for x in reference['baseline']['tests']}
    def environment(value):
        return {k: v for k, v in value.items() if k != 'container_id'}
    def signature(t):
        env = t['baseline'].get('environment', {})
        return (t['snapshot']['snapshot_sha256'], t['snapshot']['tests_sha256'], t['runner'],
                digest(environment(env)))
    if any(signature(t) != signature(reference) for t in tasks):
        raise WorkspaceError('对照需要相同源码、测试快照及实际执行环境；请重新选择。', 409)
    columns = []
    for t in tasks:
        base = {(r['group'], r['id']): r for r in t['baseline']['tests']}
        if set(base) != expected or len(base) != len(t['baseline']['tests']):
            raise WorkspaceError('基线测试集合不一致，不能对照。', 409)
        attempt = t['attempts'][-1] if t['attempts'] else None
        result = attempt.get('result') if attempt else None
        rows = {(r['group'], r['id']): r for r in result['tests']} if result else {}
        if result and (set(rows) != expected or len(rows) != len(result['tests']) or result.get('tests_sha256') != snap['tests_sha256'] or result.get('snapshot_sha256') != snap['snapshot_sha256']):
            raise WorkspaceError('候选测试集合或哈希与基线不一致，不能对照。', 409)
        if result and environment(result.get('environment', {})) != environment(t['baseline'].get('environment', {})):
            raise WorkspaceError('候选与基线执行环境不一致，不能对照。', 409)
        fixed = [k[1] for k in expected if k in rows and not base[k]['passed'] and rows[k]['passed']]
        broken = [k[1] for k in expected if k in rows and base[k]['passed'] and not rows[k]['passed']]
        columns.append({'task_id': t['id'], 'title': t['title'], 'mode': t['mode'], 'candidate': t['candidate'],
                        'status': t['status'], 'reason': t['reason'], 'max_attempts': t['max_attempts'], 'attempt_count': len(t['attempts']),
                        'task_revision': t['revision'], 'final_attempt': attempt['number'] if attempt else None,
                        'passed': sum(r['passed'] for r in rows.values()) if result else None, 'total': len(expected),
                        'fixed': sorted(fixed), 'broken': sorted(broken),
                        'remaining': sorted(k[1] for k in expected if k in rows and not rows[k]['passed']),
                        'test_duration_ms': round(sum(a.get('result', {}).get('duration_ms', 0) for a in t['attempts']), 2),
                        'model': t.get('model'), 'model_config_sha256': t.get('model_config_sha256'), 'prompt_version': t['prompt_version'],
                        'usage': t.get('usage'), 'cost': t.get('cost'), 'final_sha256': attempt.get('source_sha256') if attempt else None,
                        'review': t['reviews'][-1] if t['reviews'] else None})
    matrix = []
    for original in reference['baseline']['tests']:
        key = original['group'], original['id']
        outcomes = []
        for t in tasks:
            a = t['attempts'][-1] if t['attempts'] else None
            r = next((r for r in (a or {}).get('result', {}).get('tests', []) if (r['group'], r['id']) == key), None)
            outcomes.append({'task_id': t['id'], 'passed': r['passed'] if r else None,
                             'actual': r.get('actual') if r else None, 'error': r.get('error') if r else None})
        matrix.append({'id': original['id'], 'group': original['group'], 'name': original['name'], 'input': original['input'],
                       'expected': original['expected'], 'baseline_passed': original['passed'], 'outcomes': outcomes})
    sources = [t['attempts'][-1].get('source') if t['attempts'] else None for t in tasks]
    diffs = [{'from_task': tasks[0]['id'], 'to_task': t['id'], 'diff': ''.join(difflib.unified_diff(
        sources[0].splitlines(True), src.splitlines(True), fromfile=tasks[0]['id']+'/'+snap['path'], tofile=t['id']+'/'+snap['path']))}
        for t, src in zip(tasks[1:], sources[1:]) if sources[0] is not None and src is not None]
    return {'schema': 'd11-comparison-v1', 'snapshot': snap, 'environment': reference['baseline']['environment'],
            'columns': columns, 'tests': matrix, 'candidate_diffs': diffs, 'tasks': tasks,
            'evidence_sha256': digest(tasks), 'boundary': BOUNDARY}


def markdown(report):
    clean = lambda x: str(x if x is not None else '未知').replace('<', '&lt;').replace('>', '&gt;').replace('|', '\\|').replace('\n', ' ')
    lines = ['# '+clean(report['title']), report['boundary'], '证据快照 SHA256：'+report['evidence_sha256'],
             '| 任务 | 状态 | 轮数 | 通过 | 新修复用例 | 新破坏用例 |', '|---|---|---|---|---|---|']
    for c in report['columns']:
        lines.append('| '+' | '.join(map(clean, [c['title'], c['status'], c['attempt_count'], str(c['passed'])+'/'+str(c['total']) if c['passed'] is not None else '未执行', ','.join(c['fixed']), ','.join(c['broken'])]))+' |')
    lines += ['', '## 用例对照', '| 用例 | 基线 | '+' | '.join(clean(c['title']) for c in report['columns'])+' |', '|---|---|'+'---|'*len(report['columns'])]
    for r in report['tests']:
        lines.append('| '+clean(r['id'])+' | '+('通过' if r['baseline_passed'] else '失败')+' | '+' | '.join('未执行' if v['passed'] is None else '通过' if v['passed'] else '失败' for v in r['outcomes'])+' |')
    return '\n\n'.join(lines).encode('utf-8')
