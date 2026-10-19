"""Optional MLflow REST tracking bridge. Does not replace the serving pointer."""
import json, os, urllib.request, urllib.error
from urllib.parse import urlsplit, urlencode
from shared.process_workspace import WorkspaceError

class TrackingHTTPError(WorkspaceError):

    def __init__(self, status, code=''):
        super().__init__(f'MLflow 请求失败（HTTP {status}）；请检查服务连接与权限。', 502)
        self.http_status = status
        self.code = code

class NoRedirect(urllib.request.HTTPRedirectHandler):

    def redirect_request(self, *args, **kwargs):
        return None

def base_url():
    value = os.environ.get('LAB_MLFLOW_URL', '').rstrip('/')
    p = urlsplit(value)
    if p.scheme not in ('http', 'https') or not p.netloc or p.username or p.password or p.query or p.fragment:
        raise WorkspaceError('请在服务端配置无凭据、无查询参数的 HTTP(S) LAB_MLFLOW_URL。', 503)
    return value

def call(path, body=None):
    url = base_url() + '/api/2.0/mlflow/' + path
    headers = {'Accept': 'application/json'}
    token = os.environ.get('LAB_MLFLOW_TOKEN')
    if token:
        headers['Authorization'] = 'Bearer ' + token
    if body is not None:
        headers['Content-Type'] = 'application/json'
    request = urllib.request.Request(url, json.dumps(body, allow_nan=False).encode() if body is not None else None, headers)
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=15) as response:
            raw = response.read(1024 * 1024 + 1)
    except urllib.error.HTTPError as error:
        try:
            code = json.loads(error.read(10000)).get('error_code', '')
        except (ValueError, AttributeError):
            code = ''
        raise TrackingHTTPError(error.code, code) from None
    except (OSError, urllib.error.URLError):
        raise WorkspaceError('无法连接 MLflow，或请求超过15秒；已有本地实验与部署不受影响。', 502) from None
    if len(raw) > 1024 * 1024:
        raise WorkspaceError('MLflow 响应过大。', 502)
    try:
        value = json.loads(raw)
    except ValueError:
        raise WorkspaceError('MLflow 返回非 JSON 响应。', 502) from None
    if not isinstance(value, dict):
        raise WorkspaceError('MLflow 响应结构无效。', 502)
    return value

def experiment_id():
    name = os.environ.get('LAB_MLFLOW_EXPERIMENT', 'engineering-practice-lab')
    try:
        return call('experiments/get-by-name?' + urlencode({'experiment_name': name}))['experiment']['experiment_id']
    except TrackingHTTPError as e:
        if e.http_status != 404 and e.code != 'RESOURCE_DOES_NOT_EXIST':
            raise
    try:
        return call('experiments/create', {'name': name})['experiment_id']
    except TrackingHTTPError as e:
        if e.code != 'RESOURCE_ALREADY_EXISTS':
            raise
        return call('experiments/get-by-name?' + urlencode({'experiment_name': name}))['experiment']['experiment_id']
