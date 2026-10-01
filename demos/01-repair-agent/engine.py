"""Curated repair verification: real subprocess tests, deterministic proposal provider.
Only trusted bundled fixtures execute. This is NOT a sandbox for untrusted code.
"""
import ast,difflib,json,subprocess,sys,tempfile,time
from pathlib import Path
CASES={
 'boundary':{'title':'边界条件 · 满 100 元免运费','issue':'订单金额大于等于 100 元免运费，否则运费 10 元。',
 'before':'def shipping(total):\n    return 0 if total > 100 else 10\n',
 'after':'def shipping(total):\n    return 0 if total >= 100 else 10\n',
 'wrong':'def shipping(total):\n    return 0\n','fn':'shipping','tests':[(0,10),(99,10),(100,0),(101,0)],'holdout':[(50,10),(99.99,10),(100.01,0)]},
 'empty':{'title':'空输入 · 平均值','issue':'平均值函数接收数值列表，空列表约定返回 0。',
 'before':'def average(values):\n    return sum(values) / len(values)\n',
 'after':'def average(values):\n    return sum(values) / len(values) if values else 0\n',
 'wrong':'def average(values):\n    return 0\n','fn':'average','tests':[([],0),([2,4],3),([0],0),([-3,3],0)],'holdout':[([4,8,12],8),([-2,-4],-3),([0.5,1.5],1)]},
 'dedupe':{'title':'数据丢失 · 稳定去重','issue':'去重时保留元素首次出现的顺序。',
 'before':'def unique(values):\n    return sorted(set(values))\n',
 'after':'def unique(values):\n    return list(dict.fromkeys(values))\n',
 'wrong':'def unique(values):\n    return values\n','fn':'unique','tests':[([3,1,3,2],[3,1,2]),([],[]),([1,1],[1]),([2,1],[2,1])],'holdout':[([5,2,5,1],[5,2,1]),([9,9,8],[9,8]),([0,-1,0],[0,-1])]}
}

def check(source,case,holdout=False):
    pairs=case['holdout'] if holdout else case['tests']
    script=source+'\nimport json\ncases='+repr(pairs)+'\nresults=[]\nfor value, expected in cases:\n    try:\n        actual='+case['fn']+'(value)\n        results.append({"input":value,"expected":expected,"actual":actual,"pass":actual==expected})\n    except Exception as e:\n        results.append({"input":value,"expected":expected,"error":type(e).__name__,"pass":False})\nprint(json.dumps(results))\n'
    with tempfile.TemporaryDirectory(prefix='topic-lab-') as tmp:
        path=Path(tmp)/'check.py';path.write_text(script)
        p=subprocess.run([sys.executable,'-I',str(path)],capture_output=True,text=True,timeout=3,cwd=tmp)
    if p.returncode:raise RuntimeError('Bundled fixture failed')
    return json.loads(p.stdout)

def run(case_id='boundary',candidate='correct'):
    if case_id not in CASES or candidate not in ('correct','wrong'):raise ValueError('未知样例或候选补丁')
    start=time.perf_counter();case=CASES[case_id];source=case['after' if candidate=='correct' else 'wrong']
    before=check(case['before'],case);after=check(source,case);held=check(source,case,True)
    accepted=all(t['pass'] for t in after+held)
    return {'case':case_id,'title':case['title'],'provider':'离线预置候选补丁（未调用 LLM）','issue':case['issue'],
     'functions':[n.name for n in ast.walk(ast.parse(case['before'])) if isinstance(n,ast.FunctionDef)],
     'before_source':case['before'],'candidate_source':source,'before':before,'after':after,'holdout':held,
     'accepted':accepted,'diff':''.join(difflib.unified_diff(case['before'].splitlines(True),source.splitlines(True),fromfile='a/fixture.py',tofile='b/fixture.py')),
     'duration_ms':round((time.perf_counter()-start)*1000,2),'trace':['解析可信样例 AST','运行原始回归测试','读取离线候选补丁','运行回归测试 + 独立测试集','接受补丁' if accepted else '拒绝补丁；保留原始代码']}
