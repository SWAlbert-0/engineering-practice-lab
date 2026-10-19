"""Evidence-grounded role workflow; local mode is explicitly not a multi-LLM run."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import time
from shared.model_client import ask_json

PAPERS = json.loads((Path(__file__).parent/'papers.json').read_text(encoding='utf-8'))


def validate_claims(claims, papers):
    if not isinstance(claims, list) or not 1 <= len(claims) <= 15:
        raise ValueError('综述应包含 1–15 条论述。')
    sources = {p['id']: p for p in papers}
    checks = []
    for i, c in enumerate(claims, 1):
        if not isinstance(c, dict) or not all(isinstance(c.get(k), str) and c[k].strip() for k in ('text', 'paper', 'quote')):
            raise ValueError('论述缺少 text、paper 或 quote 字段。')
        if len(c['text']) > 1500 or len(c['quote']) > 1500:
            raise ValueError('论述或证据过长。')
        p = sources.get(c['paper'])
        valid = bool(p and c['quote'] in p['note'])
        checks.append({'id': f'CLAIM-{i:03}', **c, 'valid': valid,
                       'reason': '编号与摘记引用存在；语义支持待人工审核' if valid else '来源不存在，或引用不在选定摘记中'})
    return checks


def run(topic, ids, mode='offline'):
    if not isinstance(topic, str) or not 1 <= len(topic.strip()) <= 500:
        raise ValueError('综述问题应为 1–500 字。')
    if not isinstance(ids, list) or not 1 <= len(ids) <= 5 or any(not isinstance(i, str) for i in ids):
        raise ValueError('请选择 1–5 篇资料。')
    selected = [p for p in PAPERS if p['id'] in ids]
    if len(selected) != len(set(ids)):
        raise ValueError('选择中存在未知文献。')
    if mode not in ('offline', 'single', 'multi'):
        raise ValueError('未知工作流模式。')
    started, trace = time.perf_counter(), []
    trace.append({'role': '规划', 'action': '固定问题、资料池及预算', 'detail': f'{len(selected)} 篇摘记；问题：{topic}'})

    def read(p):
        if mode == 'multi':
            row = ask_json('你是文献证据提取者。只根据输入摘记，返回 {"text":一条简洁的方法或局限描述,"paper":输入id,"quote":摘记中的逐字连续片段}。'
                           '不要根据常识添加实验结论，不输出数字对比。', {'topic': topic, 'paper': p})
            if row.get('paper') != p['id']:
                raise ValueError('证据提取返回了错误的文献编号。')
        else:
            row = {'text': p['note'].split('。')[0] + '。', 'paper': p['id'], 'quote': p['note'].split('。')[0]}
        checked = validate_claims([row], [p])[0]
        if not checked['valid']:
            raise ValueError('证据提取引用不存在于所选摘记，已停止融合。')
        return row

    if mode == 'multi':
        with ThreadPoolExecutor(max_workers=3) as pool:
            evidence = list(pool.map(read, selected))
        trace.append({'role': '阅读者', 'action': '最多 3 个并行模型调用提取证据', 'detail': f'已核验 {len(evidence)} 条摘记引用'})
    else:
        evidence = [read(p) for p in selected]
        trace.append({'role': '阅读者', 'action': '按文献建立摘记证据表', 'detail': '离线抽取，不表示已执行模型阅读'})
    if mode in ('single', 'multi'):
        data = ask_json('你是文献综合者。根据所给摘记和问题，返回 {"claims":[{"text":综合论述,"paper":一个输入文献id,"quote":该文献摘记逐字引用}]}。'
                        '每条论述绑定一篇文献。缺少证据时说明局限，不添加外部文献或虚构实验。',
                        {'topic': topic, 'papers': selected, 'evidence': evidence})
        claims = data.get('claims')
    else:
        claims = evidence
    checks = validate_claims(claims, selected)
    if not all(c['valid'] for c in checks):
        raise ValueError('融合结果包含无法定位的引用，未保存为可审核综述。')
    trace.extend([{'role': '综合', 'action': '组织带引用的论述', 'detail': '模型综合' if mode != 'offline' else '摘记列表，仅用于演示'},
                  {'role': '核查', 'action': '校验来源编号与摘记引用', 'detail': '此检查不判断论文全文的语义支持；需人工审核'}])
    return {'topic': topic, 'mode': mode, 'provider': {'offline': '离线角色流程（未调用模型）', 'single': '单次模型综合', 'multi': '并行阅读角色 + 模型综合'}[mode],
            'papers': selected, 'evidence': evidence, 'claims': checks, 'trace': trace,
            'model_calls': 0 if mode == 'offline' else 1 if mode == 'single' else len(selected)+1,
            'duration_ms': round((time.perf_counter()-started)*1000, 2),
            'boundary': '输入为人工编写的论文摘要摘记，不是PDF全文。引用检查只校验摘记位置；不代表论述已被全文支持。没有文献搜索、PDF解析和跨领域盲评。'}
