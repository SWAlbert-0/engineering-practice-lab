"""Versioned single-user D09 workspace. Reviews are declarations, not authentication."""
from shared.model_settings import model_name, model_session

import csv
import difflib
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
import uuid
from shared.model_client import ask_json, configured
from shared.process_workspace import WorkspaceError

KINDS=('正向','异常','边界','权限')
SAMPLE='学生可以查看本人选修课堂的签到任务。\n学生必须在签到有效期内提交签到码，同一任务不能重复签到。\n教师可以修改本人课堂的考勤状态，修改时必须填写原因。\n管理员可以导出考勤记录，系统应快速完成导出。'
def now():return datetime.now(timezone.utc).isoformat()
def uid(p):return p+'-'+uuid.uuid4().hex[:16]
def dump(v):return json.dumps(v,ensure_ascii=False,allow_nan=False)
def sha(s):return hashlib.sha256(s.encode('utf-8')).hexdigest()
def text(v,label,limit=300,empty=False):
    if not isinstance(v,str) or len(v)>limit or (not empty and not v.strip()):raise WorkspaceError(f'{label}应为{0 if empty else 1}–{limit}字。')
    return v.strip()
def strings(v,label,maximum=20):
    if not isinstance(v,list) or len(v)>maximum:raise WorkspaceError(label+'必须为长度受限的数组。')
    return [text(x,label,1000) for x in v]
def number(v,label):
    if type(v) is not int or v<0:raise WorkspaceError(label+'必须是非负整数。')
    return v

def paragraphs(source):
    text(source,'需求正文',20000)
    if any(ord(c)<32 and c not in '\n\r\t' for c in source):raise WorkspaceError('正文包含不支持的控制字符。')
    rows=[]
    for match in re.finditer(r'[^\r\n]+',source):
        raw=match.group();s=raw.strip()
        if not s:continue
        if len(s)>1500:raise WorkspaceError('单个段落最多 1500 字，请拆分过长的段落。')
        start=match.start()+len(raw)-len(raw.lstrip())
        rows.append({'id':f'P{len(rows)+1:03}','text':s,'start':start,'end':start+len(s)})
    if len(rows)>40:raise WorkspaceError('最多 40 个非空段落，请按需求范围拆分文档。')
    return rows

def rule_analysis(ps):
    requirements=[];cases=[]
    for i,p in enumerate(ps,1):
        source=p['text'];rid=f'REQ-{i:03}'
        actor=next((a for a in ('管理员','教师','学生','用户','系统') if a in source),'待确认')
        clauses=[m.group().strip() for m in re.finditer(r'[^，,。；;]+',source) if m.group().strip()]
        criteria=[{'id':f'AC-{i:03}-{j:02}','text':q,'quote':q} for j,q in enumerate(clauses[:8],1)]
        questions=[]
        if len(clauses)>8:questions.append('本段子条件超过八项，请拆分原文并重新分析，避免遗漏验收范围。')
        if actor=='待确认':questions.append('由谁发起操作？')
        if re.search(r'快速|及时|合理|友好|高效',source):questions.append('请明确数据量、完成时限或可观察的验收标准。')
        r={'id':rid,'paragraph_id':p['id'],'actor':actor,'behavior':source,'preconditions':[],
           'constraints':[q for q in clauses if re.search('必须|不能|不得|仅|本人|有效期|权限',q)],'criteria':criteria,'questions':questions}
        requirements.append(r)
        kinds=['正向']
        if re.search(r'不能|不得|必须|失败|重复|无效',source):kinds.append('异常')
        if re.search(r'有效期|至少|最多|不超过|[0-9０-９]+',source):kinds.append('边界')
        if re.search(r'本人|权限|仅|只能|管理员|教师',source):kinds.append('权限')
        instructions={
            '正向':('准备满足原文约束的数据','执行需求指定的操作','操作符合原文验收条件'),
            '异常':('选定一项原文约束，准备违反该约束的数据','提交不满足条件的请求','核验原文约束，确认失败提示和业务数据'),
            '边界':('从原文选定数量或时间边界，准备边界前、等于和边界后三组数据','分别执行操作并记录每组结果','逐组核对边界是否包含及处理结果'),
            '权限':('依据原文访问范围，准备有权与无权的两组身份','分别请求同一业务对象','核对授权范围与越权处理结果')}
        for kind in kinds:
            prepare,action,expected=instructions[kind]
            cases.append({'id':f'TC-{len(cases)+1:03}','requirement_id':rid,'criterion_ids':[a['id'] for a in criteria],
                'kind':kind,'title':kind+' · '+source[:65],'precondition':actor+'具备原文约定的准备条件（待确认具体数据）',
                'steps':[{'action':prepare,'input':source,'expected':'准备数据对应原文约束'},
                         {'action':action,'input':'待确认具体测试输入','expected':expected+'：'+source}],
                'questions':list(questions)+['补齐具体前置数据、操作输入与可观察的预期；边界和错误文案不得凭空补造。'],'origin':'rule'})
    return {'requirements':requirements,'cases':cases,'provider':'离线规则与场景模板','model':None,'usage':None,'prompt_version':'d09-1'}

def validate_requirements(rows,ps):
    if not isinstance(rows,list) or len(rows)!=len(ps):raise WorkspaceError('分析必须覆盖每个原文段落，结果未入库。')
    sources={p['id']:p for p in ps};seen=set();out=[]
    for i,r in enumerate(sorted(rows,key=lambda r:r.get('paragraph_id','') if isinstance(r,dict) else ''),1):
        if not isinstance(r,dict):raise WorkspaceError('需求项格式无效。')
        pid=r.get('paragraph_id')
        if pid not in sources or pid in seen:raise WorkspaceError('存在缺失或重复的原文段落引用。')
        seen.add(pid);criteria=r.get('criteria')
        if not isinstance(criteria,list) or not 1<=len(criteria)<=8:raise WorkspaceError('每个需求须有 1–8 项带原文依据的验收条件。')
        ac=[]
        for j,a in enumerate(criteria,1):
            if not isinstance(a,dict):raise WorkspaceError('验收条件格式无效。')
            quote=text(a.get('quote'),'验收原文',2000)
            if quote not in sources[pid]['text']:raise WorkspaceError('验收条件引用不在对应原文段落内。')
            ac.append({'id':f'AC-{i:03}-{j:02}','text':text(a.get('text'),'验收条件',2000),'quote':quote})
        out.append({'id':f'REQ-{i:03}','paragraph_id':pid,'actor':text(r.get('actor'),'角色',80),
            'behavior':text(r.get('behavior'),'行为',2000),'preconditions':strings(r.get('preconditions',[]),'前置条件'),
            'constraints':strings(r.get('constraints',[]),'约束'),'criteria':ac,'questions':strings(r.get('questions',[]),'待确认问题')})
    return out

def validate_cases(rows,requirements,strict=True):
    if not isinstance(rows,list) or len(rows)>160 or (strict and not rows):raise WorkspaceError('用例集应包含 1–160 条用例。')
    reqs={r['id']:r for r in requirements};out=[];seen=set()
    for c in rows:
        if not isinstance(c,dict):raise WorkspaceError('用例格式无效。')
        cid=text(c.get('id'),'用例编号',50)
        if not re.fullmatch(r'[A-Za-z0-9-]+',cid) or cid in seen:raise WorkspaceError('用例编号重复或格式无效。')
        seen.add(cid);rid=c.get('requirement_id');kind=c.get('kind')
        if rid not in reqs or kind not in KINDS:raise WorkspaceError('用例关联的需求或场景类型无效。')
        valid={a['id'] for a in reqs[rid]['criteria']};links=c.get('criterion_ids')
        if not isinstance(links,list) or not links or any(not isinstance(a,str) or a not in valid for a in links):raise WorkspaceError('每条用例须关联对应需求的有效验收条件。')
        steps=c.get('steps')
        if not isinstance(steps,list) or len(steps)>20 or (strict and not steps) or any(not isinstance(s,dict) for s in steps):raise WorkspaceError('每条用例须有 1–20 个步骤。')
        out.append({'id':cid,'requirement_id':rid,'criterion_ids':list(dict.fromkeys(links)),'kind':kind,
            'title':text(c.get('title'),'用例标题',300,not strict),'precondition':text(c.get('precondition',''),'前置条件',2000,not strict),
            'steps':[{k:text(s.get(k,''),{'action':'操作','input':'输入','expected':'预期'}[k],2000,not strict) for k in ('action','input','expected')} for s in steps],
            'questions':strings(c.get('questions',[]),'待确认问题'),'origin':text(c.get('origin','human'),'来源',60)})
    return out

def generate(ps,mode):
    if mode=='offline':return rule_analysis(ps)
    if mode!='llm':raise WorkspaceError('未知生成方式。')
    if len(ps)>6:raise WorkspaceError('模型首版每次最多 6 段原文，以限制单次输出规模；请拆分需求文档。')
    result=ask_json('分析需求并生成测试设计。只使用输入原文；缺少条件应写入 questions，禁止补造业务阈值。'
        '返回 {"requirements":[{"paragraph_id":"P001","actor":"角色或待确认","behavior":"行为","preconditions":[],"constraints":[],"criteria":[{"text":"验收条件","quote":"本段逐字引用"}],"questions":[]}],'
        '"cases":[{"paragraph_id":"P001","criterion_indexes":[0],"kind":"正向|异常|边界|权限","title":"标题","precondition":"前置条件",'
        '"steps":[{"action":"操作","input":"具体输入或待确认","expected":"可观察预期或待确认"}],"questions":[]}]}。'
        '每段恰好一个需求；每段至少一个正向场景；仅在原文支持时补充异常、边界、权限场景。每段最多四条用例。',{'paragraphs':ps},max_tokens=6000)
    reqs=validate_requirements(result.get('requirements'),ps);mapping={r['paragraph_id']:r for r in reqs};raw=result.get('cases')
    if not isinstance(raw,list) or not 1<=len(raw)<=24:raise WorkspaceError('模型用例数量无效。')
    cases=[]
    for i,c in enumerate(raw,1):
        if not isinstance(c,dict) or c.get('paragraph_id') not in mapping:raise WorkspaceError('模型用例原文引用无效。')
        r=mapping[c['paragraph_id']];indexes=c.get('criterion_indexes')
        if not isinstance(indexes,list) or not indexes or any(type(n) is not int or not 0<=n<len(r['criteria']) for n in indexes):raise WorkspaceError('模型用例验收条件索引无效。')
        cases.append({**c,'id':f'TC-{i:03}','requirement_id':r['id'],'criterion_ids':[r['criteria'][n]['id'] for n in indexes],'origin':'llm'})
    cases=validate_cases(cases,reqs)
    if {c['requirement_id'] for c in cases if c['kind']=='正向'}!={r['id'] for r in reqs}:raise WorkspaceError('模型未为每个需求生成正向用例。')
    return {'requirements':reqs,'cases':cases,'provider':'大模型结构化分析与用例生成','model':model_name(),'usage':None,'prompt_version':'d09-1'}

class RequirementsWorkspace:
    def __init__(self,directory,start_worker=True):
        self.db=Path(directory)/'requirements.sqlite3';self.db.parent.mkdir(parents=True,exist_ok=True)
        self.lock=threading.RLock();self.wake=threading.Event();self.stopping=threading.Event();self.thread=None
        with self.connect() as c:
            c.executescript('''PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT);
            CREATE TABLE IF NOT EXISTS documents(id TEXT PRIMARY KEY,title TEXT,current INTEGER,created TEXT);
            CREATE TABLE IF NOT EXISTS versions(document_id TEXT,number INTEGER,text TEXT,paragraphs TEXT,sha TEXT,filename TEXT,created TEXT,PRIMARY KEY(document_id,number));
            CREATE TABLE IF NOT EXISTS analyses(id TEXT PRIMARY KEY,document_id TEXT,source_version INTEGER,mode TEXT,data TEXT,created TEXT);
            CREATE TABLE IF NOT EXISTS sets(id TEXT PRIMARY KEY,analysis_id TEXT,current INTEGER,created TEXT);
            CREATE TABLE IF NOT EXISTS set_versions(set_id TEXT,number INTEGER,cases TEXT,created TEXT,PRIMARY KEY(set_id,number));
            CREATE TABLE IF NOT EXISTS drafts(set_id TEXT PRIMARY KEY,base_version INTEGER,revision INTEGER,cases TEXT,updated TEXT);
            CREATE TABLE IF NOT EXISTS reviews(id TEXT PRIMARY KEY,set_id TEXT,version INTEGER,case_id TEXT,decision TEXT,actor TEXT,comment TEXT,created TEXT);
            CREATE TABLE IF NOT EXISTS releases(id TEXT PRIMARY KEY,set_id TEXT,version INTEGER,data TEXT,created TEXT);
            CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,document_id TEXT,source_version INTEGER,mode TEXT,status TEXT,phase TEXT,cancel INTEGER,result TEXT,error TEXT,created TEXT,updated TEXT);
            ''')
            if not c.execute("SELECT 1 FROM meta WHERE key='schema'").fetchone():
                self._insert_document(c,'课堂考勤管理',SAMPLE,'sample.md');c.execute("INSERT INTO meta VALUES('schema','1')")
            c.execute("UPDATE jobs SET status='interrupted',phase='服务已重启，请确认后重试',updated=? WHERE status='running'",(now(),))
        if start_worker:self.thread=threading.Thread(target=self._worker,daemon=True,name='requirements-worker');self.thread.start()
    @contextmanager
    def connect(self):
        c=sqlite3.connect(str(self.db),timeout=15);c.row_factory=sqlite3.Row
        try:yield c;c.commit()
        except Exception:c.rollback();raise
        finally:c.close()
    def close(self):
        self.stopping.set();self.wake.set()
        if self.thread:self.thread.join(timeout=2)
    def _row(self,c,table,id):
        r=c.execute('SELECT * FROM '+table+' WHERE id=?',(id,)).fetchone()
        if not r:raise WorkspaceError('记录不存在。',404)
        return dict(r)
    def _version(self,c,doc,version=None):
        d=self._row(c,'documents',doc);version=d['current'] if version is None else int(version)
        r=c.execute('SELECT * FROM versions WHERE document_id=? AND number=?',(doc,version)).fetchone()
        if not r:raise WorkspaceError('需求版本不存在。',404)
        v=dict(r);v['paragraphs']=json.loads(v['paragraphs']);return d,v
    def _insert_document(self,c,title,source,filename):
        ps=paragraphs(source);doc=uid('spec');at=now()
        c.execute('INSERT INTO documents VALUES(?,?,1,?)',(doc,title,at))
        c.execute('INSERT INTO versions VALUES(?,?,?,?,?,?,?)',(doc,1,source,dump(ps),sha(source),filename,at));return doc
    def import_document(self,data):
        title=text(data.get('title'),'需求名称',120);source=data.get('text');paragraphs(source)
        filename=text(data.get('filename','pasted.txt'),'文件名',180)
        if Path(filename).suffix.lower() not in ('.txt','.md'):raise WorkspaceError('仅支持 UTF-8 TXT 或 Markdown。')
        with self.lock,self.connect() as c:
            if c.execute('SELECT count(*) FROM documents').fetchone()[0]>=100:raise WorkspaceError('最多 100 份需求文档。')
            doc=self._insert_document(c,title,source,filename)
        return {'document_id':doc,'version':1}
    def revise(self,doc,data):
        source=data.get('text');ps=paragraphs(source);base=number(data.get('base_version'),'原文版本')
        with self.lock,self.connect() as c:
            d,v=self._version(c,doc)
            if d['current']!=base:raise WorkspaceError('需求原文已更新，请对照最新版本后再保存。',409)
            if sha(source)==v['sha']:return {'document_id':doc,'version':base,'unchanged':True}
            n=base+1;c.execute('INSERT INTO versions VALUES(?,?,?,?,?,?,?)',(doc,n,source,dump(ps),sha(source),v['filename'],now()))
            c.execute('UPDATE documents SET current=? WHERE id=?',(n,doc))
        return {'document_id':doc,'version':n}
    def document(self,doc,version=None):
        with self.connect() as c:
            d,v=self._version(c,doc,version)
            return {'document':d,'version':v,'versions':[dict(r) for r in c.execute('SELECT number,sha,created FROM versions WHERE document_id=? ORDER BY number DESC',(doc,))]}
    def state(self):
        with self.connect() as c:
            documents=[dict(r) for r in c.execute('SELECT d.*,v.sha,v.filename FROM documents d JOIN versions v ON d.id=v.document_id AND d.current=v.number ORDER BY d.created DESC')]
            sets=[dict(r) for r in c.execute('SELECT s.*,a.document_id,a.source_version,a.mode,d.title,d.current AS source_current FROM sets s JOIN analyses a ON a.id=s.analysis_id JOIN documents d ON d.id=a.document_id ORDER BY s.created DESC')]
            jobs=[dict(r) for r in c.execute('SELECT * FROM jobs ORDER BY created DESC LIMIT 100')]
            for j in jobs:j['result']=json.loads(j['result']) if j['result'] else None
            releases=[{'id':r['id'],'set_id':r['set_id'],'version':r['version'],'created':r['created']} for r in c.execute('SELECT * FROM releases ORDER BY created DESC')]
        return {'documents':documents,'sets':sets,'jobs':jobs,'releases':releases,'capabilities':{'llm':configured()},'scope':'本机单工作区 · 服务端持久化 · 未启用账户权限'}
    def analyze(self,doc,data):
        version=number(data.get('version'),'需求版本');mode=data.get('mode','offline')
        if mode not in ('offline','llm'):raise WorkspaceError('未知生成模式。')
        with self.lock,self.connect() as c:
            _,v=self._version(c,doc,version)
            if mode=='llm' and (not configured() or len(v['paragraphs'])>6):raise WorkspaceError('模型模式需要先配置服务，且每份文档最多 6 个非空段落。')
            if c.execute("SELECT count(*) FROM jobs WHERE status IN ('queued','running')").fetchone()[0]>=10:raise WorkspaceError('任务队列已满。',429)
            job=uid('reqjob');c.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?,?)',(job,doc,version,mode,'queued','等待分析',0,None,'',now(),now()))
        self.wake.set();return {'job_id':job}
    def job_action(self,job,action):
        with self.lock,self.connect() as c:
            r=self._row(c,'jobs',job)
            if action=='cancel':
                if r['status'] not in ('queued','running'):raise WorkspaceError('此任务不能取消。',409)
                status='cancelled' if r['status']=='queued' else 'running'
                c.execute('UPDATE jobs SET cancel=1,status=?,phase=?,updated=? WHERE id=?',(status,'已请求取消，等待当前阶段结束',now(),job));return {'job_id':job}
            if action!='retry' or r['status'] not in ('failed','cancelled','interrupted'):raise WorkspaceError('此任务不能重试。',409)
        return self.analyze(r['document_id'],{'version':r['source_version'],'mode':r['mode']})
    def _check(self,c,job):
        r=self._row(c,'jobs',job)
        if self.stopping.is_set() or r['cancel']:raise WorkspaceError('任务已取消。')
    @model_session
    def process_one(self):
        with self.lock,self.connect() as c:
            job=c.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY created LIMIT 1").fetchone()
            if not job:return False
            job=dict(job);c.execute("UPDATE jobs SET status='running',phase='提取验收条件与设计场景',updated=? WHERE id=?",(now(),job['id']))
            _,v=self._version(c,job['document_id'],job['source_version'])
        try:
            result=generate(v['paragraphs'],job['mode'])
            with self.lock,self.connect() as c:
                self._check(c,job['id']);analysis=uid('analysis');setid=uid('suite')
                self._insert_analysis(c,analysis,setid,job['document_id'],job['source_version'],job['mode'],result)
                c.execute("UPDATE jobs SET status='succeeded',phase='用例集已建立，等待人工核查',result=?,updated=? WHERE id=?",(dump({'set_id':setid}),now(),job['id']))
        except Exception as error:
            if not isinstance(error,ValueError):
                import traceback;traceback.print_exc()
            with self.lock,self.connect() as c:
                r=self._row(c,'jobs',job['id']);status='cancelled' if r['cancel'] else 'interrupted' if self.stopping.is_set() else 'failed'
                message=str(error) if isinstance(error,ValueError) else '分析失败，请检查服务端日志。'
                c.execute('UPDATE jobs SET status=?,phase=?,error=?,updated=? WHERE id=?',(status,'结果未入库',message[:1000],now(),job['id']))
        return True
    def _insert_analysis(self,c,analysis,setid,doc,version,mode,result):
        at=now();metadata={k:v for k,v in result.items() if k!='cases'}
        c.execute('INSERT INTO analyses VALUES(?,?,?,?,?,?)',(analysis,doc,version,mode,dump(metadata),at))
        c.execute('INSERT INTO sets VALUES(?,?,1,?)',(setid,analysis,at))
        c.execute('INSERT INTO set_versions VALUES(?,?,?,?)',(setid,1,dump(result['cases']),at))
    def _worker(self):
        while not self.stopping.is_set():
            try:
                if self.process_one():continue
            except Exception:
                import traceback;traceback.print_exc()
            self.wake.wait(1);self.wake.clear()
    def _detail(self,c,setid,version=None):
        s=self._row(c,'sets',setid);a=self._row(c,'analyses',s['analysis_id']);a['data']=json.loads(a['data'])
        d,v=self._version(c,a['document_id'],a['source_version']);n=s['current'] if version is None else int(version)
        row=c.execute('SELECT * FROM set_versions WHERE set_id=? AND number=?',(setid,n)).fetchone()
        if not row:raise WorkspaceError('用例集版本不存在。',404)
        cases=json.loads(row['cases']);_,latest=self._version(c,d['id']);unchanged=set()
        matcher=difflib.SequenceMatcher(a=[p['text'] for p in v['paragraphs']],b=[p['text'] for p in latest['paragraphs']],autojunk=False)
        for block in matcher.get_matching_blocks():unchanged.update(p['id'] for p in v['paragraphs'][block.a:block.a+block.size])
        affected=[r['id'] for r in a['data']['requirements'] if r['paragraph_id'] not in unchanged]
        reviews=[dict(r) for r in c.execute('SELECT * FROM reviews WHERE set_id=? AND version=? ORDER BY created,id',(setid,n))]
        draft=c.execute('SELECT * FROM drafts WHERE set_id=?',(setid,)).fetchone();draft=dict(draft) if draft else None
        if draft:draft['cases']=json.loads(draft['cases'])
        return {'set':s,'version':n,'cases':cases,'analysis':a,'document':d,'source':v,'source_outdated':d['current']!=a['source_version'],
            'affected_requirement_ids':affected,'reviews':reviews,'draft':draft,'versions':[dict(r) for r in c.execute('SELECT number,created FROM set_versions WHERE set_id=? ORDER BY number DESC',(setid,))]}
    def suite(self,setid,version=None):
        with self.connect() as c:return self._detail(c,setid,version)
    def save_draft(self,setid,data):
        base=number(data.get('base_version'),'用例集版本');revision=number(data.get('draft_revision'),'草稿修订号')
        with self.lock,self.connect() as c:
            s=self._detail(c,setid);old=s['draft']
            if s['set']['current']!=base or revision!=(old['revision'] if old else 0):raise WorkspaceError('保存冲突：服务端已有较新的内容。请保留本地修改并对照服务端版本。',409)
            cases=validate_cases(data.get('cases'),s['analysis']['data']['requirements'],strict=False)
            c.execute('INSERT OR REPLACE INTO drafts VALUES(?,?,?,?,?)',(setid,base,revision+1,dump(cases),now()))
        return {'draft_revision':revision+1,'base_version':base,'saved_at':now()}
    def discard_draft(self,setid,data):
        base=number(data.get('base_version'),'用例集版本');revision=number(data.get('draft_revision'),'草稿修订号')
        with self.lock,self.connect() as c:
            s=self._detail(c,setid);draft=s['draft']
            if s['set']['current']!=base or not draft or draft['revision']!=revision:raise WorkspaceError('草稿已经变化，请重新对照后操作。',409)
            c.execute('DELETE FROM drafts WHERE set_id=?',(setid,))
        return {'set_id':setid,'version':base}
    def commit(self,setid,data):
        base=number(data.get('base_version'),'用例集版本');revision=number(data.get('draft_revision'),'草稿修订号')
        with self.lock,self.connect() as c:
            s=self._detail(c,setid);draft=s['draft']
            if s['set']['current']!=base or not draft or draft['revision']!=revision:raise WorkspaceError('保存冲突：草稿或用例集已更新，请重新对照。',409)
            cases=validate_cases(draft['cases'],s['analysis']['data']['requirements']);old={x['id']:x for x in s['cases']}
            for case in cases:
                before=old.get(case['id'])
                case['origin']=before['origin'] if before==case else ('human' if before is None else before['origin'].split('+')[0]+'+human')
            n=base+1;c.execute('INSERT INTO set_versions VALUES(?,?,?,?)',(setid,n,dump(cases),now()))
            c.execute('UPDATE sets SET current=? WHERE id=?',(n,setid));c.execute('DELETE FROM drafts WHERE set_id=?',(setid,))
        return {'set_id':setid,'version':n}
    def _review_ready(self,case):
        fields=case['title']+case['precondition']+dump(case['steps'])
        if case['questions'] or re.search('待确认|待补充|待完善',fields):raise WorkspaceError('用例 '+case['id']+' 仍有待确认内容，请先编辑完善。')
    def review(self,setid,data):
        actor=text(data.get('actor'),'记录人',80);comment=text(data.get('comment',''),'审核说明',2000,True);decision=data.get('decision')
        if decision=='approved' and len(comment)<5:raise WorkspaceError('核对通过时请填写至少 5 字的审核说明。')
        ids=data.get('case_ids');version=number(data.get('version'),'用例集版本')
        if decision not in ('approved','rejected') or not isinstance(ids,list) or not ids or len(ids)>160 or any(not isinstance(x,str) for x in ids):raise WorkspaceError('请选择有效的用例与审核结论。')
        if data.get('confirmed_count')!=len(set(ids)):raise WorkspaceError('请确认本次审核的用例数量。')
        with self.lock,self.connect() as c:
            s=self._detail(c,setid);cases={x['id']:x for x in s['cases']}
            if s['set']['current']!=version or s['draft']:raise WorkspaceError('请先保存并核对最新用例集，未提交草稿不能审核。',409)
            if any(x not in cases for x in ids):raise WorkspaceError('审核包含无效用例。')
            if decision=='approved':
                for cid in set(ids):
                    if cases[cid]['requirement_id'] in s['affected_requirement_ids']:raise WorkspaceError('需求来源已变化，此用例不能核对通过。',409)
                    self._review_ready(cases[cid])
            for cid in set(ids):c.execute('INSERT INTO reviews VALUES(?,?,?,?,?,?,?,?)',(uid('review'),setid,version,cid,decision,actor,comment,now()))
        return {'reviewed':len(set(ids)),'version':version}
    def changes(self,doc,before,after):
        with self.connect() as c:
            _,a=self._version(c,doc,before);_,b=self._version(c,doc,after);changes=[]
            for op,i,j,x,y in difflib.SequenceMatcher(a=[p['text'] for p in a['paragraphs']],b=[p['text'] for p in b['paragraphs']],autojunk=False).get_opcodes():
                if op=='equal':continue
                changes.append({'kind':op,'before':a['paragraphs'][i:j],'after':b['paragraphs'][x:y]})
            return {'document_id':doc,'before':a['number'],'after':b['number'],'changes':changes,'boundary':'逐段文本对齐；不推断跨段语义影响。'}
    def _bundle(self,s):
        return {'format':'engineering-practice-d09','schema':1,'set_id':s['set']['id'],'set_version':s['version'],
            'document':{'id':s['document']['id'],'title':s['document']['title'],'version':s['source']['number'],'text':s['source']['text'],'sha256':s['source']['sha'],'paragraphs':s['source']['paragraphs']},
            'analysis':s['analysis']['data'],'cases':s['cases'],'reviews':s['reviews'],'source_outdated':s['source_outdated'],
            'affected_requirement_ids':s['affected_requirement_ids'],'status':'draft','exported_at':now(),
            'boundary':'本机人工核对记录；关联有效不代表语义覆盖，未执行被测系统。'}
    def publish(self,setid,data):
        actor=text(data.get('actor'),'发布记录人',80);version=number(data.get('version'),'发布版本')
        with self.lock,self.connect() as c:
            s=self._detail(c,setid)
            if s['set']['current']!=version or s['draft'] or s['source_outdated']:raise WorkspaceError('存在草稿、旧版本或需求修订，不能发布。',409)
            decisions={r['case_id']:r['decision'] for r in s['reviews']}
            for case in s['cases']:
                self._review_ready(case)
                if decisions.get(case['id'])!='approved':raise WorkspaceError('所有用例须在当前版本核对通过后才能发布。')
            linked={x for case in s['cases'] for x in case['criterion_ids']};required={a['id'] for r in s['analysis']['data']['requirements'] for a in r['criteria']}
            if linked!=required:raise WorkspaceError('仍有验收条件没有关联用例，不能发布。')
            bundle=self._bundle(s);release=uid('release');bundle.update(status='released',release_id=release,published_by=actor,published_at=now())
            bundle['sha256']=sha(dump(bundle));c.execute('INSERT INTO releases VALUES(?,?,?,?,?)',(release,setid,version,dump(bundle),now()))
        return {'release_id':release,'version':version}
    def import_bundle(self,data):
        bundle=data.get('bundle')
        if not isinstance(bundle,dict) or bundle.get('format')!='engineering-practice-d09' or bundle.get('schema')!=1:raise WorkspaceError('不是受支持的 D09 JSON 导出文件。')
        if bundle.get('sha256') and sha(dump({k:v for k,v in bundle.items() if k!='sha256'}))!=bundle['sha256']:raise WorkspaceError('发布文件校验失败，内容已变化。')
        d=bundle.get('document',{});source=d.get('text');ps=paragraphs(source)
        if d.get('sha256')!=sha(source):raise WorkspaceError('需求原文校验失败。')
        title=text(d.get('title'),'需求名称',120);a=bundle.get('analysis',{})
        reqs=validate_requirements(a.get('requirements'),ps);cases=validate_cases(bundle.get('cases'),reqs)
        result={**a,'requirements':reqs,'cases':cases,'imported_from':{'set_id':bundle.get('set_id'),'set_version':bundle.get('set_version'),'source_version':d.get('version')},'archived_reviews':bundle.get('reviews',[])}
        with self.lock,self.connect() as c:
            if c.execute('SELECT count(*) FROM documents').fetchone()[0]>=100:raise WorkspaceError('最多 100 份需求文档。')
            doc=self._insert_document(c,title,source,'restored.md');analysis=uid('analysis');setid=uid('suite');self._insert_analysis(c,analysis,setid,doc,1,'import',result)
        return {'document_id':doc,'set_id':setid,'version':1}
    def export(self,id,fmt='json',version=None,release=False):
        with self.connect() as c:
            bundle=json.loads(self._row(c,'releases',id)['data']) if release else self._bundle(self._detail(c,id,version))
        if fmt=='json':return dump(bundle).encode('utf-8'),'application/json; charset=utf-8',id+'.json'
        reqs={r['id']:r for r in bundle['analysis']['requirements']};reviews={r['case_id']:r for r in bundle['reviews']};rows=[]
        for case in bundle['cases']:
            review=reviews.get(case['id'],{});r=reqs[case['requirement_id']]
            rows.append([case['id'],case['title'],case['kind'],case['precondition'], '\n'.join(f"{i}. 操作：{s['action']} | 输入：{s['input']} | 预期：{s['expected']}" for i,s in enumerate(case['steps'],1)),case['requirement_id'],','.join(case['criterion_ids']),r['paragraph_id'],case['origin'],review.get('decision','pending'),review.get('actor',''),review.get('created',''),bundle['document']['title'],bundle['document']['version'],bundle['set_version'],bundle['status'],bundle['document']['sha256'],'\n'.join(case['questions'])])
        headers=['用例编号','标题','类型','前置条件','步骤与输入预期','需求编号','验收条件','原文段落','来源','审核','记录人','审核时间','需求名称','需求版本','用例集版本','发布状态','原文SHA256','待确认问题']
        if fmt=='csv':
            stream=io.StringIO(newline='');writer=csv.writer(stream);writer.writerow(headers)
            # Prevent spreadsheet formulas when exporting user or model text.
            writer.writerows([["'"+str(x) if str(x).lstrip().startswith(('=','+','-','@','\t','\r')) else x for x in row] for row in rows])
            return stream.getvalue().encode('utf-8-sig'),'text/csv; charset=utf-8',id+'.csv'
        if fmt=='markdown':
            esc=lambda x:str(x).replace('<','&lt;').replace('>','&gt;').replace('|','\\|')
            out=[f"# {esc(bundle['document']['title'])}",f"需求 v{bundle['document']['version']} · 用例集 v{bundle['set_version']} · {bundle['status']}",bundle['boundary']]
            for row in rows:out+=['\n## '+esc(row[0])+' · '+esc(row[1])]+[f'**{headers[i]}**：{esc(row[i])}' for i in (2,3,4,5,6,7,8,9,10,11,17)]
            out+=['\n## 原文']+[f"{p['id']}：{esc(p['text'])}" for p in bundle['document']['paragraphs']]
            return '\n\n'.join(out).encode('utf-8'),'text/markdown; charset=utf-8',id+'.md'
        raise WorkspaceError('仅支持 JSON、CSV 或 Markdown 导出。')

_singleton=None
_singleton_lock=threading.Lock()
def get_requirements_workspace():
    global _singleton
    with _singleton_lock:
        if _singleton is None:_singleton=RequirementsWorkspace(os.environ.get('LAB_DATA_DIR',str(Path(__file__).resolve().parents[1]/'data')))
        return _singleton
