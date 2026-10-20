"""D11 local workspace: immutable task inputs, leases, attempts and review evidence."""
from shared.model_settings import model_name, identity, model_session

from contextlib import contextmanager
from datetime import datetime,timezone
import difflib
import json
import os
from pathlib import Path
import sqlite3
import threading
import time
import uuid
from shared.model_client import ask_json,configured
from shared.process_workspace import WorkspaceError
from shared.repair_fixtures import CASES,PROTOCOL,canonical,digest,snapshot,validate_proposal
from shared.repair_judge import evaluate
from shared.repair_runner import RunnerError,RunnerTimeout

FINAL=('succeeded','failed','cancelled','interrupted','timed_out')
def now():return datetime.now(timezone.utc).isoformat()
def uid(prefix):return prefix+'-'+uuid.uuid4().hex[:16]
def text(value,label,limit=120):
    if not isinstance(value,str) or not 1<=len(value.strip())<=limit:raise WorkspaceError(label+f'应为 1–{limit} 字。')
    return value.strip()
def diff_for(before,after,path):return ''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='a/'+path,tofile='b/'+path))
def gates(task,attempt=None):
    attempts=task['attempts'];attempt=attempt or next((a for a in reversed(attempts) if a.get('passed')),None)
    result=attempt.get('result') if attempt else None;tests=result.get('tests',[]) if result else [];base=task.get('baseline')
    return {'reproduced':bool(base and any(not t['passed'] for t in base['tests'])),
            'patch_valid':bool(attempt and attempt.get('source_sha256')==digest(attempt.get('source',''))),
            'regression':bool(tests and all(t['passed'] for t in tests if t['group']=='regression')),
            'acceptance':bool(tests and all(t['passed'] for t in tests if t['group']=='acceptance')),
            'snapshot':bool(result and result.get('snapshot_sha256')==task['snapshot']['snapshot_sha256'] and result.get('tests_sha256')==task['snapshot']['tests_sha256']),
            'environment':bool(result and base and result.get('environment',{}).get('kind')==task['runner'] and (result['environment'].get('image_id')==base['environment'].get('image_id') if task['runner']=='docker' else result['environment'].get('python')==base['environment'].get('python')))}

class RepairWorkspace:
    def __init__(self,directory,start_worker=True,mode=None):
        self.db=Path(directory)/'repair.sqlite3';self.db.parent.mkdir(parents=True,exist_ok=True)
        if os.name!='nt' and self.db.parent.stat().st_uid==os.geteuid():self.db.parent.chmod(0o770)
        self.mode=mode or os.environ.get('LAB_REPAIR_RUNNER','trusted')
        if self.mode not in ('trusted','docker'):raise ValueError('LAB_REPAIR_RUNNER must be trusted or docker')
        self.stop=threading.Event();self.wake=threading.Event();self.thread=None;self.owner=uid('local')
        with self.connect() as c:
            c.executescript('''PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY,title TEXT NOT NULL,repository TEXT NOT NULL,mode TEXT NOT NULL,runner TEXT NOT NULL,
            status TEXT NOT NULL,phase TEXT NOT NULL,reason TEXT,owner TEXT,heartbeat REAL,cancel INTEGER NOT NULL DEFAULT 0,
            created TEXT NOT NULL,updated TEXT NOT NULL,revision INTEGER NOT NULL DEFAULT 1,data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT,task_id TEXT NOT NULL,created TEXT NOT NULL,phase TEXT NOT NULL,detail TEXT NOT NULL,attempt INTEGER);
            CREATE TABLE IF NOT EXISTS reviews(id TEXT PRIMARY KEY,task_id TEXT NOT NULL,attempt_sha256 TEXT NOT NULL,decision TEXT NOT NULL,actor TEXT NOT NULL,comment TEXT NOT NULL,created TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS comparisons(id TEXT PRIMARY KEY,title TEXT NOT NULL,created TEXT NOT NULL,body TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS queue ON tasks(status,created);
            CREATE INDEX IF NOT EXISTS task_events ON events(task_id,seq);''')
            c.execute("INSERT OR IGNORE INTO meta VALUES('workspace',?)",(uid('repair-workspace'),));c.execute("INSERT OR IGNORE INTO meta VALUES('schema','1')")
            self.workspace_id=c.execute("SELECT value FROM meta WHERE key='workspace'").fetchone()[0]
        if os.name=='nt' or self.db.stat().st_uid==os.geteuid():self.db.chmod(0o660)
        if start_worker and self.mode=='trusted':
            self.recover();self.thread=threading.Thread(target=self.loop,daemon=True);self.thread.start()
    @contextmanager
    def connect(self,write=False):
        c=sqlite3.connect(self.db,timeout=15);c.row_factory=sqlite3.Row;c.execute('PRAGMA busy_timeout=15000')
        try:
            if write:c.execute('BEGIN IMMEDIATE')
            yield c;c.commit()
        except BaseException:c.rollback();raise
        finally:c.close()
    def close(self):
        self.stop.set();self.wake.set()
        if self.thread:self.thread.join(5)
    def _event(self,c,tid,phase,detail,attempt=None):c.execute('INSERT INTO events(task_id,created,phase,detail,attempt) VALUES(?,?,?,?,?)',(tid,now(),phase,detail,attempt))
    def _row(self,c,tid):
        row=c.execute('SELECT * FROM tasks WHERE id=?',(tid,)).fetchone()
        if not row:raise WorkspaceError('修复任务不存在。',404)
        return row
    def _task(self,row):
        out=dict(row);out.update(json.loads(out.pop('data')));out.pop('owner',None);out.pop('heartbeat',None);out.pop('cancel',None);return out
    def task(self,tid):
        with self.connect() as c:
            out=self._task(self._row(c,tid));out['reviews']=[dict(r) for r in c.execute('SELECT * FROM reviews WHERE task_id=? ORDER BY rowid',(tid,))]
            out['events']=[dict(r) for r in c.execute('SELECT * FROM events WHERE task_id=? ORDER BY seq',(tid,))]
        out['gates']=gates(out);return out
    def capabilities(self):
        if self.mode=='trusted':return {'runner':'trusted','ready':True,'llm':False,'message':'可信样例进程；只执行内置候选，不执行手写或模型代码。'}
        with self.connect() as c:row=c.execute("SELECT value FROM meta WHERE key='worker'").fetchone()
        worker=json.loads(row[0]) if row else {};ready=bool(worker.get('ready') and time.time()-worker.get('heartbeat',0)<12)
        return {'runner':'docker','ready':ready,'llm':bool(ready and configured() and worker.get('llm')),'image_id':worker.get('image_id'),
                'policy':worker.get('policy'),'worker_uid':worker.get('worker_uid'),'message':worker.get('message','独立运行器尚未连接，请检查 repair-worker 服务。') if not ready else '独立 Docker 运行器已连接；测试使用一次性受限容器。'}
    def state(self):
        self.recover()
        with self.connect() as c:
            rows=c.execute('SELECT * FROM tasks ORDER BY created DESC LIMIT 200').fetchall();tasks=[]
            for row in rows:
                t=self._task(row);reviews=[dict(r) for r in c.execute('SELECT * FROM reviews WHERE task_id=? ORDER BY rowid',(t['id'],))]
                tasks.append({k:t[k] for k in ('id','title','repository','mode','runner','status','phase','reason','created','updated','revision')}|{'attempt_count':len(t['attempts']),'review':reviews[-1] if reviews else None,'parent_id':t['parent_id']})
        return {'schema':1,'repositories':[snapshot(k) for k in CASES],'tasks':tasks,'capabilities':self.capabilities(),
                'comparisons':self.comparisons(),
                'boundary':'三个原创快照及一个开源算法教学改编；独立验收为公开测试，不等于跨仓库泛化评测。'}
    @model_session
    def create(self,value,parent_id=None):
        parent_id=parent_id or value.get('parent_id')
        key=value.get('repository');mode=value.get('mode','offline');candidate=value.get('candidate','correct');budget=value.get('max_attempts',2)
        if key not in CASES or mode not in ('offline','llm','manual'):raise WorkspaceError('请选择受控快照和有效生成方式。')
        if candidate not in ('correct','wrong','progressive'):raise WorkspaceError('未知离线候选。')
        if type(budget) is not int or not 1<=budget<=3:raise WorkspaceError('每个任务允许 1–3 轮候选，最多两次修订。')
        caps=self.capabilities()
        if not caps['ready']:raise WorkspaceError(caps['message'],503)
        if mode!='offline' and self.mode!='docker':raise WorkspaceError('手写和模型候选需要独立 Docker 运行器；当前只开放内置可信样例。',503)
        if mode=='llm' and not caps['llm']:raise WorkspaceError('模型未配置或运行器未连接；不会回退为离线候选。',503)
        source=None
        if mode=='manual':
            try:source=validate_proposal({'files':[{'path':value.get('path'),'content':value.get('source')}],'summary':'人工提交候选'},key)['content']
            except ValueError as e:raise WorkspaceError(str(e)) from None
            budget=1
        if parent_id:
            parent=self.task(text(parent_id,'来源任务',80))
            if parent['status'] not in FINAL or parent['repository']!=key or parent['snapshot']['snapshot_sha256']!=snapshot(key)['snapshot_sha256']:raise WorkspaceError('来源任务尚未结束或代码快照不一致，请重新选择。',409)
        title=text(value.get('title') or CASES[key]['category']+' · '+CASES[key]['title'],'任务名称');tid=uid('repair');stamp=now()
        body={'snapshot':snapshot(key),'candidate':candidate,'max_attempts':budget,'manual_source':source,'parent_id':parent_id,'baseline':None,'attempts':[],
              'environment':None,'model':model_name() if mode=='llm' else None,'prompt_version':PROTOCOL,'usage':None,'cost':None,'model_config_sha256':digest(identity()) if mode=='llm' else None}
        with self.connect(True) as c:
            if c.execute("SELECT count(*) FROM tasks WHERE status IN ('queued','running','cancelling')").fetchone()[0]>=24:raise WorkspaceError('等待或运行的任务已达 24 个，请完成或取消后再提交。',409)
            c.execute('INSERT INTO tasks(id,title,repository,mode,runner,status,phase,created,updated,data) VALUES(?,?,?,?,?,?,?,?,?,?)',
                      (tid,title,key,mode,self.mode,'queued','queued',stamp,stamp,canonical(body)))
            self._event(c,tid,'queued','任务入队，输入快照和测试集已固定。')
        self.wake.set();return {'task_id':tid,'status':'queued'}
    def action(self,tid,action):
        if action=='retry':
            t=self.task(tid)
            if t['status'] not in FINAL:raise WorkspaceError('请先等待或取消当前执行。',409)
            return self.create({'title':t['title'][:100]+' · 重试','repository':t['repository'],'mode':t['mode'],'candidate':t['candidate'],'max_attempts':t['max_attempts'],'path':t['snapshot']['path'],'source':t['manual_source']},tid)
        if action!='cancel':raise WorkspaceError('未知任务操作。',404)
        with self.connect(True) as c:
            r=self._row(c,tid)
            if r['status'] in FINAL:return {'task_id':tid,'status':r['status']}
            status='cancelled' if r['status']=='queued' else 'cancelling'
            c.execute('UPDATE tasks SET cancel=1,status=?,phase=?,updated=?,revision=revision+1 WHERE id=?',(status,status,now(),tid))
            self._event(c,tid,status,'请求停止；运行器将回收测试环境。模型请求若已发送，最多等待当前请求超时。')
        return {'task_id':tid,'status':status}
    def review(self,tid,value):
        actor=text(value.get('actor'),'记录人',80);comment=text(value.get('comment'),'审查说明',2000);decision=value.get('decision')
        if len(comment)<5 or decision not in ('approved','rejected'):raise WorkspaceError('请选择审查结论，并填写至少 5 字的依据。')
        with self.connect(True) as c:
            row=self._row(c,tid);t=self._task(row)
            if value.get('revision')!=row['revision']:raise WorkspaceError('任务或审查记录已变化，请刷新后重新核对。',409)
            if t['status'] not in FINAL:raise WorkspaceError('执行尚未结束，不能记录最终审查。',409)
            successful=next((a for a in reversed(t['attempts']) if a.get('passed')),None)
            sha=successful['source_sha256'] if successful else ''
            if decision=='approved' and (t['status']!='succeeded' or not all(gates(t,successful).values()) or value.get('attempt_sha256')!=sha):raise WorkspaceError('当前补丁未通过完整门禁或证据已变化，不能认可。',409)
            rid=uid('review');c.execute('INSERT INTO reviews VALUES(?,?,?,?,?,?,?)',(rid,tid,sha,decision,actor,comment,now()))
            c.execute('UPDATE tasks SET updated=?,revision=revision+1 WHERE id=?',(now(),tid));self._event(c,tid,'review',actor+' 记录：'+('认可补丁' if decision=='approved' else '退回修改'))
        return {'review_id':rid,'decision':decision}
    def export(self,tid,fmt='json',attempt=None):
        t=self.task(tid)
        if fmt=='json':return canonical({'schema':'d11-task-v1','task':t,'boundary':'本机审查记录不包含身份认证；公开教学测试不构成修复泛化结论。'}).encode(),'application/json; charset=utf-8',tid+'.json'
        if fmt!='patch':raise WorkspaceError('仅支持 JSON 或 patch 导出。')
        try:a=next(a for a in t['attempts'] if a['number']==int(attempt or len(t['attempts'])))
        except (ValueError,StopIteration,TypeError):raise WorkspaceError('候选轮次不存在。',404) from None
        if not a.get('diff'):raise WorkspaceError('本轮没有可导出的有效补丁。',409)
        return a['diff'].encode(),'text/x-diff; charset=utf-8',tid+'-attempt-'+str(a['number'])+'.patch'
    def comparisons(self):
        with self.connect() as c:
            return [dict(r) for r in c.execute('SELECT id,title,created FROM comparisons ORDER BY rowid DESC LIMIT 100')]
    def create_comparison(self,value):
        from shared.repair_reports import build_comparison
        ids=value.get('task_ids')
        if not isinstance(ids,list) or not 2<=len(ids)<=4 or any(not isinstance(i,str) for i in ids) or len(set(ids))!=len(ids):
            raise WorkspaceError('请选择2–4个不重复的已结束任务。')
        title=text(value.get('title'),'对照名称',120)
        with self.connect(True) as c:
            tasks=[]
            for tid in ids:
                t=self._task(self._row(c,tid))
                if t['status'] not in FINAL or not t.get('baseline'):
                    raise WorkspaceError('任务尚未结束或没有实际基线证据，不能建立对照。',409)
                t['reviews']=[dict(r) for r in c.execute('SELECT * FROM reviews WHERE task_id=? ORDER BY rowid',(tid,))]
                t['events']=[dict(r) for r in c.execute('SELECT * FROM events WHERE task_id=? ORDER BY seq',(tid,))]
                t['gates']=gates(t);tasks.append(t)
            report=build_comparison(tasks)
            report.update(id=uid('comparison'),title=title,created=now())
            if c.execute('SELECT count(*) FROM comparisons').fetchone()[0]>=100:
                raise WorkspaceError('已保存100份对照，请复用或导出已有记录。',409)
            c.execute('INSERT INTO comparisons VALUES(?,?,?,?)',(report['id'],title,report['created'],canonical(report)))
        return {'comparison_id':report['id']}
    def comparison(self,id):
        with self.connect() as c:
            r=c.execute('SELECT body FROM comparisons WHERE id=?',(id,)).fetchone()
            if not r:raise WorkspaceError('对照报告不存在。',404)
            return json.loads(r[0])
    def export_comparison(self,id,fmt='json'):
        from shared.repair_reports import markdown
        report=self.comparison(id)
        if fmt=='json':return canonical(report).encode(),'application/json; charset=utf-8',id+'.json'
        if fmt=='markdown':return markdown(report),'text/markdown; charset=utf-8',id+'.md'
        raise WorkspaceError('对照报告支持JSON或Markdown。')
    def heartbeat_worker(self,info):
        with self.connect(True) as c:c.execute("INSERT OR REPLACE INTO meta VALUES('worker',?)",(canonical({**info,'heartbeat':time.time(),'llm':configured(),'worker_uid':os.getuid() if hasattr(os,'getuid') else None}),))
    def recover(self):
        with self.connect(True) as c:
            rows=c.execute("SELECT id FROM tasks WHERE status IN ('running','cancelling') AND heartbeat<?",(time.time()-20,)).fetchall()
            for row in rows:
                c.execute("UPDATE tasks SET status='interrupted',phase='interrupted',reason='worker_lost',updated=?,revision=revision+1 WHERE id=?",(now(),row['id']))
                self._event(c,row['id'],'interrupted','运行器心跳过期，结果未发布；可显式新建重试任务。')
        return [r['id'] for r in rows]
    def _claim(self):
        with self.connect(True) as c:
            row=c.execute("SELECT * FROM tasks WHERE status='queued' AND runner=? ORDER BY created LIMIT 1",(self.mode,)).fetchone()
            if not row:return None
            c.execute("UPDATE tasks SET status='running',phase='reproduce',owner=?,heartbeat=?,updated=?,revision=revision+1 WHERE id=?",(self.owner,time.time(),now(),row['id']))
            return row['id']
    def _cancelled(self,tid):
        with self.connect() as c:
            row=self._row(c,tid);return self.stop.is_set() or bool(row['cancel']) or row['owner']!=self.owner or row['status'] not in ('running','cancelling')
    def _update(self,tid,body,phase,message,number=None):
        with self.connect(True) as c:
            row=self._row(c,tid)
            if row['owner']!=self.owner or row['status'] not in ('running','cancelling') or row['cancel']:raise InterruptedError('运行已取消或租约失效。')
            c.execute('UPDATE tasks SET data=?,phase=?,updated=?,revision=revision+1 WHERE id=?',(canonical(body),phase,now(),tid));self._event(c,tid,phase,message,number)
    def _finish(self,tid,status,reason=None):
        with self.connect(True) as c:
            row=self._row(c,tid)
            if row['owner']!=self.owner or row['status'] not in ('running','cancelling'):return
            if row['cancel']:status,reason='cancelled','user_cancelled'
            c.execute('UPDATE tasks SET status=?,phase=?,reason=?,updated=?,revision=revision+1 WHERE id=?',(status,status,reason,now(),tid));self._event(c,tid,status,reason or '所有测试门禁通过，等待人工审查。')
    @model_session
    def process_one(self,runner=None):
        tid=self._claim()
        if not tid:return False
        done=threading.Event()
        def beat():
            while not done.wait(1):
                with self.connect(True) as c:c.execute('UPDATE tasks SET heartbeat=? WHERE id=? AND owner=? AND status IN (?,?)',(time.time(),tid,self.owner,'running','cancelling'))
        heartbeat=threading.Thread(target=beat,daemon=True);heartbeat.start();started=time.monotonic()
        try:
            t=self.task(tid);key=t['repository'];body={k:t[k] for k in ('snapshot','candidate','max_attempts','manual_source','parent_id','baseline','attempts','environment','model','prompt_version','usage','cost','model_config_sha256')}
            if body['snapshot']['snapshot_sha256']!=snapshot(key)['snapshot_sha256']:raise RunnerError('代码或测试快照版本已变化，请新建任务。')
            stopped=lambda:self._cancelled(tid)
            if self.mode=='docker' and runner is None:raise RunnerError('独立运行器未提供。')
            def execute(source):
                if stopped():raise InterruptedError('运行已取消。')
                if time.monotonic()-started>240:raise RunnerTimeout('任务超过 240 秒总时限。')
                if self.mode=='trusted':
                    if source not in (CASES[key]['before'],CASES[key]['correct'],CASES[key]['wrong']):raise RunnerError('可信模式拒绝非内置源码。')
                    result=evaluate(key,source,stopped);result['environment']={'kind':'trusted','python':result['python'],'policy':'仅允许内置可信代码，不是隔离沙箱'}
                else:result=runner.run(key,source,tid,stopped)
                if result.get('snapshot_sha256')!=body['snapshot']['snapshot_sha256'] or result.get('tests_sha256')!=body['snapshot']['tests_sha256']:raise RunnerError('测试镜像与固定快照不一致，请重新构建。')
                expected=[('regression',i) for i in range(1,len(CASES[key]['tests'])+1)]+[('acceptance',i) for i in range(1,len(CASES[key]['acceptance'])+1)]
                rows=result.get('tests',[])
                if len(rows)!=len(expected) or [(r.get('group'),r.get('id')) for r in rows]!=[(g,('REG' if g=='regression' else 'ACC')+f'-{n:02}') for g,n in expected] or any(type(r.get('passed')) is not bool for r in rows):raise RunnerError('测试结果缺失或结构无效。')
                return result
            self._update(tid,body,'reproduce','在固定快照上运行原始测试。');body['baseline']=execute(CASES[key]['before']);body['environment']=body['baseline']['environment']
            self._update(tid,body,'baseline','原始测试已保存，确认缺陷是否可复现。')
            if all(r['passed'] for r in body['baseline']['tests']):self._finish(tid,'failed','not_reproduced');return True
            feedback={'regression':[r for r in body['baseline']['tests'] if r['group']=='regression']}
            rounds=1 if t['mode']=='manual' or t['mode']=='offline' and t['candidate']!='progressive' else t['max_attempts']
            for number in range(1,rounds+1):
                if stopped():raise InterruptedError('运行已取消。')
                self._update(tid,body,'propose','生成第 '+str(number)+' 轮候选。',number)
                metadata={'provider':t['mode'],'model':t['model'],'prompt_version':PROTOCOL,'usage':None,'cost':None}
                if t['mode']=='llm':
                    if body['model_config_sha256']!=digest(identity()):raise ValueError('模型配置已变化，请新建任务以固定调用来源。')
                    if time.monotonic()-started>194:raise RunnerTimeout('剩余时限不足以再发起一次模型请求。')
                    payload={'issue':body['snapshot']['issue'],'allowed_file':body['snapshot']['path'],'function':CASES[key]['fn'],'baseline':body['snapshot']['source'],
                             'previous_candidate':body['attempts'][-1].get('source') if body['attempts'] else None,'feedback':feedback,'round':number,'max_rounds':rounds}
                    metadata['input_sha256']=digest(payload)
                    value=ask_json('修复指定 Python 单函数。只返回 {"files":[{"path":"指定原路径","content":"完整函数源码"}],"summary":"修复依据"}。'
                        '禁止修改测试、增加文件、导入、I/O、动态执行或访问内部属性。允许常见纯函数内置操作，dict.fromkeys 可用于保序去重。保留函数名和单参数签名。',payload,max_tokens=1800)
                else:
                    source=t['manual_source'] if t['mode']=='manual' else CASES[key]['wrong' if t['candidate']=='wrong' or t['candidate']=='progressive' and number==1 else 'correct']
                    value={'files':[{'path':CASES[key]['path'],'content':source}],'summary':'人工候选' if t['mode']=='manual' else '预置候选用于验证门禁与执行流程。'}
                if stopped():raise InterruptedError('运行已取消。')
                attempt={'number':number,'created':now(),'metadata':metadata,'passed':False}
                try:proposal=validate_proposal(value,key)
                except ValueError as e:
                    attempt.update(status='invalid_patch',error=str(e));body['attempts'].append(attempt);feedback={'validation_error':str(e)}
                    self._update(tid,body,'patch_rejected',str(e),number);continue
                source=proposal['content'];attempt.update(source=source,source_sha256=digest(source),summary=proposal['summary'],path=proposal['path'],diff=diff_for(CASES[key]['before'],source,CASES[key]['path']),status='testing')
                body['attempts'].append(attempt);self._update(tid,body,'test','路径和源码校验通过，开始回归与独立验收。',number)
                result=execute(source);attempt['result']=result;attempt['passed']=all(r['passed'] for r in result['tests']);attempt['status']='passed' if attempt['passed'] else 'failed'
                self._update(tid,body,'verified','测试证据已保存。'+('本轮通过。' if attempt['passed'] else '本轮未通过。'),number)
                if attempt['passed']:
                    if not all(gates({**t,**body},attempt).values()):raise RunnerError('执行证据未通过一致性校验。')
                    self._finish(tid,'succeeded');return True
                feedback={'regression':[r for r in result['tests'] if r['group']=='regression'],'acceptance_passed':all(r['passed'] for r in result['tests'] if r['group']=='acceptance')}
            self._finish(tid,'failed','budget_exhausted')
        except InterruptedError:self._finish(tid,'cancelled' if not self.stop.is_set() else 'interrupted','user_cancelled' if not self.stop.is_set() else 'worker_stopped')
        except RunnerTimeout as e:
            self._event_error(tid,str(e));self._finish(tid,'timed_out','time_limit')
        except (ValueError,RunnerError) as e:
            self._event_error(tid,str(e));self._finish(tid,'failed','model_error' if self.task(tid)['phase']=='propose' else 'runner_error')
        except Exception:
            import traceback;traceback.print_exc();self._event_error(tid,'执行器发生异常，任务未认可。请查看服务端日志后显式重试。');self._finish(tid,'failed','internal_error')
        finally:done.set();heartbeat.join(2)
        return True
    def _event_error(self,tid,message):
        with self.connect(True) as c:self._event(c,tid,'error',message)
    def loop(self):
        while not self.stop.is_set():
            if not self.process_one():self.wake.wait(.3);self.wake.clear()

_singleton=None
_singleton_lock=threading.Lock()
def get_repair_workspace():
    global _singleton
    with _singleton_lock:
        if _singleton is None:_singleton=RepairWorkspace(os.environ.get('LAB_DATA_DIR',str(Path(__file__).resolve().parents[1]/'data')))
        return _singleton
