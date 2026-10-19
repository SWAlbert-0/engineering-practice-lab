"""Trusted judge, also copied into the read-only job image. Candidate has no I/O API."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parent))
from repair_fixtures import CASES, SAFE_BUILTINS, snapshot, validate_source

CHILD='''import builtins,json,sys
v=json.load(sys.stdin)
env={"__builtins__":{k:getattr(builtins,k) for k in v["builtins"]}}
try:
 exec(compile(v["source"],"<candidate>","exec"),env)
 result=env[v["fn"]](v["input"])
 print(json.dumps({"actual":result},allow_nan=False))
except Exception as error:
 print(json.dumps({"error":type(error).__name__}))
'''

def evaluate(key,source,stopped=lambda:False):
    source=validate_source(source,key);case=CASES[key];rows=[];start=time.monotonic()
    for group,pairs in (('regression',case['tests']),('acceptance',case['acceptance'])):
        for i,(value,expected) in enumerate(pairs,1):
            if stopped():raise InterruptedError('运行已取消。')
            began=time.monotonic();payload={'source':source,'fn':case['fn'],'input':value,'builtins':SAFE_BUILTINS}
            try:
                p=subprocess.run([sys.executable,'-I','-S','-X','utf8','-c',CHILD],input=json.dumps(payload),capture_output=True,text=True,encoding='utf-8',timeout=1,
                                 env={'PYTHONUTF8':'1','PYTHONIOENCODING':'utf-8'})
                if p.returncode or len(p.stdout)>64000:result={'error':'ProcessError'}
                else:
                    try:result=json.loads(p.stdout)
                    except (ValueError,TypeError):result={'error':'InvalidOutput'}
            except subprocess.TimeoutExpired:result={'error':'Timeout'}
            actual=result.get('actual');passed='actual' in result and actual==expected
            rows.append({'id':('REG' if group=='regression' else 'ACC')+f'-{i:02}','group':group,'name':case['fn']+'('+json.dumps(value,ensure_ascii=False)+')',
                         'input':value,'expected':expected,'actual':actual,'error':result.get('error'),'passed':passed,'duration_ms':round((time.monotonic()-began)*1000,2),
                         'log':('PASS' if passed else 'FAIL')+' '+case['fn']+' | expected='+json.dumps(expected,ensure_ascii=False)+' | '+('error='+result['error'] if result.get('error') else 'actual='+json.dumps(actual,ensure_ascii=False))})
    return {'snapshot_sha256':snapshot(key)['snapshot_sha256'],'tests_sha256':snapshot(key)['tests_sha256'],'tests':rows,'duration_ms':round((time.monotonic()-start)*1000,2),'python':sys.version.split()[0]}

if __name__=='__main__':
    if '--self-check' in sys.argv:print(json.dumps({'protocol':'d11-1','repositories':list(CASES)}))
    else:
        payload=json.loads(os.environ['LAB_REPAIR_PAYLOAD']);print(json.dumps(evaluate(payload['repository'],payload['source']),ensure_ascii=False,allow_nan=False))
