"""Traceable requirement extraction, draft cases and version impact analysis."""
import difflib
import re
import time
from shared.model_client import ask_json

SAMPLE = '学生可以查看本人选修课堂的签到任务。\n学生必须在签到有效期内提交签到码，同一任务不能重复签到。\n教师可以修改本人课堂的考勤状态，修改时必须填写原因。\n管理员可以导出考勤记录，系统应快速完成导出。'


def source_lines(text):
    if not isinstance(text, str) or not 1 <= len(text.strip()) <= 10000:
        raise ValueError('需求正文应为 1–10000 字。')
    lines = [line.strip() for line in re.split(r'[\n。；]+', text) if line.strip()]
    if len(lines) > 40:
        raise ValueError('一次最多分析 40 个需求片段，请分批处理。')
    return lines


def analyze(text, mode='offline'):
    started = time.perf_counter()
    lines = source_lines(text)
    if mode not in ('offline', 'llm'):
        raise ValueError('未知分析模式。')
    items = []
    if mode == 'llm':
        result = ask_json('分析软件需求。返回 {"requirements":[{"source":原文片段逐字引用,"actor":角色,"title":短标题}]}。'
                          '每个输入片段必须对应一条结果，source 不可改写，不可添加未明确提出的功能。', {'sources': lines})
        rows = result.get('requirements')
        if not isinstance(rows, list) or len(rows) != len(lines):
            raise ValueError('模型结果未覆盖所有需求片段，未保存分析。')
        if any(not isinstance(r, dict) or not isinstance(r.get('source'), str) for r in rows) or sorted(r['source'] for r in rows) != sorted(lines):
            raise ValueError('模型引用与输入原文不一致，未保存分析。')
        items = sorted(rows, key=lambda r: lines.index(r['source']))
    else:
        for line in lines:
            actor = next((a for a in ('管理员', '教师', '学生', '用户', '系统') if a in line), '待确认角色')
            items.append({'source': line, 'actor': actor, 'title': line[:48]})
    requirements, cases, issues = [], [], []
    seen = set()
    for i, item in enumerate(items, 1):
        rid = f'REQ-{i:03}'
        line = item['source']
        actor, title = item.get('actor'), item.get('title')
        if not isinstance(actor, str) or not isinstance(title, str) or not actor.strip() or not title.strip() or len(actor) > 40 or len(title) > 300:
            raise ValueError('模型角色或标题字段不符合要求。')
        requirements.append({'id': rid, 'title': title, 'actor': actor, 'source': line,
                             'rules': re.findall(r'(?:必须|不能|不得|仅|只有)[^，,。；]+', line), 'status': '待确认'})
        if re.search('快速|及时|合理|友好|高效', line):
            issues.append({'requirement': rid, 'kind': '可验证性', 'question': '需要明确耗时、容量或可观察的验收条件。', 'quote': line})
        if '待确认' in actor:
            issues.append({'requirement': rid, 'kind': '角色缺失', 'question': '请确认由谁发起此操作。', 'quote': line})
        if line in seen:
            issues.append({'requirement': rid, 'kind': '重复片段', 'question': '与先前片段相同，请确认是否合并。', 'quote': line})
        seen.add(line)
        cases.append({'id': f'TC-{len(cases)+1:03}', 'requirement': rid, 'kind': '主流程', 'title': f'{actor}执行：{title}',
                      'precondition': f'{actor}已具备该需求约定的访问资格；具体准备数据待确认。',
                      'steps': ['准备符合原文条件的数据', '执行原文指定操作', '核对业务结果与记录'],
                      'expected': line, 'status': '待完善'})
        if re.search('不能|不得|必须|有效期|本人|权限', line):
            cases.append({'id': f'TC-{len(cases)+1:03}', 'requirement': rid, 'kind': '约束核验', 'title': '不满足条件时：' + title,
                          'precondition': '选择一项原文约束，构造不满足该约束的数据。',
                          'steps': ['明确被违反的约束', '尝试原文中的操作', '检查系统提示及数据是否变化'],
                          'expected': '应满足以下约束，具体错误提示和状态变化需人工补齐：' + line, 'status': '待完善'})
    # This is structural traceability, not semantic coverage or executed tests.
    return {'provider': '模型 API 提取 + 本地用例模板' if mode == 'llm' else '离线规则提取 + 用例模板（未调用模型）',
            'mode': mode, 'requirements': requirements, 'cases': cases, 'issues': issues,
            'stats': {'requirements': len(requirements), 'cases': len(cases), 'questions': len(issues)},
            'duration_ms': round((time.perf_counter()-started)*1000, 2),
            'boundary': '追踪关系表示已建立关联，不代表需求已正确覆盖。用例为待审草稿，没有执行被测系统；ER/UML与100样例评测尚未实现。'}


def compare(before, after):
    old, new = source_lines(before), source_lines(after)
    delta = []
    for op, i, j, x, y in difflib.SequenceMatcher(a=old, b=new, autojunk=False).get_opcodes():
        if op == 'equal':
            continue
        delta.append({'kind': {'replace': '修改', 'insert': '新增', 'delete': '删除'}[op],
                      'before': old[i:j], 'after': new[x:y],
                      'affected': [f'REQ-{n+1:03}' for n in range(i, j)]})
    return {'changes': delta, 'boundary': '按片段文本对齐，关联旧版本需求；不推断同义改写与跨需求语义影响。新增片段没有旧用例关联。'}
