"""D02 single-instance data, trusted linear artifacts, deployment and explicit windows."""
import base64, csv, hashlib, io, json, math, os, re, signal, sqlite3, subprocess, sys, threading, time, uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from shared.process_workspace import WorkspaceError
ROOT = Path(__file__).resolve().parents[1]
FINAL = ('succeeded', 'failed', 'cancelled', 'interrupted')

def now():
    return datetime.now(timezone.utc).isoformat()

def uid(prefix):
    return prefix + '-' + uuid.uuid4().hex[:16]

def dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)

def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode() if isinstance(value, str) else dump(value).encode()).hexdigest()

def text(value, label, limit=200, empty=False):
    if not isinstance(value, str) or len(value) > limit or (not empty and (not value.strip())):
        raise WorkspaceError(f'{label}应为{(0 if empty else 1)}–{limit}字。')
    return value.strip()

def number(value, label, minimum, maximum):
    if isinstance(value, bool):
        raise WorkspaceError(label + '必须为数值。')
    try:
        v = float(value)
    except (ValueError, TypeError):
        raise WorkspaceError(label + '必须为数值。') from None
    if not math.isfinite(v) or not minimum <= v <= maximum:
        raise WorkspaceError(f'{label}应在{minimum}–{maximum}之间。')
    return v

def parse_csv(raw, kind, label):
    if not 0 < len(raw) <= 4 * 1024 * 1024:
        raise WorkspaceError('CSV 文件应为1字节–4 MiB。')
    try:
        source = raw.decode('utf-8-sig')
    except UnicodeError:
        raise WorkspaceError('CSV 必须使用 UTF-8 编码。') from None
    if '\x00' in source:
        raise WorkspaceError('CSV 含无效空字符。')
    try:
        all_rows = list(csv.reader(io.StringIO(source), strict=True))
    except csv.Error:
        raise WorkspaceError('CSV 格式无法解析。') from None
    if not all_rows:
        raise WorkspaceError('CSV 没有表头。')
    headers = [x.strip() for x in all_rows[0]]
    if len(headers) != len(set(headers)) or any((not re.fullmatch('[\\w\\u4e00-\\u9fff][\\w\\u4e00-\\u9fff .-]{0,39}', x) for x in headers)):
        raise WorkspaceError('列名应唯一，为1–40字的字母、数字、汉字、空格或 _.-，首位不得为空格。')
    if label and label not in headers:
        raise WorkspaceError('标签列不存在。')
    features = [h for h in headers if h != label]
    if not 1 <= len(features) <= 12:
        raise WorkspaceError('支持1–12个数值特征。')
    rows = []
    labels = []
    errors = []
    missing = invalid = bad_labels = 0
    for line, cells in enumerate(all_rows[1:], 2):
        if not cells or not any((c.strip() for c in cells)):
            continue
        if len(cells) != len(headers):
            raise WorkspaceError(f'第{line}行列数与表头不一致。')
        source = dict(zip(headers, cells))
        row = {}
        issue = []
        for feature in features:
            val = source[feature].strip()
            if not val:
                row[feature] = None
                missing += 1
                issue.append(feature + '缺失')
                continue
            try:
                n = float(val)
            except ValueError:
                n = float('nan')
            if not math.isfinite(n) or abs(n) > 1000000:
                row[feature] = None
                invalid += 1
                issue.append(feature + '无效')
            else:
                row[feature] = n
        label_value = source[label].strip() if label else ''
        y = int(label_value) if label_value in ('0', '1') else None
        if label_value and y is None:
            bad_labels += 1
            issue.append('标签无效')
        rows.append(row)
        labels.append(y)
        errors.append(issue)
        if len(rows) > 10000:
            raise WorkspaceError('最多10000行。')
    if not rows:
        raise WorkspaceError('没有有效数据行。')
    duplicates = len(rows) - len({dump(r) for r in rows})
    quality = {'missing_values': missing, 'invalid_values': invalid, 'invalid_labels': bad_labels, 'invalid_feature_rows': sum((any((v is None for v in r.values())) for r in rows)), 'duplicate_feature_rows': duplicates, 'labeled_rows': sum((y is not None for y in labels))}
    if kind == 'training':
        if not label or missing or invalid or bad_labels or (None in labels):
            raise WorkspaceError('训练数据要求全部数值特征有效、标签完整且为0/1；监控数据可保留缺失用于质量检查。')
        if len(rows) < 40 or min(labels.count(0), labels.count(1)) < 4:
            raise WorkspaceError('训练至少40行，且每类至少4行。')
    return {'features': features, 'label': label, 'rows': rows, 'labels': labels, 'errors': errors, 'quality': quality}

def validate_artifact(value):
    if not isinstance(value, dict) or value.get('schema') != 'lab-linear-v1':
        raise WorkspaceError('模型制品 schema 不受支持。')
    features = value.get('features')
    n = len(features) if isinstance(features, list) else 0
    if not 1 <= n <= 12 or len(set(features)) != n or any((not isinstance(f, str) for f in features)):
        raise WorkspaceError('模型特征 schema 无效。')
    for key in ('mean', 'scale', 'coefficient'):
        v = value.get(key)
        if not isinstance(v, list) or len(v) != n or any((type(x) not in (int, float) or not math.isfinite(x) or abs(x) > 1000000000.0 for x in v)):
            raise WorkspaceError('模型数值参数无效。')
    if any((v <= 0 for v in value['scale'])) or value.get('classes') != [0, 1] or value.get('threshold') != 0.5:
        raise WorkspaceError('模型尺度、类别或阈值无效。')
    number(value.get('intercept'), '模型截距', -1000000000.0, 1000000000.0)
    reference = value.get('reference')
    if not isinstance(reference, list) or len(reference) != n:
        raise WorkspaceError('模型参考分布无效。')
    for r in reference:
        if not isinstance(r, dict) or not isinstance(r.get('edges'), list) or len(r['edges']) > 9 or any((type(x) not in (int, float) or not math.isfinite(x) for x in r['edges'])) or (r['edges'] != sorted(set(r['edges']))):
            raise WorkspaceError('模型分箱无效。')
        counts = r.get('counts')
        if not isinstance(counts, list) or len(counts) != len(r['edges']) + 1 or any((type(x) is not int or x < 0 for x in counts)) or (sum(counts) == 0):
            raise WorkspaceError('模型分布计数无效。')
    return value

def infer(artifact, rows):
    if not isinstance(rows, list) or not 1 <= len(rows) <= 10000:
        raise WorkspaceError('请提供1–10000行数据。')
    features = artifact['features']
    x = []
    for row in rows:
        if not isinstance(row, dict) or set(row) != set(features):
            raise WorkspaceError('请求特征名需与加载模型完全一致。')
        x.append([number(row[f], f, -1000000, 1000000) for f in features])
    matrix = np.asarray(x, dtype=float)
    z = (matrix - np.asarray(artifact['mean'])) / np.asarray(artifact['scale']) @ np.asarray(artifact['coefficient']) + float(artifact['intercept'])
    prob = 1 / (1 + np.exp(-np.clip(z, -500, 500)))
    return [{'prediction': int(p >= 0.5), 'probability': float(p)} for p in prob]

def sample_csv(profile='training', n=600, seed=42):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(n, 4))
    x[:, 0] += 2.5 if profile == 'feature_shift' else 0
    y = (x[:, 0] + 0.8 * x[:, 1] - 0.6 * x[:, 2] + rng.normal(0, 0.25, n) > 0).astype(int)
    if profile == 'label_shift':
        y = 1 - y
    if profile == 'noisy_training':
        y = np.where(rng.random(n) < 0.15, 1 - y, y)
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(['feature_1', 'feature_2', 'feature_3', 'feature_4'] + ([] if profile == 'missing_labels' else ['label']))
    for i, (row, label) in enumerate(zip(x, y)):
        cells = [format(float(v), '.8g') for v in row]
        if profile == 'missing_values' and i % 5 == 0:
            cells[0] = ''
        w.writerow(cells + ([] if profile == 'missing_labels' else [int(label)]))
    return out.getvalue().encode()

class MlopsWorkspace:

    def __init__(self, directory, start_worker=True):
        self.db = Path(directory) / 'mlops.sqlite3'
        self.db.parent.mkdir(parents=True, exist_ok=True)
        self.stop = threading.Event()
        self.wake = threading.Event()
        self.owner = uid('worker')
        self.thread = None
        with self.connect() as c:
            c.executescript('PRAGMA journal_mode=WAL;\n        CREATE TABLE IF NOT EXISTS datasets(id TEXT PRIMARY KEY,parent TEXT,title TEXT,kind TEXT,origin TEXT,filename TEXT,sha TEXT,raw BLOB,data TEXT,active INTEGER,created TEXT);\n        CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,kind TEXT,status TEXT,payload TEXT,result TEXT,error TEXT,owner TEXT,heartbeat REAL,cancel INTEGER DEFAULT 0,created TEXT,updated TEXT);\n        CREATE TABLE IF NOT EXISTS experiments(id TEXT PRIMARY KEY,job TEXT,dataset TEXT,parameters TEXT,metrics TEXT,split TEXT,policy TEXT,gate INTEGER,model TEXT,duration_ms REAL,created TEXT);\n        CREATE TABLE IF NOT EXISTS models(id TEXT PRIMARY KEY,experiment TEXT,artifact TEXT,sha TEXT,review_revision INTEGER DEFAULT 0,created TEXT);\n        CREATE TABLE IF NOT EXISTS reviews(id TEXT PRIMARY KEY,model TEXT,revision INTEGER,decision TEXT,actor TEXT,comment TEXT,sha TEXT,created TEXT);\n        CREATE TABLE IF NOT EXISTS deployment(id INTEGER PRIMARY KEY CHECK(id=1),revision INTEGER,model TEXT,previous TEXT,updated TEXT);\n        INSERT OR IGNORE INTO deployment VALUES(1,0,NULL,NULL,NULL);\n        CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY,job TEXT,action TEXT,status TEXT,target TEXT,loaded TEXT,revision INTEGER,actor TEXT,comment TEXT,error TEXT,duration_ms REAL,created TEXT);\n        CREATE TABLE IF NOT EXISTS requests(id TEXT PRIMARY KEY,model TEXT,revision INTEGER,status TEXT,rows INTEGER,duration_ms REAL,samples TEXT,error TEXT,created TEXT);\n        CREATE TABLE IF NOT EXISTS counters(name TEXT PRIMARY KEY,value REAL);\n        CREATE TABLE IF NOT EXISTS windows(id TEXT PRIMARY KEY,job TEXT,dataset TEXT,model TEXT,baseline TEXT,revision INTEGER,policy TEXT,report TEXT,created TEXT);\n        CREATE TABLE IF NOT EXISTS alerts(id TEXT PRIMARY KEY,window TEXT,kind TEXT,severity TEXT,status TEXT,revision INTEGER,summary TEXT,created TEXT);\n        CREATE TABLE IF NOT EXISTS alert_actions(id TEXT PRIMARY KEY,alert TEXT,revision INTEGER,status TEXT,actor TEXT,comment TEXT,created TEXT);\n        CREATE TABLE IF NOT EXISTS tracking(experiment TEXT PRIMARY KEY,remote_run TEXT,url TEXT,status TEXT,error TEXT,updated TEXT);\n        CREATE INDEX IF NOT EXISTS queue_mlops ON jobs(status,created);')
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
        if table not in ('datasets', 'jobs', 'experiments', 'models', 'windows', 'alerts'):
            raise ValueError('Invalid table')
        r = c.execute('SELECT * FROM ' + table + ' WHERE id=?', (id,)).fetchone()
        if not r:
            raise WorkspaceError('记录不存在。', 404)
        return r

    def dataset(self, id, c=None):
        if c is None:
            with self.connect() as connection:
                return self.dataset(id, connection)
        d = dict(self.required(c, 'datasets', id))
        d.pop('raw')
        d['data'] = json.loads(d['data'])
        return d

    def import_dataset(self, value):
        kind = value.get('kind', 'training')
        if kind not in ('training', 'monitoring'):
            raise WorkspaceError('数据用途应为训练或监控。')
        try:
            raw = base64.b64decode(value['content_base64'], validate=True) if 'content_base64' in value else text(value.get('text'), 'CSV 文本', 4 * 1024 * 1024).encode()
        except (ValueError, TypeError):
            raise WorkspaceError('文件编码无效。') from None
        label = text(value.get('label', 'label'), '标签列', 40, True)
        data = parse_csv(raw, kind, label)
        title = text(value.get('title'), '数据名称', 120)
        filename = text(value.get('filename', 'pasted.csv'), '文件名', 160).replace('\\', '/').split('/')[-1]
        if not filename.lower().endswith('.csv'):
            raise WorkspaceError('只接受 UTF-8 CSV 文件。')
        parent = value.get('parent')
        hash = digest(raw)
        with self.connect(True) as c:
            if parent:
                self.required(c, 'datasets', parent)
            old = c.execute("SELECT id FROM datasets WHERE active=1 AND sha=? AND kind=? AND json_extract(data,'$.label')=?", (hash, kind, label)).fetchone()
            if old:
                return {'dataset_id': old['id'], 'deduplicated': True}
            if c.execute('SELECT count(*) FROM datasets WHERE active=1').fetchone()[0] >= 100:
                raise WorkspaceError('最多100份有效数据快照。')
            if c.execute('SELECT coalesce(sum(length(raw)),0) FROM datasets').fetchone()[0] + len(raw) > 128 * 1024 * 1024:
                raise WorkspaceError('原始数据已达128 MiB，请先备份整理。')
            id = uid('data')
            c.execute('INSERT INTO datasets VALUES(?,?,?,?,?,?,?,?,?,1,?)', (id, parent, title, kind, 'uploaded', filename, hash, raw, dump(data), now()))
        return {'dataset_id': id, 'deduplicated': False}

    def sample_file(self, profile):
        if profile not in ('training', 'noisy_training', 'clean', 'feature_shift', 'label_shift', 'missing_labels', 'missing_values'):
            raise WorkspaceError('未知教学方案。')
        return sample_csv(profile, seed=42 if profile.endswith('training') else 84)

    def create_sample(self, value):
        profile = value.get('profile', 'training')
        if profile not in ('training', 'noisy_training', 'clean', 'feature_shift', 'label_shift', 'missing_labels', 'missing_values'):
            raise WorkspaceError('未知教学数据方案。')
        seed = int(number(value.get('seed', 42 if profile.endswith('training') else 84), '种子', 0, 100000))
        raw = sample_csv(profile, seed=seed)
        r = self.import_dataset({'title': '合成教学数据 · ' + profile, 'kind': 'training' if profile.endswith('training') else 'monitoring', 'label': '' if profile == 'missing_labels' else 'label', 'filename': profile + '.csv', 'content_base64': base64.b64encode(raw).decode()})
        if not r['deduplicated']:
            with self.connect(True) as c:
                c.execute("UPDATE datasets SET origin='synthetic' WHERE id=?", (r['dataset_id'],))
        return r

    def archive(self, id):
        with self.connect(True) as c:
            self.required(c, 'datasets', id)
            c.execute('UPDATE datasets SET active=0 WHERE id=?', (id,))
        return {'archived': True}

    def experiment(self, id, c=None):
        if c is None:
            with self.connect() as connection:
                return self.experiment(id, connection)
        e = dict(self.required(c, 'experiments', id))
        for key in ('parameters', 'metrics', 'split', 'policy'):
            e[key] = json.loads(e[key])
        row = c.execute('SELECT * FROM tracking WHERE experiment=?', (id,)).fetchone()
        e['tracking'] = dict(row) if row else None
        return e

    def model(self, id, c=None):
        if c is None:
            with self.connect() as connection:
                return self.model(id, connection)
        m = dict(self.required(c, 'models', id))
        try:
            m['artifact'] = validate_artifact(json.loads(m['artifact']))
        except (ValueError, TypeError, KeyError):
            m['artifact'] = {}
        m['experiment'] = self.experiment(m['experiment'], c)
        m['reviews'] = [dict(r) for r in c.execute('SELECT * FROM reviews WHERE model=? ORDER BY revision', (id,))]
        m['decision'] = m['reviews'][-1]['decision'] if m['reviews'] and m['reviews'][-1]['sha'] == m['sha'] else 'pending'
        return m

    def _load(self, id, c):
        row = self.required(c, 'models', id)
        if digest(row['artifact']) != row['sha']:
            raise WorkspaceError('模型制品哈希不一致；未加载。', 409)
        try:
            a = validate_artifact(json.loads(row['artifact']))
        except (ValueError, TypeError, KeyError):
            raise WorkspaceError('模型制品结构损坏；未加载。', 409) from None
        infer(a, [dict(zip(a['features'], a['mean']))])
        return (a, row['sha'])

    def head(self, c):
        return dict(c.execute('SELECT * FROM deployment WHERE id=1').fetchone())

    def health(self):
        with self.connect() as c:
            d = self.head(c)
            pending = c.execute("SELECT id,payload,status FROM jobs WHERE kind='deploy' AND status IN ('queued','running') ORDER BY created DESC LIMIT 1").fetchone()
            d['target'] = json.loads(pending['payload'])['model'] if pending else d['model']
            d['pending_job'] = pending['id'] if pending else None
            if not d['model']:
                return {**d, 'ready': False, 'features': [], 'message': '尚未发布模型。'}
            try:
                a, sha = self._load(d['model'], c)
                return {**d, 'ready': True, 'features': a['features'], 'sha': sha, 'message': '当前制品已校验，可接受预测。'}
            except WorkspaceError as e:
                return {**d, 'ready': False, 'features': [], 'message': str(e)}

    def state(self):
        self.recover()
        with self.connect() as c:
            datasets = []
            for r in c.execute('SELECT id FROM datasets WHERE active=1 ORDER BY created DESC'):
                d = self.dataset(r['id'], c)
                datasets.append({k: d[k] for k in ('id', 'parent', 'title', 'kind', 'origin', 'filename', 'sha', 'created')} | {'rows': len(d['data']['rows']), 'features': d['data']['features'], 'label': d['data']['label'], 'quality': d['data']['quality']})
            experiments = [{k: e[k] for k in ('id', 'dataset', 'parameters', 'metrics', 'policy', 'gate', 'model', 'duration_ms', 'created')} for e in (self.experiment(r['id'], c) for r in c.execute('SELECT id FROM experiments ORDER BY created DESC'))]
            models = []
            for r in c.execute('SELECT id FROM models ORDER BY created DESC'):
                m = self.model(r['id'], c)
                models.append({'id': m['id'], 'experiment': m['experiment']['id'], 'dataset': m['experiment']['dataset'], 'sha': m['sha'], 'features': m['artifact'].get('features', []), 'decision': m['decision'], 'review_revision': m['review_revision'], 'gate': bool(m['experiment']['gate']), 'created': m['created']})
            jobs = [{k: r[k] for k in ('id', 'kind', 'status', 'error', 'created', 'updated')} for r in c.execute('SELECT * FROM jobs ORDER BY created DESC LIMIT 100')]
            events = [dict(r) for r in c.execute('SELECT * FROM events ORDER BY created DESC LIMIT 100')]
            windows = [{'id': r['id'], 'model': r['model'], 'dataset': r['dataset'], 'revision': r['revision'], 'created': r['created'], 'report': json.loads(r['report'])} for r in c.execute('SELECT * FROM windows ORDER BY created DESC LIMIT 100')]
            alerts = [dict(r) for r in c.execute('SELECT * FROM alerts ORDER BY created DESC LIMIT 200')]
            requests = [{**dict(r), 'samples': json.loads(r['samples'])} for r in c.execute('SELECT * FROM requests ORDER BY created DESC LIMIT 30')]
            counters = {r['name']: r['value'] for r in c.execute('SELECT * FROM counters')}
        return {'schema': 1, 'datasets': datasets, 'experiments': experiments, 'models': models, 'jobs': jobs, 'events': events, 'windows': windows, 'alerts': alerts, 'requests': requests, 'counters': counters, 'service': self.health(), 'capabilities': {'mlflow': bool(os.environ.get('LAB_MLFLOW_URL')), 'runtime': 'trusted-linear-json'}}

    def _queue(self, c, kind, payload):
        same = c.execute("SELECT id FROM jobs WHERE kind=? AND payload=? AND status IN ('queued','running')", (kind, dump(payload))).fetchone()
        if same:
            return same['id']
        if c.execute("SELECT count(*) FROM jobs WHERE status IN ('queued','running')").fetchone()[0] >= 20:
            raise WorkspaceError('等待任务已达20项。', 409)
        id = uid('job')
        stamp = now()
        c.execute("INSERT INTO jobs VALUES(?,?,'queued',?,'{}','',NULL,NULL,0,?,?)", (id, kind, dump(payload), stamp, stamp))
        return id

    def train(self, value):
        dataset = value.get('dataset')
        p = {'seed': int(number(value.get('seed', 42), '随机种子', 0, 100000)), 'c': number(value.get('c', 1), '正则参数 C', 0.01, 100), 'name': text(value.get('name', '二分类训练实验'), '实验名称', 100)}
        policy = {'min_accuracy': number(value.get('min_accuracy', 0.7), '最低验证准确率', 0.5, 1), 'max_log_loss': number(value.get('max_log_loss', 0.8), '最高 Log Loss', 0.01, 5)}
        with self.connect(True) as c:
            d = self.dataset(dataset, c)
            if not d['active'] or d['kind'] != 'training':
                raise WorkspaceError('请选择有效训练数据。', 409)
            id = self._queue(c, 'train', {'dataset': dataset, 'sha': d['sha'], 'parameters': p, 'policy': policy})
        self.wake.set()
        return {'job_id': id}

    def review_model(self, id, value):
        actor = text(value.get('actor'), '审核人', 80)
        comment = text(value.get('comment'), '审核依据', 2000)
        decision = value.get('decision')
        if decision not in ('approved', 'rejected'):
            raise WorkspaceError('审核结论无效。')
        with self.connect(True) as c:
            m = self.model(id, c)
            if value.get('revision') != m['review_revision'] or value.get('sha') != m['sha']:
                raise WorkspaceError('模型审核状态已变化，请刷新。', 409)
            if decision == 'approved':
                self._load(id, c)
                if not m['experiment']['gate']:
                    raise WorkspaceError('该模型未通过训练时固定的质量门禁，不能批准。', 409)
            revision = m['review_revision'] + 1
            c.execute('UPDATE models SET review_revision=? WHERE id=?', (revision, id))
            c.execute('INSERT INTO reviews VALUES(?,?,?,?,?,?,?,?)', (uid('review'), id, revision, decision, actor, comment, m['sha'], now()))
        return {'revision': revision}

    def deploy(self, value):
        actor = text(value.get('actor'), '操作人', 80)
        comment = text(value.get('comment'), '发布说明', 2000)
        rollback = value.get('rollback') is True
        with self.connect(True) as c:
            d = self.head(c)
            m = self.model(value.get('model'), c)
            if value.get('revision') != d['revision']:
                raise WorkspaceError('活动版本已变化，请刷新后重新确认。', 409)
            if m['id'] == d['model']:
                raise WorkspaceError('该版本已在服务中。', 409)
            if m['decision'] != 'approved' or not m['experiment']['gate']:
                raise WorkspaceError('模型需通过质量门禁及人工审核。', 409)
            if rollback and (not c.execute("SELECT 1 FROM events WHERE target=? AND status='succeeded'", (m['id'],)).fetchone()):
                raise WorkspaceError('回滚只能选择曾成功加载的历史模型。', 409)
            payload = {'model': m['id'], 'sha': m['sha'], 'review_revision': m['review_revision'], 'revision': d['revision'], 'actor': actor, 'comment': comment, 'rollback': rollback}
            id = self._queue(c, 'deploy', payload)
        self.wake.set()
        return {'job_id': id}

    def job(self, id):
        with self.connect() as c:
            r = dict(self.required(c, 'jobs', id))
            r['payload'] = json.loads(r['payload'])
            r['result'] = json.loads(r['result'])
            r.pop('owner')
            r.pop('heartbeat')
            return r

    def job_action(self, id, action):
        with self.connect(True) as c:
            j = self.required(c, 'jobs', id)
            if action == 'cancel':
                if j['status'] not in FINAL:
                    c.execute("UPDATE jobs SET cancel=1,status=CASE WHEN status='queued' THEN 'cancelled' ELSE status END,updated=? WHERE id=?", (now(), id))
                return {'job_id': id}
            if action != 'retry' or j['status'] not in ('failed', 'interrupted', 'cancelled'):
                raise WorkspaceError('只能显式重试失败、中断或取消的任务。', 409)
            p = json.loads(j['payload'])
            if j['kind'] == 'deploy' and p['revision'] != self.head(c)['revision']:
                raise WorkspaceError('活动版本已变化，请创建新的发布任务。', 409)
            new = self._queue(c, j['kind'], p)
        self.wake.set()
        return {'job_id': new}

    def recover(self):
        with self.connect(True) as c:
            c.execute("UPDATE jobs SET status='interrupted',error='任务心跳中断，可显式重试。',updated=? WHERE status='running' AND heartbeat<?", (now(), time.time() - 20))

    def cancelled(self, id, c=None):
        if c is None:
            with self.connect() as connection:
                return self.cancelled(id, connection)
        j = self.required(c, 'jobs', id)
        return self.stop.is_set() or j['cancel'] or j['status'] != 'running' or (j['owner'] != self.owner)

    def _counter(self, c, name, value=1):
        c.execute('INSERT INTO counters VALUES(?,?) ON CONFLICT(name) DO UPDATE SET value=value+excluded.value', (name, value))

    def predict(self, value):
        start = time.perf_counter()
        model = None
        revision = None
        try:
            with self.connect() as c:
                d = self.head(c)
                model = d['model']
                revision = d['revision']
                if not model:
                    raise WorkspaceError('尚未发布模型。', 503)
                a, sha = self._load(model, c)
            rows = value.get('rows')
            if not isinstance(rows, list) or not 1 <= len(rows) <= 1000:
                raise WorkspaceError('实时预测支持1–1000行，请按特征名提供对象。')
            output = infer(a, rows)
            duration = (time.perf_counter() - start) * 1000
            result = {'model_id': model, 'deployment_revision': revision, 'artifact_sha': sha, 'features': a['features'], 'predictions': output, 'rows': len(output), 'duration_ms': duration, 'timing_scope': 'model loading, input validation and inference; excludes audit write'}
            message = ''
            status = 'succeeded'
        except WorkspaceError as e:
            message = str(e)
            status = 'failed'
            error = e
            output = []
            duration = (time.perf_counter() - start) * 1000
        with self.connect(True) as c:
            id = uid('request')
            c.execute('INSERT INTO requests VALUES(?,?,?,?,?,?,?,?,?)', (id, model, revision, status, len(output), duration, dump(output[:5]), message, now()))
            self._counter(c, 'requests_total')
            self._counter(c, 'prediction_rows_total', len(output))
            self._counter(c, 'prediction_seconds_sum', duration / 1000)
            if status == 'failed':
                self._counter(c, 'request_errors_total')
            c.execute('DELETE FROM requests WHERE id IN (SELECT id FROM requests ORDER BY created DESC LIMIT -1 OFFSET 2000)')
        if status == 'failed':
            raise error
        return {**result, 'request_id': id}

    def monitor(self, value):
        policy = {'psi_threshold': number(value.get('psi_threshold', 0.2), 'PSI 阈值', 0.01, 5), 'min_rows': int(number(value.get('min_rows', 30), '最少有效行数', 10, 10000)), 'min_label_coverage': number(value.get('min_label_coverage', 0.8), '标签覆盖率门槛', 0.1, 1), 'min_accuracy': number(value.get('min_accuracy', 0.7), '准确率门槛', 0, 1), 'max_drop': number(value.get('max_drop', 0.1), '同窗口降幅门槛', 0.01, 1)}
        with self.connect(True) as c:
            d = self.head(c)
            if not d['model'] or value.get('revision') != d['revision']:
                raise WorkspaceError('服务尚未就绪或版本已变化，请刷新。', 409)
            a, sha = self._load(d['model'], c)
            dataset = self.dataset(value.get('dataset'), c)
            if not dataset['active'] or dataset['kind'] != 'monitoring' or set(dataset['data']['features']) != set(a['features']):
                raise WorkspaceError('请选择与当前模型特征一致的有效监控数据。')
            id = self._queue(c, 'monitor', {'dataset': dataset['id'], 'model': d['model'], 'sha': sha, 'baseline': d['previous'], 'revision': d['revision'], 'policy': policy})
        self.wake.set()
        return {'job_id': id}

    def window(self, id):
        with self.connect() as c:
            r = dict(self.required(c, 'windows', id))
            r['policy'] = json.loads(r['policy'])
            r['report'] = json.loads(r['report'])
            r['alerts'] = [dict(a) for a in c.execute('SELECT * FROM alerts WHERE window=?', (id,))]
            return r

    def alert(self, id):
        with self.connect() as c:
            r = dict(self.required(c, 'alerts', id))
            r['actions'] = [dict(a) for a in c.execute('SELECT * FROM alert_actions WHERE alert=? ORDER BY revision', (id,))]
            return r

    def alert_action(self, id, value):
        actor = text(value.get('actor'), '处理人', 80)
        comment = text(value.get('comment'), '处理依据', 2000)
        status = value.get('status')
        if status not in ('acknowledged', 'resolved', 'open'):
            raise WorkspaceError('告警状态无效。')
        with self.connect(True) as c:
            a = self.required(c, 'alerts', id)
            if value.get('revision') != a['revision']:
                raise WorkspaceError('告警处理状态已变化，请刷新。', 409)
            revision = a['revision'] + 1
            c.execute('UPDATE alerts SET status=?,revision=? WHERE id=?', (status, revision, id))
            c.execute('INSERT INTO alert_actions VALUES(?,?,?,?,?,?,?)', (uid('action'), id, revision, status, actor, comment, now()))
        return {'revision': revision}

    def _train(self, job):
        p = job['payload']
        d = self.dataset(p['dataset'])
        data = d['data']
        if not d['active'] or d['sha'] != p['sha']:
            raise WorkspaceError('训练数据已归档或哈希变化。', 409)
        payload = {'features': data['features'], 'x': [[r[f] for f in data['features']] for r in data['rows']], 'y': data['labels'], 'parameters': p['parameters']}
        env = {**os.environ, 'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1'}
        with tempfile_input(dump(payload).encode()) as input_file:
            proc = subprocess.Popen([sys.executable, '-I', '-X', 'utf8', str(ROOT / 'scripts/train_mlops.py')], stdin=input_file, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, start_new_session=os.name == 'posix')
            start = time.monotonic()
            try:
                while True:
                    try:
                        out, err = proc.communicate(timeout=0.2)
                        break
                    except subprocess.TimeoutExpired:
                        if self.cancelled(job['id']):
                            raise InterruptedError('训练已取消。')
                        if time.monotonic() - start > 50:
                            raise WorkspaceError('训练超过50秒，已停止。')
                if proc.returncode:
                    raise WorkspaceError('训练进程失败或达到资源限制，请检查数据。')
            finally:
                if proc.poll() is None:
                    if os.name == 'posix':
                        os.killpg(proc.pid, signal.SIGKILL)
                    else:
                        proc.kill()
                    proc.communicate()
        try:
            r = json.loads(out)
            validate_artifact(r['artifact'])
            metrics = r['metrics']
            split = r['split']
        except (ValueError, KeyError, TypeError):
            raise WorkspaceError('训练输出不符合安全制品协议。') from None
        actual = infer(r['artifact'], [data['rows'][i] for i in split['validation']])
        accuracy = sum((x['prediction'] == data['labels'][i] for x, i in zip(actual, split['validation']))) / len(actual)
        if abs(accuracy - metrics['accuracy']) > 1e-10:
            raise WorkspaceError('制品重载与训练验证结果不一致。')
        return {'artifact': r['artifact'], 'metrics': metrics, 'split': split, 'gate': metrics['converged'] and metrics['accuracy'] >= p['policy']['min_accuracy'] and (metrics['log_loss'] <= p['policy']['max_log_loss'])}

    def _monitor(self, job):
        p = job['payload']
        d = self.dataset(p['dataset'])
        data = d['data']
        policy = p['policy']
        with self.connect() as c:
            a, sha = self._load(p['model'], c)
            source=self.model(p['model'],c)['experiment']['dataset']
            training_reused=self.dataset(source,c)['sha']==d['sha']
            if sha != p['sha']:
                raise WorkspaceError('模型制品已变化，监控任务未执行。', 409)
            baseline = None
            baseline_error = ''
            if p['baseline']:
                try:
                    baseline, _ = self._load(p['baseline'], c)
                except WorkspaceError as e:
                    baseline_error = str(e)
        valid = [i for i, row in enumerate(data['rows']) if all((row.get(f) is not None for f in a['features']))]
        rows = [data['rows'][i] for i in valid]
        output = infer(a, rows) if rows else []
        labeled = [j for j, i in enumerate(valid) if data['labels'][i] is not None]
        ys = [data['labels'][valid[j]] for j in labeled]
        accuracy = sum((output[j]['prediction'] == y for j, y in zip(labeled, ys))) / len(labeled) if labeled else None
        features = []
        for idx, f in enumerate(a['features']):
            values = [r[f] for r in data['rows'] if r[f] is not None]
            ref = a['reference'][idx]
            counts = np.bincount(np.searchsorted(ref['edges'], values, side='right'), minlength=len(ref['edges']) + 1).tolist()
            reference = (np.asarray(ref['counts']) + 0.5) / (sum(ref['counts']) + 0.5 * len(counts))
            current = (np.asarray(counts) + 0.5) / (len(values) + 0.5 * len(counts))
            psi = float(np.sum((current - reference) * np.log(current / reference))) if values else None
            features.append({'feature': f, 'psi': psi, 'rows': len(values), 'edges': ref['edges'], 'reference_counts': ref['counts'], 'current_counts': counts})
        baseline_accuracy = None
        if baseline and set(baseline['features']) != set(a['features']):
            baseline_error = '上一模型特征结构不同，未进行同窗口对照。'
        if baseline and set(baseline['features']) == set(a['features']) and labeled:
            b = infer(baseline, rows)
            baseline_accuracy = sum((b[j]['prediction'] == y for j, y in zip(labeled, ys))) / len(labeled)
        coverage = len(labeled) / len(valid) if valid else 0
        enough = len(valid) >= policy['min_rows']
        quality_ready = enough and len(labeled) >= policy['min_rows'] and (coverage >= policy['min_label_coverage'])
        drop = baseline_accuracy - accuracy if quality_ready and baseline_accuracy is not None else None
        report = {'training_data_reused':training_reused,'total_rows': len(data['rows']), 'valid_rows': len(valid), 'labeled_rows': len(labeled), 'label_coverage': coverage, 'quality': data['quality'], 'accuracy': accuracy, 'quality_ready': quality_ready, 'baseline_accuracy': baseline_accuracy, 'baseline_error': baseline_error, 'accuracy_drop': drop, 'features': features, 'samples': [{'row': valid[i] + 1, **x} for i, x in enumerate(output[:10])], 'boundary': '显式导入的数据快照；并非持续采集。PSI 漂移不等同模型效果下降。'}
        alerts = []
        if training_reused:alerts.append(('training_overlap','info','窗口原文件与训练快照完全相同，结果不是独立留出评估。'))
        if data['quality']['invalid_feature_rows'] or data['quality']['invalid_labels']:
            alerts.append(('data_quality', 'warning', '数据含缺失或无效值；检查质量统计与跳过行。'))
        if not enough:
            alerts.append(('insufficient_rows', 'warning', '有效行少于门槛，漂移与质量仅供观察。'))
        if coverage < policy['min_label_coverage'] or len(labeled) < policy['min_rows']:
            alerts.append(('labels_missing', 'info', '标签不足，不触发效果下降结论或自动回滚。'))
        if enough and any((f['psi'] is not None and f['rows'] >= policy['min_rows'] and (f['psi'] > policy['psi_threshold']) for f in features)):
            alerts.append(('feature_drift', 'warning', '特征分布超过本窗口 PSI 阈值，需核对输入变化。'))
        if quality_ready and (accuracy < policy['min_accuracy'] or (drop is not None and drop > policy['max_drop'])):
            alerts.append(('quality_drop', 'critical', '有标签窗口的准确率或同窗口降幅超过本窗口门槛。'))
        return {'report': report, 'alerts': alerts}

    def process_one(self):
        self.recover()
        with self.connect(True) as c:
            r = c.execute("SELECT id FROM jobs WHERE status='queued' ORDER BY created LIMIT 1").fetchone()
            if not r:
                return False
            id = r['id']
            c.execute("UPDATE jobs SET status='running',owner=?,heartbeat=?,updated=? WHERE id=?", (self.owner, time.time(), now(), id))
        done = threading.Event()

        def heartbeat():
            while not done.wait(1):
                with self.connect(True) as c:
                    c.execute('UPDATE jobs SET heartbeat=? WHERE id=? AND owner=?', (time.time(), id, self.owner))
        beat = threading.Thread(target=heartbeat, daemon=True)
        beat.start()
        job = self.job(id)
        p = job['payload']
        start = time.perf_counter()
        try:
            if self.cancelled(id):
                raise InterruptedError('任务已取消。')
            if job['kind'] == 'train':
                output = self._train(job)
            elif job['kind'] == 'monitor':
                output = self._monitor(job)
            elif job['kind'] == 'tracking':
                output = self._track(job)
            elif job['kind'] == 'deploy':
                with self.connect() as c:
                    a, sha = self._load(p['model'], c)
                    if sha != p['sha']:
                        raise WorkspaceError('制品哈希已变化，未切换。', 409)
                output = {}
            else:
                raise WorkspaceError('未知任务类型。')
            duration = (time.perf_counter() - start) * 1000
            with self.connect(True) as c:
                if self.cancelled(id, c):
                    raise InterruptedError('任务已取消。')
                if job['kind'] == 'train':
                    dataset = self.dataset(p['dataset'], c)
                    if not dataset['active'] or dataset['sha'] != p['sha']:
                        raise WorkspaceError('训练期间数据已归档，结果未提交。', 409)
                    e = uid('experiment')
                    m = uid('model')
                    artifact = dump(output['artifact'])
                    c.execute('INSERT INTO experiments VALUES(?,?,?,?,?,?,?,?,?,?,?)', (e, id, p['dataset'], dump(p['parameters']), dump(output['metrics']), dump(output['split']), dump(p['policy']), int(output['gate']), m, duration, now()))
                    c.execute('INSERT INTO models VALUES(?,?,?,?,0,?)', (m, e, artifact, digest(artifact), now()))
                    result = {'experiment_id': e, 'model_id': m}
                elif job['kind'] == 'deploy':
                    head = self.head(c)
                    m = self.model(p['model'], c)
                    self._load(p['model'], c)
                    if head['revision'] != p['revision'] or m['decision'] != 'approved' or m['review_revision'] != p['review_revision']:
                        raise WorkspaceError('加载期间活动版本或审核状态已变化，未切换。', 409)
                    revision = head['revision'] + 1
                    c.execute('UPDATE deployment SET revision=?,model=?,previous=?,updated=? WHERE id=1', (revision, p['model'], head['model'], now()))
                    c.execute('INSERT INTO events VALUES(?,?,?,?,?,?,?,?,?,?,?,?)', (uid('event'), id, 'rollback' if p['rollback'] else 'deploy', 'succeeded', p['model'], p['model'], revision, p['actor'], p['comment'], '', duration, now()))
                    result = {'model_id': p['model'], 'revision': revision, 'verified': True}
                elif job['kind'] == 'tracking':
                    result = output
                else:
                    w = uid('window')
                    c.execute('INSERT INTO windows VALUES(?,?,?,?,?,?,?,?,?)', (w, id, p['dataset'], p['model'], p['baseline'], p['revision'], dump(p['policy']), dump(output['report']), now()))
                    for kind, severity, summary in output['alerts']:
                        c.execute("INSERT INTO alerts VALUES(?,?,?,?,'open',0,?,?)", (uid('alert'), w, kind, severity, summary, now()))
                    result = {'window_id': w}
                c.execute("UPDATE jobs SET status='succeeded',result=?,updated=? WHERE id=?", (dump(result), now(), id))
        except Exception as e:
            message = str(e) if isinstance(e, (WorkspaceError, ValueError, InterruptedError)) else '任务执行失败，请查看服务端日志。'
            status = 'interrupted' if self.stop.is_set() else 'cancelled' if isinstance(e, InterruptedError) else 'failed'
            if not isinstance(e, (WorkspaceError, ValueError, InterruptedError)):
                import traceback
                traceback.print_exc()
            with self.connect(True) as c:
                c.execute('UPDATE jobs SET status=?,error=?,updated=? WHERE id=? AND owner=?', (status, message, now(), id, self.owner))
                if job['kind'] == 'tracking':
                    c.execute('UPDATE tracking SET status=?,error=?,updated=? WHERE experiment=?', (status, message, now(), p['experiment']))
                if job['kind'] == 'deploy':
                    head = self.head(c)
                    c.execute('INSERT INTO events VALUES(?,?,?,?,?,?,?,?,?,?,?,?)', (uid('event'), id, 'rollback' if p['rollback'] else 'deploy', status, p['model'], head['model'], head['revision'], p['actor'], p['comment'], message, (time.perf_counter() - start) * 1000, now()))
        finally:
            done.set()
            beat.join(2)
        return True

    def loop(self):
        while not self.stop.is_set():
            if not self.process_one():
                self.wake.wait(0.4)
                self.wake.clear()

    def track(self, id):
        from shared.mlops_tracking import base_url
        base = base_url()
        with self.connect(True) as c:
            self.required(c, 'experiments', id)
            job = self._queue(c, 'tracking', {'experiment': id, 'base': base})
        self.wake.set()
        return {'job_id': job}

    def _track(self, job):
        from shared.mlops_tracking import base_url, call, experiment_id
        p = job['payload']
        base = base_url()
        if p['base'] != base:
            raise WorkspaceError('MLflow 地址已改变，请新建同步任务。', 409)
        e = self.experiment(p['experiment'])
        m = self.model(e['model'])
        dataset = self.dataset(e['dataset'])
        stamp = int(datetime.fromisoformat(e['created']).timestamp() * 1000)
        with self.connect(True) as c:
            row = c.execute('SELECT * FROM tracking WHERE experiment=?', (e['id'],)).fetchone()
            if row and row['url'] != base:
                raise WorkspaceError('此实验已关联其他 MLflow 地址，不复用旧 run ID。', 409)
            c.execute("INSERT INTO tracking VALUES(?,NULL,?,'running','',?) ON CONFLICT(experiment) DO UPDATE SET status='running',error='',updated=excluded.updated", (e['id'], base, now()))

        def checked(path, body=None):
            if self.cancelled(job['id']):
                raise InterruptedError('同步已取消；远端已写入内容可能保留。')
            return call(path, body)
        remote = row['remote_run'] if row else None
        if not remote:
            exp = experiment_id()
            found = checked('runs/search', {'experiment_ids': [str(exp)], 'filter': "tags.`lab.experiment_id` = '" + e['id'] + "'", 'max_results': 2}).get('runs', [])
            if len(found) > 1:
                raise WorkspaceError('MLflow 存在重复 run，请先在远端核对。', 409)
            result = found[0] if found else checked('runs/create', {'experiment_id': str(exp), 'start_time': stamp, 'run_name': e['parameters'].get('name', e['id']), 'tags': [{'key': 'lab.experiment_id', 'value': e['id']}, {'key': 'lab.model_id', 'value': m['id']}]})['run']
            remote = result['info'].get('run_id') or result['info']['run_uuid']
            with self.connect(True) as c:
                c.execute('UPDATE tracking SET remote_run=?,updated=? WHERE experiment=?', (remote, now(), e['id']))
        params = {**e['parameters'], 'dataset_sha256': dataset['sha'], 'artifact_sha256': m['sha'], 'feature_count': len(dataset['data']['features'])}
        metrics = [{'key': k, 'value': v, 'timestamp': stamp, 'step': 0} for k, v in e['metrics'].items() if type(v) in (int, float)]
        checked('runs/log-batch', {'run_id': remote, 'params': [{'key': k, 'value': str(v)} for k, v in params.items()], 'metrics': metrics, 'tags': [{'key': 'lab.quality_gate', 'value': str(bool(e['gate'])).lower()}]})
        checked('runs/update', {'run_id': remote, 'status': 'FINISHED', 'end_time': stamp + int(e['duration_ms'])})
        with self.connect(True) as c:
            c.execute("UPDATE tracking SET status='succeeded',error='',updated=? WHERE experiment=?", (now(), e['id']))
        return {'experiment_id': e['id'], 'remote_run': remote, 'boundary': '仅同步参数、指标和血缘标识；制品权重和模型注册/别名仍由本地工作区管理。'}

    def export(self, kind, id):
        if kind == 'datasets':
            with self.connect() as c:
                r = self.required(c, 'datasets', id)
                return (r['raw'], 'text/csv; charset=utf-8', id + '.csv')
        if kind == 'models':
            value = self.model(id)
        elif kind == 'experiments':
            value = self.experiment(id)
        elif kind == 'windows':
            value = self.window(id)
        else:
            raise WorkspaceError('导出对象不存在。', 404)
        return (dump(value).encode(), 'application/json; charset=utf-8', id + '.json')

    def metrics(self):
        with self.connect() as c:
            counters = {r['name']: r['value'] for r in c.execute('SELECT * FROM counters')}
        service = self.health()
        s = {'counters': counters, 'service': service}
        out = []
        for key, help, type, value in [('lab_mlops_requests_total', 'Observed prediction requests', 'counter', s['counters'].get('requests_total', 0)), ('lab_mlops_request_errors_total', 'Failed prediction requests', 'counter', s['counters'].get('request_errors_total', 0)), ('lab_mlops_prediction_rows_total', 'Successfully predicted rows', 'counter', s['counters'].get('prediction_rows_total', 0)), ('lab_mlops_prediction_seconds_sum', 'Model loading validation and inference seconds excluding audit write', 'counter', s['counters'].get('prediction_seconds_sum', 0)), ('lab_mlops_deployment_revision', 'Active deployment revision', 'gauge', s['service']['revision']), ('lab_mlops_ready', 'Artifact readiness checked on request', 'gauge', int(s['service']['ready']))]:
            out.extend(['# HELP ' + key + ' ' + help, '# TYPE ' + key + ' ' + type, key + ' ' + str(value)])
        return ('\n'.join(out) + '\n').encode()

@contextmanager
def tempfile_input(data):
    import tempfile
    with tempfile.TemporaryFile() as f:
        f.write(data)
        f.seek(0)
        yield f
_singleton = None
_singleton_lock = threading.Lock()

def get_mlops_workspace():
    global _singleton
    with _singleton_lock:
        if _singleton is None:
            _singleton = MlopsWorkspace(os.environ.get('LAB_DATA_DIR', str(ROOT / 'data')))
        return _singleton
