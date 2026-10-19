"""D13 local evidence workspace. Exact quote checks do not prove semantic support."""
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit
import uuid
from shared.model_client import ask_json, configured
from shared.process_workspace import WorkspaceError
ROOT = Path(__file__).resolve().parents[1]
FIELDS = ('method', 'finding', 'limitation')
SCOPES = ('full_text', 'abstract', 'notes')
FINAL = ('succeeded', 'failed', 'cancelled', 'interrupted')

def now():
    return datetime.now(timezone.utc).isoformat()

def uid(p):
    return p + '-' + uuid.uuid4().hex[:16]

def dump(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True, allow_nan=False)

def sha(x):
    return hashlib.sha256(x if isinstance(x, bytes) else x.encode() if isinstance(x, str) else dump(x).encode()).hexdigest()

def text(x, label, limit=300, empty=False):
    if not isinstance(x, str) or len(x) > limit or (not empty and (not x.strip())):
        raise WorkspaceError(label + f'应为{(0 if empty else 1)}–{limit}字。')
    return x.strip()

def model_fp():
    return sha({'base': os.environ.get('LAB_LLM_BASE_URL'), 'model': os.environ.get('LAB_LLM_MODEL')})

def pages_from(raw, name):
    if name.lower().endswith('.pdf'):
        if not raw.startswith(b'%PDF-'):
            raise WorkspaceError('文件不是 PDF。')
        try:
            run = subprocess.run([sys.executable, '-I', '-X', 'utf8', str(ROOT / 'scripts/parse_process_pdf.py')], input=raw, capture_output=True, timeout=25)
            value = json.loads(run.stdout.decode('utf-8'))
            if run.returncode or value.get('error'):
                raise WorkspaceError(value.get('error', 'PDF 解析失败。'))
            return value['pages']
        except WorkspaceError:
            raise
        except (subprocess.TimeoutExpired, ValueError, KeyError):
            raise WorkspaceError('PDF 无法解析或超过25秒；可提供 UTF-8 原文文本。') from None
    try:
        value = raw.decode('utf-8-sig').replace('\x00', '').strip()
    except UnicodeError:
        raise WorkspaceError('TXT/Markdown 必须使用 UTF-8 编码。') from None
    if not value or len(value) > 300000:
        raise WorkspaceError('文本应为1–30万字。')
    pages = [{'page': i + 1, 'text': v.strip()} for i, v in enumerate(value.split('\x0c')) if v.strip()]
    if len(pages) > 100:
        raise WorkspaceError('最多100个文本分页。')
    return pages

def locate(pages, page, quote, start=None):
    quote = text(quote, '逐字证据', 1500)
    p = next((p for p in pages if p['page'] == page), None)
    if not p:
        raise WorkspaceError('引用页码不存在。')
    value = p['text']
    if start is None:
        if value.count(quote) != 1:
            raise WorkspaceError('原文中没有唯一匹配；请指定正确页码与起始字符位置。')
        start = value.find(quote)
    if type(start) is not int or start < 0 or value[start:start + len(quote)] != quote:
        raise WorkspaceError('引用与原文位置不一致，未保存。')
    return {'page': page, 'start': start, 'end': start + len(quote), 'quote': quote}

def validate_sections(rows, outline, evidence):
    if not isinstance(rows, list) or len(rows) != len(outline):
        raise WorkspaceError('章节必须与已确认提纲一一对应。')
    allowed = {e['id'] for e in evidence}
    result = []
    total = 0
    for target, row in zip(outline, rows):
        if not isinstance(row, dict) or row.get('id') != target['id']:
            raise WorkspaceError('章节标识与提纲不一致。')
        claims = row.get('claims')
        if not isinstance(claims, list) or not 1 <= len(claims) <= 12:
            raise WorkspaceError('每章应包含1–12条带证据论述。')
        checked = []
        for i, c in enumerate(claims, 1):
            if not isinstance(c, dict):
                raise WorkspaceError('论述格式无效。')
            ids = c.get('evidence_ids')
            if not isinstance(ids, list) or not 1 <= len(ids) <= 4 or any((not isinstance(e, str) or e not in allowed for e in ids)):
                raise WorkspaceError('论述引用了未核对、过期或其他专题的证据。')
            checked.append({'id': target['id'] + f'-C{i:02}', 'text': text(c.get('text'), '论述', 3000), 'evidence_ids': list(dict.fromkeys(ids))})
        total += len(checked)
        result.append({'id': target['id'], 'title': target['title'], 'claims': checked})
    if total > 40:
        raise WorkspaceError('单份草案最多40条论述。')
    return result

class LiteratureWorkspace:

    def __init__(self, directory, start_worker=True):
        self.db = Path(directory) / 'literature.sqlite3'
        self.db.parent.mkdir(parents=True, exist_ok=True)
        self.stop = threading.Event()
        self.wake = threading.Event()
        self.owner = uid('reader')
        self.thread = None
        with self.connect() as c:
            c.executescript('PRAGMA journal_mode=WAL;\n            CREATE TABLE IF NOT EXISTS papers(id TEXT PRIMARY KEY,current INTEGER NOT NULL DEFAULT 0,active INTEGER NOT NULL DEFAULT 1,created TEXT NOT NULL);\n            CREATE TABLE IF NOT EXISTS paper_versions(paper TEXT,number INTEGER,metadata TEXT,filename TEXT,sha TEXT,raw BLOB,pages TEXT,status TEXT,error TEXT,created TEXT,PRIMARY KEY(paper,number));\n            CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY,revision INTEGER NOT NULL,data TEXT NOT NULL,created TEXT NOT NULL,updated TEXT NOT NULL);\n            CREATE TABLE IF NOT EXISTS selections(project TEXT,paper TEXT,revision INTEGER,decision TEXT,reason TEXT,updated TEXT,PRIMARY KEY(project,paper));\n            CREATE TABLE IF NOT EXISTS evidence(id TEXT PRIMARY KEY,project TEXT,paper TEXT,version INTEGER,revision INTEGER,data TEXT,status TEXT,actor TEXT,comment TEXT,created TEXT,updated TEXT);\n            CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,project TEXT,kind TEXT,mode TEXT,status TEXT,payload TEXT,context TEXT,model TEXT,model_fp TEXT,owner TEXT,heartbeat REAL,cancel INTEGER DEFAULT 0,error TEXT,result TEXT,created TEXT,updated TEXT);\n            CREATE TABLE IF NOT EXISTS nodes(job TEXT,key TEXT,status TEXT,result TEXT,error TEXT,reused_from TEXT,PRIMARY KEY(job,key));\n            CREATE TABLE IF NOT EXISTS drafts(id TEXT PRIMARY KEY,project TEXT,current INTEGER,context TEXT,draft TEXT,draft_revision INTEGER,created TEXT);\n            CREATE TABLE IF NOT EXISTS draft_versions(draft TEXT,number INTEGER,sections TEXT,created TEXT,PRIMARY KEY(draft,number));\n            CREATE TABLE IF NOT EXISTS reviews(id TEXT PRIMARY KEY,draft TEXT,version INTEGER,claim TEXT,decision TEXT,actor TEXT,comment TEXT,created TEXT);\n            CREATE TABLE IF NOT EXISTS releases(id TEXT PRIMARY KEY,draft TEXT,version INTEGER,bundle TEXT,created TEXT);\n            CREATE INDEX IF NOT EXISTS queue ON jobs(status,created);CREATE INDEX IF NOT EXISTS evidence_project ON evidence(project);')
        if start_worker:
            self.thread = threading.Thread(target=self.loop, daemon=True)
            self.thread.start()

    @contextmanager
    def connect(self, write=False):
        c = sqlite3.connect(self.db, timeout=15)
        c.row_factory = sqlite3.Row
        c.execute('PRAGMA busy_timeout=15000')
        try:
            if write:
                c.execute('BEGIN IMMEDIATE')
            yield c
            c.commit()
        except BaseException:
            c.rollback()
            raise
        finally:
            c.close()

    def close(self):
        self.stop.set()
        self.wake.set()
        if self.thread:
            self.thread.join(5)

    def required(self, c, table, id):
        if table not in ('papers', 'projects', 'jobs', 'drafts', 'releases', 'evidence'):
            raise ValueError('Invalid table')
        r = c.execute('SELECT * FROM ' + table + ' WHERE id=?', (id,)).fetchone()
        if not r:
            raise WorkspaceError('记录不存在。', 404)
        return r

    def paper(self, id, version=None, c=None):
        if c is None:
            with self.connect() as connection:
                return self.paper(id, version, connection)
        p = dict(self.required(c, 'papers', id))
        versions = c.execute('SELECT number,status,error,filename,created FROM paper_versions WHERE paper=? ORDER BY number DESC', (id,)).fetchall()
        try:
            number = int(version) if version is not None else p['current'] or versions[0]['number']
        except (ValueError, IndexError):
            raise WorkspaceError('文献版本无效。') from None
        row = c.execute('SELECT * FROM paper_versions WHERE paper=? AND number=?', (id, number)).fetchone()
        if not row:
            raise WorkspaceError('文献版本不存在。', 404)
        v = dict(row)
        v.pop('raw')
        v['metadata'] = json.loads(v['metadata'])
        v['pages'] = json.loads(v['pages'])
        return {'paper': p, 'version': v, 'versions': [dict(r) for r in versions]}

    def import_paper(self, value):
        filename = text(value.get('filename', 'pasted.txt'), '文件名', 180).replace('\\', '/').split('/')[-1]
        if Path(filename).suffix.lower() not in ('.pdf', '.txt', '.md'):
            raise WorkspaceError('仅支持文本型PDF、UTF-8 TXT/Markdown。')
        try:
            raw = base64.b64decode(value['content_base64'], validate=True) if 'content_base64' in value else text(value.get('text'), '原文', 300000).encode()
        except (ValueError, TypeError):
            raise WorkspaceError('文件编码无效。') from None
        if not 0 < len(raw) <= 8 * 1024 * 1024:
            raise WorkspaceError('单份文件应为1字节–8 MiB。')
        scope = value.get('scope', 'full_text')
        if scope not in SCOPES:
            raise WorkspaceError('请选择原文、摘要或阅读摘记。')
        year = value.get('year')
        if year in ('', None):
            year = None
        else:
            try:
                year = int(year)
            except (ValueError, TypeError):
                raise WorkspaceError('年份无效。') from None
            if not 1900 <= year <= 2100:
                raise WorkspaceError('年份应在1900–2100之间。')
        url = text(value.get('url', ''), '原文链接', 1000, True)
        if url and (urlsplit(url).scheme not in ('http', 'https') or not urlsplit(url).netloc):
            raise WorkspaceError('原文链接仅接受 HTTP(S)，导入不会抓取该网址。')
        doi = text(value.get('doi', ''), 'DOI', 200, True).lower().removeprefix('https://doi.org/')
        if doi and (not re.fullmatch('10\\.\\d{4,9}/\\S+', doi)):
            raise WorkspaceError('DOI格式无效。')
        meta = {'title': text(value.get('title'), '标题', 300), 'authors': text(value.get('authors', ''), '作者', 500, True), 'year': year, 'doi': doi, 'url': url, 'scope': scope}
        digest = sha(raw)
        id = value.get('paper_id')
        stamp = now()
        with self.connect(True) as c:
            if id:
                p = self.required(c, 'papers', id)
                if not p['active'] or value.get('base_version') != p['current']:
                    raise WorkspaceError('文献版本已变化，请刷新后上传。', 409)
                if c.execute("SELECT 1 FROM paper_versions WHERE paper=? AND status='pending'", (id,)).fetchone():
                    raise WorkspaceError('此文献仍在解析，请等待后再修订。', 409)
                number = c.execute('SELECT max(number) FROM paper_versions WHERE paper=?', (id,)).fetchone()[0] + 1
            else:
                duplicate = c.execute("SELECT v.paper,v.number FROM paper_versions v JOIN papers p ON p.id=v.paper WHERE p.active=1 AND (p.current=v.number OR v.status='pending') AND v.sha=? ORDER BY v.number DESC LIMIT 1", (digest,)).fetchone()
                if duplicate:
                    return {'paper_id': duplicate['paper'], 'version': duplicate['number'], 'deduplicated': True}
                if doi:
                    for p in c.execute('SELECT id FROM papers WHERE active=1'):
                        if self.paper(p['id'], c=c)['version']['metadata']['doi'] == doi:
                            raise WorkspaceError('DOI已存在，请在对应文献中上传新版本。', 409)
                if c.execute('SELECT count(*) FROM papers WHERE active=1').fetchone()[0] >= 100:
                    raise WorkspaceError('本机首版最多100份有效文献。')
                id = uid('paper')
                number = 1
                c.execute('INSERT INTO papers VALUES(?,0,1,?)', (id, stamp))
            if c.execute('SELECT coalesce(sum(length(raw)),0) FROM paper_versions').fetchone()[0] + len(raw) > 256 * 1024 * 1024:
                raise WorkspaceError('文献存储已达256 MiB，请备份并整理。')
            c.execute("INSERT INTO paper_versions VALUES(?,?,?,?,?,?,?,'pending','',?)", (id, number, dump(meta), filename, digest, raw, '[]', stamp))
            job = self._enqueue(c, None, 'import', 'offline', {'paper': id, 'version': number}, None)
        self.wake.set()
        return {'paper_id': id, 'version': number, 'job_id': job, 'deduplicated': False}

    def delete_paper(self, id, version):
        with self.connect(True) as c:
            p = self.required(c, 'papers', id)
            if p['current'] != version:
                raise WorkspaceError('文献版本已变化。', 409)
            c.execute('UPDATE papers SET active=0 WHERE id=?', (id,))
        return {'deleted': True}

    def project(self, id, c=None):
        if c is None:
            with self.connect() as connection:
                return self.project(id, connection)
        row = dict(self.required(c, 'projects', id))
        row.update(json.loads(row.pop('data')))
        row['selections'] = [dict(r) for r in c.execute('SELECT * FROM selections WHERE project=? ORDER BY updated', (id,))]
        return row

    def save_project(self, value, id=None):
        outline = value.get('outline', ['研究方法', '主要发现', '局限与研究空白'])
        if not isinstance(outline, list) or not 1 <= len(outline) <= 4:
            raise WorkspaceError('提纲应为1–4章。')
        body = {'title': text(value.get('title'), '专题名称', 120), 'question': text(value.get('question'), '研究问题', 1500), 'inclusion': text(value.get('inclusion', ''), '纳入标准', 2000, True), 'exclusion': text(value.get('exclusion', ''), '排除标准', 2000, True), 'outline': [{'id': f'SEC-{i:02}', 'title': text(s, '章节标题', 120)} for i, s in enumerate(outline, 1)], 'outline_confirmed': value.get('outline_confirmed') is True}
        stamp = now()
        with self.connect(True) as c:
            if id:
                row = self.required(c, 'projects', id)
                if value.get('revision') != row['revision']:
                    raise WorkspaceError('专题已被修改，请刷新后合并。', 409)
                c.execute('UPDATE projects SET data=?,revision=revision+1,updated=? WHERE id=?', (dump(body), stamp, id))
            else:
                id = uid('review')
                c.execute('INSERT INTO projects VALUES(?,1,?,?,?)', (id, dump(body), stamp, stamp))
        return {'project_id': id}

    def screen(self, project, paper, value):
        decision = value.get('decision')
        reason = text(value.get('reason'), '筛选理由', 1500)
        if decision not in ('included', 'excluded', 'undecided'):
            raise WorkspaceError('未知筛选结论。')
        with self.connect(True) as c:
            self.required(c, 'projects', project)
            p = self.required(c, 'papers', paper)
            if not p['active'] or p['current'] == 0:
                raise WorkspaceError('文献尚未就绪或已删除。', 409)
            r = c.execute('SELECT revision FROM selections WHERE project=? AND paper=?', (project, paper)).fetchone()
            if value.get('revision', 0) != (r[0] if r else 0):
                raise WorkspaceError('筛选结论已变化，请刷新。', 409)
            if decision == 'included' and c.execute("SELECT count(*) FROM selections WHERE project=? AND decision='included' AND paper<>?", (project, paper)).fetchone()[0] >= 6:
                raise WorkspaceError('一个专题最多纳入6篇文献，请缩小范围。')
            c.execute('INSERT OR REPLACE INTO selections VALUES(?,?,?,?,?,?)', (project, paper, r[0] + 1 if r else 1, decision, reason, now()))
        return {'saved': True}

    def evidence(self, project, c=None):
        if c is None:
            with self.connect() as connection:
                return self.evidence(project, connection)
        self.required(c, 'projects', project)
        out = []
        for row in c.execute('SELECT * FROM evidence WHERE project=? ORDER BY created', (project,)):
            e = dict(row)
            e.update(json.loads(e.pop('data')))
            p = c.execute('SELECT active,current FROM papers WHERE id=?', (e['paper'],)).fetchone()
            sel = c.execute('SELECT decision FROM selections WHERE project=? AND paper=?', (project, e['paper'])).fetchone()
            e['stale'] = not p or not p['active'] or p['current'] != e['version'] or (not sel) or (sel[0] != 'included')
            out.append(e)
        return out

    def _evidence_value(self, value, paper):
        field = value.get('field')
        if field not in FIELDS:
            raise WorkspaceError('证据字段应为方法、发现或局限。')
        page = value.get('page')
        if type(page) is not int:
            raise WorkspaceError('页码必须为整数。')
        return {**locate(paper['version']['pages'], page, value.get('quote'), value.get('start')), 'field': field, 'summary': text(value.get('summary'), '证据说明', 2000)}

    def save_evidence(self, project, value, id=None):
        with self.connect(True) as c:
            self.required(c, 'projects', project)
            paper = self.paper(value.get('paper'), c=c)
            sel = c.execute('SELECT decision FROM selections WHERE project=? AND paper=?', (project, paper['paper']['id'])).fetchone()
            if not paper['paper']['active'] or paper['version']['number'] != value.get('version') or (not sel) or (sel[0] != 'included'):
                raise WorkspaceError('请选择当前纳入文献的有效版本。', 409)
            body = self._evidence_value(value, paper)
            stamp = now()
            if id:
                old = self.required(c, 'evidence', id)
                if old['project'] != project:
                    raise WorkspaceError('证据不属于此专题。', 404)
                if value.get('revision') != old['revision']:
                    raise WorkspaceError('证据已变化，请刷新后合并。', 409)
                c.execute("UPDATE evidence SET paper=?,version=?,revision=revision+1,data=?,status='pending',actor='',comment='',updated=? WHERE id=?", (value['paper'], value['version'], dump(body), stamp, id))
            else:
                if c.execute('SELECT count(*) FROM evidence WHERE project=?', (project,)).fetchone()[0] >= 60:
                    raise WorkspaceError('单个专题最多60条证据。')
                id = uid('ev')
                c.execute("INSERT INTO evidence VALUES(?,?,?,?,1,?,'pending','','',?,?)", (id, project, value['paper'], value['version'], dump(body), stamp, stamp))
        return {'evidence_id': id}

    def review_evidence(self, id, value):
        actor = text(value.get('actor'), '核对人', 80)
        comment = text(value.get('comment'), '核对说明', 2000)
        status = value.get('status')
        if status not in ('confirmed', 'conflict'):
            raise WorkspaceError('核对结论无效。')
        with self.connect(True) as c:
            row = self.required(c, 'evidence', id)
            e = next((e for e in self.evidence(row['project'], c) if e['id'] == id))
            if value.get('revision') != row['revision'] or e['stale']:
                raise WorkspaceError('证据已变化或过期，请重新摘录与核对。', 409)
            c.execute('UPDATE evidence SET status=?,actor=?,comment=?,revision=revision+1,updated=? WHERE id=?', (status, actor, comment, now(), id))
        return {'saved': True}

    def context(self, project, c=None):
        if c is None:
            with self.connect() as connection:
                return self.context(project, connection)
        p = self.project(project, c)
        papers = []
        for s in p['selections']:
            if s['decision'] == 'included':
                doc = self.paper(s['paper'], c=c)
                papers.append({'id': s['paper'], 'version': doc['paper']['current'], 'active': doc['paper']['active'], 'metadata': doc['version']['metadata'], 'sha': doc['version']['sha'], 'pages': doc['version']['pages'], 'status': doc['version']['status']})
        evidence = self.evidence(project, c)
        body = {'project': {k: p[k] for k in ('id', 'revision', 'title', 'question', 'inclusion', 'exclusion', 'outline', 'outline_confirmed')}, 'selections': p['selections'], 'papers': papers, 'evidence': evidence}
        body['fingerprint'] = sha(body)
        return body

    def state(self):
        self.recover()
        with self.connect() as c:
            papers = []
            for r in c.execute('SELECT id FROM papers WHERE active=1 ORDER BY created DESC'):
                p = self.paper(r['id'], c=c)
                v = p['version']
                papers.append({'id': r['id'], 'current': p['paper']['current'], **v['metadata'], 'filename': v['filename'], 'status': v['status'], 'pages': len(v['pages'])})
            projects = [self.project(r['id'], c) for r in c.execute('SELECT id FROM projects ORDER BY updated DESC')]
            jobs = [{k: r[k] for k in ('id', 'project', 'kind', 'mode', 'status', 'error', 'created', 'updated')} for r in c.execute('SELECT * FROM jobs ORDER BY created DESC LIMIT 100')]
            drafts = [dict(r) for r in c.execute('SELECT id,project,current,draft_revision,created FROM drafts ORDER BY created DESC')]
            releases = [dict(r) for r in c.execute('SELECT id,draft,version,created FROM releases ORDER BY created DESC')]
        return {'papers': papers, 'projects': projects, 'jobs': jobs, 'drafts': drafts, 'releases': releases, 'capabilities': {'llm': configured(), 'pdf': True}, 'schema': 1}

    def _enqueue(self, c, project, kind, mode, payload, context):
        id = uid('job')
        stamp = now()
        if context is not None:
            existing = c.execute("SELECT id FROM jobs WHERE project=? AND kind=? AND mode=? AND context=? AND status IN ('queued','running') ORDER BY created LIMIT 1", (project, kind, mode, dump(context))).fetchone()
            if existing:
                return existing['id']
        if c.execute("SELECT count(*) FROM jobs WHERE status IN ('queued','running')").fetchone()[0] >= 24:
            raise WorkspaceError('等待任务已达24项，请先完成或取消。', 409)
        c.execute("INSERT INTO jobs(id,project,kind,mode,status,payload,context,model,model_fp,cancel,error,result,created,updated) VALUES(?,?,?,?,?,?,?,?,?,0,'','{}',?,?)", (id, project, kind, mode, 'queued', dump(payload), dump(context) if context else None, os.environ.get('LAB_LLM_MODEL') if mode != 'offline' else None, model_fp() if mode != 'offline' else None, stamp, stamp))
        return id

    def enqueue(self, project, kind, value):
        mode = value.get('mode', 'offline')
        if kind not in ('read', 'write') or mode not in ('offline', 'single', 'multi'):
            raise WorkspaceError('任务或生成方式无效。')
        if mode != 'offline' and (not configured()):
            raise WorkspaceError('模型尚未配置；没有自动回退。', 503)
        with self.connect(True) as c:
            ctx = self.context(project, c)
            if not ctx['papers'] or any((not p['active'] or p['version'] == 0 or p['status'] != 'ready' for p in ctx['papers'])):
                raise WorkspaceError('请先纳入已就绪的文献。', 409)
            if kind == 'write':
                if not ctx['project']['outline_confirmed']:
                    raise WorkspaceError('请先确认章节提纲。', 409)
                confirmed = [e for e in ctx['evidence'] if not e['stale'] and e['status'] == 'confirmed']
                if not confirmed or any((e['stale'] or e['status'] != 'confirmed' for e in ctx['evidence'])):
                    raise WorkspaceError('证据存在待核对、冲突或过期项，请先处理矩阵。', 409)
                if {p['id'] for p in ctx['papers']} != {e['paper'] for e in confirmed}:
                    raise WorkspaceError('每篇纳入文献至少需要一条已核对证据。', 409)
            if mode != 'offline':
                length = sum((len(p['text']) for paper in ctx['papers'] for p in paper['pages'])) if kind == 'read' else len(dump(ctx['evidence']))
                if length > 24000:
                    raise WorkspaceError('模型输入超过24000字；请缩小专题或手工摘录，不截断原文后冒充全文阅读。')
            id = self._enqueue(c, project, kind, mode, {}, ctx)
        self.wake.set()
        return {'job_id': id}

    def job(self, id):
        with self.connect() as c:
            r = dict(self.required(c, 'jobs', id))
            r['payload'] = json.loads(r['payload'])
            r['result'] = json.loads(r['result'])
            r['nodes'] = [{**dict(n), 'result': json.loads(n['result']) if n['result'] else None} for n in c.execute('SELECT * FROM nodes WHERE job=? ORDER BY key', (id,))]
            r.pop('owner')
            r.pop('heartbeat')
            r['context'] = json.loads(r['context']) if r['context'] else None
            return r

    def job_action(self, id, action):
        with self.connect(True) as c:
            old = dict(self.required(c, 'jobs', id))
            old['context'] = json.loads(old['context']) if old['context'] else None
            old['payload'] = json.loads(old['payload'])
            old['nodes'] = [{**dict(n), 'result': json.loads(n['result']) if n['result'] else None} for n in c.execute('SELECT * FROM nodes WHERE job=?', (id,))]
            if action == 'cancel':
                if old['status'] not in FINAL:
                    c.execute("UPDATE jobs SET cancel=1,status=CASE WHEN status='queued' THEN 'cancelled' ELSE status END,updated=? WHERE id=?", (now(), id))
                if old['kind'] == 'import' and old['status'] == 'queued':
                    c.execute("UPDATE paper_versions SET status='failed',error='解析已取消。' WHERE paper=? AND number=?", (old['payload']['paper'], old['payload']['version']))
                return {'job_id': id}
            if action != 'retry' or old['status'] not in ('failed', 'interrupted', 'cancelled'):
                raise WorkspaceError('只能显式重试失败、中断或取消的任务。', 409)
            if old['context'] and self.context(old['project'], c)['fingerprint'] != old['context']['fingerprint']:
                raise WorkspaceError('输入已变化，请按当前专题新建任务。', 409)
            if old['mode'] != 'offline' and old['model_fp'] != model_fp():
                raise WorkspaceError('模型配置已变化，请新建任务。', 409)
            if old['kind'] == 'import':
                p = self.paper(old['payload']['paper'], old['payload']['version'], c)
                if not p['paper']['active'] or p['paper']['current'] >= old['payload']['version'] or p['versions'][0]['number'] != old['payload']['version'] or (p['version']['status'] == 'pending'):
                    raise WorkspaceError('文献解析已在进行、已完成或版本已被替代。', 409)
            new = self._enqueue(c, old['project'], old['kind'], old['mode'], old['payload'], old['context'])
            for n in old['nodes']:
                if n['status'] == 'succeeded':
                    c.execute("INSERT INTO nodes VALUES(?,?,'succeeded',?,'',?)", (new, n['key'], dump(n['result']), id))
            if old['kind'] == 'import':
                c.execute("UPDATE paper_versions SET status='pending',error='' WHERE paper=? AND number=?", (old['payload']['paper'], old['payload']['version']))
        self.wake.set()
        return {'job_id': new}

    def recover(self):
        with self.connect(True) as c:
            for r in c.execute("SELECT id FROM jobs WHERE status='running' AND heartbeat<?", (time.time() - 20,)).fetchall():
                c.execute("UPDATE jobs SET status='interrupted',error='执行心跳中断；可显式重试失败节点。',updated=? WHERE id=?", (now(), r['id']))
                c.execute("UPDATE nodes SET status='interrupted' WHERE job=? AND status='running'", (r['id'],))
                job = self.required(c, 'jobs', r['id'])
                if job['kind'] == 'import':
                    value = json.loads(job['payload'])
                    c.execute("UPDATE paper_versions SET status='failed',error='解析中断。' WHERE paper=? AND number=? AND status='pending'", (value['paper'], value['version']))

    def cancelled(self, id):
        with self.connect() as c:
            r = self.required(c, 'jobs', id)
            return self.stop.is_set() or r['cancel'] or r['status'] != 'running' or (r['owner'] != self.owner)

    def _node(self, job, key, fn):
        with self.connect(True) as c:
            r = c.execute('SELECT * FROM nodes WHERE job=? AND key=?', (job, key)).fetchone()
            if r and r['status'] == 'succeeded':
                return json.loads(r['result'])
            if self.cancelled(job):
                raise InterruptedError('任务已取消。')
            c.execute("INSERT OR REPLACE INTO nodes VALUES(?,?,'running',NULL,'',NULL)", (job, key))
        try:
            result = fn()
            with self.connect(True) as c:
                c.execute("UPDATE nodes SET status='succeeded',result=? WHERE job=? AND key=?", (dump(result), job, key))
            return result
        except Exception as e:
            message = str(e) if isinstance(e, (WorkspaceError, ValueError, InterruptedError)) else '节点执行失败，请查看服务日志。'
            with self.connect(True) as c:
                c.execute("UPDATE nodes SET status='failed',error=? WHERE job=? AND key=?", (message, job, key))
            raise

    def _read_rows(self, result, ctx, only=None):
        if not isinstance(result, list) or not 1 <= len(result) <= 18:
            raise WorkspaceError('阅读结果应为1–18条带定位的证据。')
        papers = {p['id']: p for p in ctx['papers']}
        out = []
        for r in result:
            if not isinstance(r, dict) or r.get('paper') not in papers or (only and r.get('paper') != only):
                raise WorkspaceError('阅读结果引用了错误文献。')
            if sum((e['paper'] == r['paper'] for e in out)) >= 3:
                raise WorkspaceError('每篇阅读最多返回3条证据，请缩小输出。')
            p = papers[r['paper']]
            data = self._evidence_value(r, {'version': {'pages': p['pages']}})
            out.append({'paper': p['id'], 'version': p['version'], **data})
        required = {only} if only else set(papers)
        if {r['paper'] for r in out} != required:
            raise WorkspaceError('阅读结果未覆盖全部输入文献。')
        return out

    def _read(self, job, ctx):
        mode = job['mode']
        papers = ctx['papers']
        prompt = '你是文献阅读者，只依据提供的原文。返回 {"evidence":[{"paper":"输入id","field":"method|finding|limitation","page":页码,"quote":"该页逐字连续片段","summary":"证据说明"}]}。每篇1–3条。禁止外部引用、补造实验、跨页拼接引用；只读摘要或摘记时说明来源范围。'
        if mode == 'single':
            return self._node(job['id'], 'reader:all', lambda: self._read_rows(ask_json(prompt, {'question': ctx['project']['question'], 'papers': papers}, max_tokens=5000).get('evidence'), ctx))

        def one(p):

            def call():
                if mode == 'multi':
                    return self._read_rows(ask_json(prompt, {'question': ctx['project']['question'], 'papers': [p]}, max_tokens=2200).get('evidence'), ctx, p['id'])
                page = p['pages'][0]
                matches = list(re.finditer('[^。.!?\\n]+[。.!?]?', page['text']))
                rows = []
                for field, m in zip(['method'] * 3, matches[:3]):
                    quote = m.group().strip()[:1000]
                    if not quote:
                        continue
                    start = m.start() + len(m.group()) - len(m.group().lstrip())
                    rows.append({'paper': p['id'], 'field': field, 'page': page['page'], 'start': start, 'quote': quote, 'summary': '未分类摘录，请核对类别与含义：' + quote})
                if not rows:
                    raise WorkspaceError('第一页无可摘录文本，请手工建立证据。')
                return self._read_rows(rows, ctx, p['id'])
            return self._node(job['id'], 'reader:' + p['id'], call)
        if mode == 'multi':
            with ThreadPoolExecutor(max_workers=3) as pool:
                results = list(pool.map(one, papers))
        else:
            results = [one(p) for p in papers]
        return [row for group in results for row in group]

    def _write(self, job, ctx):
        evidence = [e for e in ctx['evidence'] if e['status'] == 'confirmed' and (not e['stale'])]
        outline = ctx['project']['outline']
        mode = job['mode']
        prompt = '你是综述章节作者。只依据输入证据说明与逐字引文，返回 {"sections":[{"id":"输入章节id","claims":[{"text":"可审核论述","evidence_ids":["输入证据id"]}]}]}。章节顺序与输入一致。每章1–4条论述，每条绑定1–4个输入证据。不要编造外部文献、数值或把不同条件的实验当作可比。区分原文、摘要和阅读摘记。'

        def one(sections, key):

            def call():
                if mode == 'offline':
                    result = []
                    for section in sections:
                        index = next((i for i, s in enumerate(outline) if s['id'] == section['id']))
                        items = [e for e in evidence if e['field'] == FIELDS[index % 3]] or evidence
                        result.append({'id': section['id'], 'claims': [{'text': '证据摘编（待解释）：' + e['summary'], 'evidence_ids': [e['id']]} for e in items[:6]]})
                else:
                    result = ask_json(prompt, {'question': ctx['project']['question'], 'outline': sections, 'papers': [{'id': p['id'], 'metadata': p['metadata']} for p in ctx['papers']], 'evidence': evidence}, max_tokens=4500).get('sections')
                return validate_sections(result, sections, evidence)
            return self._node(job['id'], key, call)
        if mode == 'multi':
            with ThreadPoolExecutor(max_workers=2) as pool:
                groups = list(pool.map(lambda s: one([s], 'writer:' + s['id']), outline))
            sections = [s for group in groups for s in group]
        else:
            sections = one(outline, 'writer:all')
        return self._node(job['id'], 'citation-check', lambda: validate_sections(sections, outline, evidence))

    def process_one(self):
        self.recover()
        with self.connect(True) as c:
            r = c.execute("SELECT id FROM jobs WHERE status='queued' ORDER BY created LIMIT 1").fetchone()
            if not r:
                return False
            id = r['id']
            c.execute("UPDATE jobs SET status='running',owner=?,heartbeat=?,updated=? WHERE id=?", (self.owner, time.time(), now(), id))
        done = threading.Event()

        def beat():
            while not done.wait(1):
                with self.connect(True) as c:
                    c.execute('UPDATE jobs SET heartbeat=? WHERE id=? AND owner=?', (time.time(), id, self.owner))
        heartbeat = threading.Thread(target=beat, daemon=True)
        heartbeat.start()
        job = self.job(id)
        try:
            if job['kind'] == 'import':
                data = job['payload']
                with self.connect() as c:
                    r = c.execute('SELECT raw,filename FROM paper_versions WHERE paper=? AND number=?', (data['paper'], data['version'])).fetchone()
                pages = self._node(id, 'parse', lambda: pages_from(r['raw'], r['filename']))
                result = {'paper_id': data['paper'], 'version': data['version']}
            else:
                ctx = job['context']
                if job['mode'] != 'offline' and job['model_fp'] != model_fp():
                    raise WorkspaceError('模型配置已变化，请新建任务。', 409)
                output = self._read(job, ctx) if job['kind'] == 'read' else self._write(job, ctx)
                result = {}
            with self.connect(True) as c:
                if self.cancelled(id):
                    raise InterruptedError('任务已取消。')
                if job['kind'] == 'import':
                    p = self.required(c, 'papers', data['paper'])
                    if not p['active']:
                        raise WorkspaceError('文献已删除，不恢复为有效资料。', 409)
                    c.execute("UPDATE paper_versions SET status='ready',pages=?,error='' WHERE paper=? AND number=?", (dump(pages), data['paper'], data['version']))
                    c.execute('UPDATE papers SET current=? WHERE id=?', (data['version'], data['paper']))
                else:
                    if self.context(job['project'], c)['fingerprint'] != ctx['fingerprint']:
                        raise WorkspaceError('专题输入已变化，结果未提交；请按当前版本重新运行。', 409)
                    if job['kind'] == 'read':
                        if len(ctx['evidence']) + len(output) > 60:
                            raise WorkspaceError('证据数量超出60条，请先整理矩阵。')
                        ids = []
                        for row in output:
                            e = uid('ev')
                            body = {k: row[k] for k in ('field', 'page', 'start', 'end', 'quote', 'summary')}
                            c.execute("INSERT INTO evidence VALUES(?,?,?,?,1,?,'pending','','',?,?)", (e, job['project'], row['paper'], row['version'], dump(body), now(), now()))
                            ids.append(e)
                        result = {'evidence_ids': ids}
                    else:
                        d = uid('draft')
                        c.execute('INSERT INTO drafts VALUES(?,?,1,?,NULL,0,?)', (d, job['project'], dump(ctx), now()))
                        c.execute('INSERT INTO draft_versions VALUES(?,1,?,?)', (d, dump(output), now()))
                        result = {'draft_id': d}
                c.execute("UPDATE jobs SET status='succeeded',result=?,updated=? WHERE id=?", (dump(result), now(), id))
        except Exception as error:
            message = str(error) if isinstance(error, (WorkspaceError, ValueError, InterruptedError)) else '执行失败，请查看服务端日志。'
            if not isinstance(error, (WorkspaceError, ValueError, InterruptedError)):
                import traceback
                traceback.print_exc()
            with self.connect(True) as c:
                status = 'cancelled' if isinstance(error, InterruptedError) else 'failed'
                if self.stop.is_set():
                    status = 'interrupted'
                c.execute('UPDATE jobs SET status=?,error=?,updated=? WHERE id=? AND owner=?', (status, message, now(), id, self.owner))
                if job['kind'] == 'import':
                    c.execute("UPDATE paper_versions SET status='failed',error=? WHERE paper=? AND number=?", (message, job['payload']['paper'], job['payload']['version']))
        finally:
            done.set()
            heartbeat.join(2)
        return True

    def loop(self):
        while not self.stop.is_set():
            if not self.process_one():
                self.wake.wait(0.4)
                self.wake.clear()

    def draft(self, id, version=None, c=None):
        if c is None:
            with self.connect() as connection:
                return self.draft(id, version, connection)
        d = dict(self.required(c, 'drafts', id))
        number = int(version) if version is not None else d['current']
        r = c.execute('SELECT * FROM draft_versions WHERE draft=? AND number=?', (id, number)).fetchone()
        if not r:
            raise WorkspaceError('草案版本不存在。', 404)
        d['context'] = json.loads(d['context'])
        d['draft'] = json.loads(d['draft']) if d['draft'] else None
        d['version'] = number
        d['sections'] = json.loads(r['sections'])
        d['stale'] = self.context(d['project'], c)['fingerprint'] != d['context']['fingerprint']
        d['reviews'] = [dict(r) for r in c.execute('SELECT * FROM reviews WHERE draft=? AND version=? ORDER BY rowid', (id, number))]
        d['versions'] = [dict(r) for r in c.execute('SELECT number,created FROM draft_versions WHERE draft=? ORDER BY number DESC', (id,))]
        return d

    def save_draft(self, id, value):
        with self.connect(True) as c:
            d = self.draft(id, c=c)
            if value.get('base_version') != d['current'] or value.get('draft_revision') != d['draft_revision']:
                raise WorkspaceError('草案已在其他页面修改，请刷新并保留本地文本后合并。', 409)
            if d['stale']:
                raise WorkspaceError('证据或专题已变化，请重新生成草案。', 409)
            sections = validate_sections(value.get('sections'), d['context']['project']['outline'], d['context']['evidence'])
            revision = d['draft_revision'] + 1
            c.execute('UPDATE drafts SET draft=?,draft_revision=? WHERE id=?', (dump(sections), revision, id))
        return {'draft_revision': revision}

    def commit(self, id, value):
        with self.connect(True) as c:
            d = self.draft(id, c=c)
            if value.get('base_version') != d['current'] or value.get('draft_revision') != d['draft_revision'] or (not d['draft']) or d['stale']:
                raise WorkspaceError('没有可提交的当前草稿，或版本/证据已变化。', 409)
            number = d['current'] + 1
            c.execute('INSERT INTO draft_versions VALUES(?,?,?,?)', (id, number, dump(d['draft']), now()))
            c.execute('UPDATE drafts SET current=?,draft=NULL,draft_revision=0 WHERE id=?', (number, id))
        return {'version': number}

    def review_draft(self, id, value):
        actor = text(value.get('actor'), '核对人', 80)
        comment = text(value.get('comment'), '核对依据', 2000)
        ids = value.get('claim_ids')
        decision = value.get('decision', 'approved')
        with self.connect(True) as c:
            d = self.draft(id, c=c)
            valid = {r['id'] for s in d['sections'] for r in s['claims']}
            if d['draft'] or d['stale'] or value.get('version') != d['current']:
                raise WorkspaceError('草案未提交、来源已变化或版本不是当前版本，不能审核。', 409)
            if not isinstance(ids, list) or not ids or len(ids) != len(set(ids)) or any((i not in valid for i in ids)) or (value.get('confirmed_count') != len(ids)) or (decision not in ('approved', 'rejected')):
                raise WorkspaceError('请明确选择本版本论述并核对数量。')
            for claim in ids:
                c.execute('INSERT INTO reviews VALUES(?,?,?,?,?,?,?,?)', (uid('check'), id, d['current'], claim, decision, actor, comment, now()))
        return {'count': len(ids)}

    def publish(self, id, value):
        actor = text(value.get('actor'), '发布记录人', 80)
        with self.connect(True) as c:
            d = self.draft(id, c=c)
            claims = [r for s in d['sections'] for r in s['claims']]
            last = {r['claim']: r['decision'] for r in d['reviews']}
            if d['draft'] or d['stale'] or value.get('version') != d['current'] or any((last.get(r['id']) != 'approved' for r in claims)):
                raise WorkspaceError('发布需当前来源、无未提交草稿且全部论述已核对通过。', 409)
            id = uid('release')
            bundle = {'schema': 'd13-release-v1', 'draft_id': d['id'], 'version': d['version'], 'sections': d['sections'], 'context': d['context'], 'reviews': d['reviews'], 'actor': actor, 'created': now(), 'boundary': '逐字定位不证明语义支持；核对记录不提供身份认证。'}
            c.execute('INSERT INTO releases VALUES(?,?,?,?,?)', (id, d['id'], d['version'], dump(bundle), now()))
        return {'release_id': id}

    def export(self, id, fmt='markdown', release=False, version=None):
        with self.connect() as c:
            if release:
                bundle = json.loads(self.required(c, 'releases', id)['bundle'])
            else:
                d = self.draft(id, version, c)
                bundle = {'schema': 'd13-draft-v1', 'draft_id': id, 'version': d['version'], 'sections': d['sections'], 'context': d['context'], 'reviews': d['reviews'], 'stale': d['stale'], 'boundary': '未发布草案；导出不包含未提交的自动草稿。逐字定位不证明语义支持。'}
        if fmt == 'json':
            return (dump(bundle).encode(), 'application/json; charset=utf-8', id + '.json')
        papers = {p['id']: p for p in bundle['context']['papers']}
        evidence = {e['id']: e for e in bundle['context']['evidence']}
        used = []
        for section in bundle['sections']:
            for claim in section['claims']:
                for e in claim['evidence_ids']:
                    pid = evidence[e]['paper']
                    if pid not in used:
                        used.append(pid)
        esc = lambda s: str(s or '').replace('<', '&lt;').replace('>', '&gt;')
        if fmt == 'markdown':
            out = ['# ' + esc(bundle['context']['project']['title']), bundle['boundary'], '研究问题：' + esc(bundle['context']['project']['question'])]
            for section in bundle['sections']:
                out += ['\n## ' + esc(section['title'])]
                for claim in section['claims']:
                    out += [esc(claim['text']) + ' ' + ''.join(('[' + str(used.index(evidence[e]['paper']) + 1) + ']' for e in {evidence[e]['paper']: e for e in claim['evidence_ids']}.values()))]
            out += ['\n## 参考文献']
            for i, pid in enumerate(used, 1):
                m = papers[pid]['metadata']
                out += [f"[{i}] {esc(m['authors'])}. {esc(m['title'])}. {m['year'] or '年份待补'}. {esc(m['doi'] or m['url'])} （输入范围：{m['scope']}）"]
            out += ['\n## 证据位置']
            for eid, e in evidence.items():
                if e['paper'] in used:
                    out += [f"- {eid} · [{used.index(e['paper']) + 1}] v{e['version']} p.{e['page']} 字符{e['start']}–{e['end']}：{esc(e['quote'])}"]
            return ('\n\n'.join(out).encode(), 'text/markdown; charset=utf-8', id + '.md')
        if fmt == 'bibtex':
            clean = lambda s: re.sub('[{}\\\\\\r\\n]', ' ', str(s or '')).strip()
            items = []
            for pid in used:
                m = papers[pid]['metadata']
                fields = {k: clean(m[k]) for k in ('title', 'authors', 'year', 'doi', 'url') if m.get(k)}
                fields['author'] = fields.pop('authors', '')
                fields['note'] = 'Imported scope: ' + m['scope']
                items.append('@misc{' + pid.replace('-', '') + ',\n' + ',\n'.join(('  ' + k + ' = {' + v + '}' for k, v in fields.items())) + '\n}')
            return ('\n\n'.join(items).encode(), 'application/x-bibtex; charset=utf-8', id + '.bib')
        raise WorkspaceError('仅支持 Markdown、BibTeX 或 JSON。')

    def delete_evidence(self, id, value):
        with self.connect(True) as c:
            row = self.required(c, 'evidence', id)
            if value.get('revision') != row['revision']:
                raise WorkspaceError('证据已变化，请刷新。', 409)
            c.execute('DELETE FROM evidence WHERE id=?', (id,))
        return {'deleted': True}

    def discard_draft(self, id, value):
        with self.connect(True) as c:
            d = self.draft(id, c=c)
            if value.get('base_version') != d['current'] or value.get('draft_revision') != d['draft_revision']:
                raise WorkspaceError('草稿版本已变化，请刷新。', 409)
            c.execute('UPDATE drafts SET draft=NULL,draft_revision=draft_revision+1 WHERE id=?', (id,))
        return {'discarded': True}

    def raw_paper(self, id, version=None):
        with self.connect() as c:
            p = self.paper(id, version, c)
            r = c.execute('SELECT raw FROM paper_versions WHERE paper=? AND number=?', (id, p['version']['number'])).fetchone()
        return (r[0], 'application/pdf' if p['version']['filename'].lower().endswith('.pdf') else 'text/plain; charset=utf-8', id + '-v' + str(p['version']['number']) + Path(p['version']['filename']).suffix.lower())
_singleton = None
_singleton_lock = threading.Lock()

def get_literature_workspace():
    global _singleton
    with _singleton_lock:
        if _singleton is None:
            _singleton = LiteratureWorkspace(os.environ.get('LAB_DATA_DIR', str(ROOT / 'data')))
        return _singleton
