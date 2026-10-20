"""Manual evidence relationships and reproducible structural writing checks for D13."""
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import uuid
from shared.process_workspace import WorkspaceError

BOUNDARY = '结构就绪检查不等于语义质量评估。证据关系由人填写，不是模型自动判定；摘要和摘记不能当作论文全文。'
KINDS = ('supports', 'contrasts', 'complements')


def stamp():
    return datetime.now(timezone.utc).isoformat()


def dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def fingerprint(e):
    return hashlib.sha256(dump({k: e[k] for k in ('id', 'paper', 'version', 'revision', 'status', 'quote', 'summary', 'field', 'start', 'end')}).encode()).hexdigest()


def required_text(value, label, limit):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= limit:
        raise WorkspaceError(f'{label}应为1–{limit}字。')
    return value.strip()


class LiteratureReviewMixin:
    def relations(self, project, c=None):
        if c is None:
            with self.connect() as conn:
                return self.relations(project, conn)
        self.required(c, 'projects', project)
        current = {e['id']: e for e in self.evidence(project, c)}
        result = []
        for row in c.execute('SELECT * FROM evidence_relations WHERE project=? ORDER BY rowid', (project,)):
            body = dict(row)
            body.update(json.loads(body.pop('body')))
            endpoints = [current.get(body['left']), current.get(body['right'])]
            body['stale'] = any(e is None or e['stale'] or e['status'] != 'confirmed' or fingerprint(e) != body['sources'][e['id']] for e in endpoints)
            result.append(body)
        return result

    def save_relation(self, project, value, relation_id=None):
        kind = value.get('kind')
        if kind not in KINDS:
            raise WorkspaceError('请选择支持、分歧或补充关系。')
        actor = required_text(value.get('actor'), '记录人', 80)
        note = required_text(value.get('note'), '关系说明与条件差异', 2000)
        left, right = value.get('left'), value.get('right')
        if not isinstance(left, str) or not isinstance(right, str) or left == right:
            raise WorkspaceError('请选择两条不同的已核对证据。')
        with self.connect(True) as c:
            self.required(c, 'projects', project)
            es = {e['id']: e for e in self.evidence(project, c)}
            if left not in es or right not in es:
                raise WorkspaceError('关系端点必须属于当前专题。', 404)
            if any(es[i]['stale'] or es[i]['status'] != 'confirmed' for i in (left, right)):
                raise WorkspaceError('关系仅能连接当前有效且已核对的证据。', 409)
            if value.get('source_revisions') != {left: es[left]['revision'], right: es[right]['revision']}:
                raise WorkspaceError('证据已变化，请重新读取后记录关系。', 409)
            history = []
            if relation_id:
                row = c.execute('SELECT * FROM evidence_relations WHERE id=? AND project=?', (relation_id, project)).fetchone()
                if not row:
                    raise WorkspaceError('证据关系不存在。', 404)
                if type(value.get('revision')) is not int or value['revision'] != row['revision']:
                    raise WorkspaceError('关系已变化，请刷新后合并。', 409)
                revision = row['revision'] + 1
                history = json.loads(row['body'])['history']
            else:
                if c.execute('SELECT count(*) FROM evidence_relations WHERE project=?', (project,)).fetchone()[0] >= 60:
                    raise WorkspaceError('单个专题最多60条证据关系。')
                relation_id, revision = 'rel-' + uuid.uuid4().hex[:16], 1
            for row in c.execute('SELECT id,body FROM evidence_relations WHERE project=? AND id<>?', (project, relation_id)):
                prior = json.loads(row['body'])
                if {prior['left'], prior['right']} == {left, right}:
                    raise WorkspaceError('这两条证据已有关系，请修改已有记录。', 409)
            record = {'revision': revision, 'left': left, 'right': right, 'kind': kind, 'actor': actor, 'note': note,
                      'sources': {i: fingerprint(es[i]) for i in (left, right)}, 'updated': stamp()}
            history.append(dict(record))
            body = {**record, 'history': history}
            c.execute('INSERT OR REPLACE INTO evidence_relations VALUES(?,?,?,?)', (relation_id, project, revision, dump(body)))
        return {'relation_id': relation_id, 'revision': revision}

    def delete_relation(self, project, relation_id, value):
        with self.connect(True) as c:
            row = c.execute('SELECT revision FROM evidence_relations WHERE id=? AND project=?', (relation_id, project)).fetchone()
            if not row:
                raise WorkspaceError('证据关系不存在。', 404)
            if type(value.get('revision')) is not int or value['revision'] != row['revision']:
                raise WorkspaceError('关系已变化，请刷新后重试。', 409)
            c.execute('DELETE FROM evidence_relations WHERE id=?', (relation_id,))
        return {'deleted': True}

    def audit(self, project):
        with self.connect() as c:
            c.execute('BEGIN')
            ctx = self.context(project, c)
            relations = self.relations(project, c)
            blocking, warnings = [], []
            if not ctx['papers']:
                blocking.append({'code': 'no_papers', 'message': '尚未纳入文献。'})
            if not ctx['project']['outline_confirmed']:
                blocking.append({'code': 'outline', 'message': '章节提纲尚未确认。'})
            ready = [e for e in ctx['evidence'] if e['status'] == 'confirmed' and not e['stale']]
            for e in ctx['evidence']:
                if e['stale'] or e['status'] != 'confirmed':
                    blocking.append({'code': 'evidence', 'evidence_id': e['id'], 'paper_id': e['paper'], 'message': '证据已过期。' if e['stale'] else '证据存在分歧。' if e['status'] == 'conflict' else '证据尚未核对。'})
            rows = []
            for p in ctx['papers']:
                es = [e for e in ctx['evidence'] if e['paper'] == p['id']]
                valid = [e for e in ready if e['paper'] == p['id']]
                if not p['active'] or p['version'] == 0 or p['status'] != 'ready':
                    blocking.append({'code': 'paper_unready', 'paper_id': p['id'], 'message': '纳入文献未就绪或已移出文献库。'})
                if not valid and not es:
                    blocking.append({'code': 'missing_evidence', 'paper_id': p['id'], 'message': '纳入文献缺少有效且已核对的证据。'})
                fields = {field: [e['id'] for e in valid if e['field'] == field] for field in ('method', 'finding', 'limitation')}
                missing = [field for field, ids in fields.items() if not ids]
                rows.append({'paper_id': p['id'], 'title': p['metadata']['title'], 'scope': p['metadata']['scope'],
                             'version': p['version'], 'sha': p['sha'], 'evidence_count': len(es), 'confirmed_count': len(valid), 'fields': fields})
                if missing:
                    warnings.append({'code': 'category_gap', 'paper_id': p['id'], 'fields': missing, 'message': '部分证据类别为空；请判断是不适用还是尚未摘录。'})
                if p['metadata']['scope'] != 'full_text':
                    warnings.append({'code': 'scope', 'paper_id': p['id'], 'message': '当前输入不是论文全文，写作需明确范围。'})
                if not p['metadata'].get('authors') or not p['metadata'].get('year'):
                    warnings.append({'code': 'metadata', 'paper_id': p['id'], 'message': '作者或年份尚未补齐。'})
            for rel in relations:
                if rel['stale']:
                    blocking.append({'code': 'relation', 'relation_id': rel['id'], 'message': '关系引用的证据已变化，请重新核对或移除关系。'})
            return {'schema': 'd13-evidence-audit-v1', 'created': stamp(), 'project': ctx['project'], 'context_fingerprint': ctx['fingerprint'],
                    'ready_for_writing': not blocking, 'blocking': blocking, 'warnings': warnings, 'papers': rows,
                    'evidence': ctx['evidence'], 'relations': relations, 'boundary': BOUNDARY}

    def export_audit(self, project, fmt='json'):
        report = self.audit(project)
        if fmt == 'json':
            return dump(report).encode(), 'application/json; charset=utf-8', project+'-evidence.json'
        safe = lambda x: str(x if x is not None else '').replace('<', '&lt;').replace('>', '&gt;').replace('|', '\\|').replace('\n', ' ')
        if fmt == 'markdown':
            lines = ['# '+safe(report['project']['title'])+' / 证据核对记录', report['boundary'], '上下文：'+report['context_fingerprint'],
                     '结构检查：'+('可进入写作' if report['ready_for_writing'] else '存在待处理项')]
            for issue in report['blocking']+report['warnings']:
                lines.append('- '+safe(issue.get('evidence_id', issue.get('paper_id', issue.get('relation_id', ''))))+' '+safe(issue['message']))
            for e in report['evidence']:
                lines += ['', '## '+e['id'], f"来源 {e['paper']} v{e['version']} p.{e['page']} 字符{e['start']}–{e['end']}",
                          '> '+safe(e['quote']), safe(e['summary']), '核对：'+safe(e['status'])+(' / 来源已变更' if e['stale'] else '')]
            for r in report['relations']:
                lines += ['', '## 关系 '+r['id'], safe(r['left']+' / '+r['kind']+' / '+r['right']), safe(r['note']), '记录人：'+safe(r['actor'])]
            return '\n\n'.join(lines).encode(), 'text/markdown; charset=utf-8', project+'-evidence.md'
        if fmt == 'csv':
            out = io.StringIO(newline='')
            writer = csv.writer(out)
            writer.writerow(['证据ID','文献ID','版本','页码','类别','逐字引文','证据说明','核对状态','来源过期','核对人'])
            cell = lambda x: "'"+str(x) if str(x).lstrip().startswith(('=', '+', '-', '@', '\t', '\r')) else x
            for e in report['evidence']:
                writer.writerow([cell(x) for x in (e['id'],e['paper'],e['version'],e['page'],e['field'],e['quote'],e['summary'],e['status'],e['stale'],e['actor'])])
            return out.getvalue().encode('utf-8-sig'), 'text/csv; charset=utf-8', project+'-evidence.csv'
        raise WorkspaceError('支持JSON、Markdown或CSV导出。')
