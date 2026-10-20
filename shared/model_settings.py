"""One server-side model configuration, shared by the app and repair worker."""
from contextvars import ContextVar, copy_context
from functools import wraps
import json
import os
from pathlib import Path
import tempfile
import threading
from urllib.parse import urlsplit

_session = ContextVar('lab_model_configuration', default=None)
_lock = threading.RLock()
ROOT = Path(__file__).resolve().parents[1]


def settings_path():
    return Path(os.environ.get('LAB_DATA_DIR', str(ROOT / 'data'))) / 'model-settings.json'


def resolve():
    frozen = _session.get()
    if frozen is not None:
        return dict(frozen)
    path = settings_path()
    try:
        with path.open(encoding='utf-8') as file:
            value = json.load(file)
        if not isinstance(value, dict) or value.get('schema') != 1:
            raise ValueError()
        return {k: value.get(k, '') for k in ('base_url', 'model', 'vision_model', 'api_key')} | {'source': 'overview'}
    except FileNotFoundError:
        return {'base_url': os.environ.get('LAB_LLM_BASE_URL', '').strip().rstrip('/'),
                'model': os.environ.get('LAB_LLM_MODEL', '').strip(),
                'vision_model': os.environ.get('LAB_LLM_VISION_MODEL', '').strip(),
                'api_key': os.environ.get('LAB_LLM_API_KEY', '').strip(), 'source': 'environment'}
    except (OSError, ValueError, TypeError):
        # A damaged saved configuration must not silently select another provider.
        return {'base_url': '', 'model': '', 'vision_model': '', 'api_key': '', 'source': 'invalid'}


def configured():
    value = resolve()
    return all(value.get(k) for k in ('base_url', 'model', 'api_key'))


def model_name(vision=False):
    value = resolve()
    return (value.get('vision_model') if vision else '') or value.get('model') or None


def identity():
    value = resolve()
    return {'base': value.get('base_url') or None, 'model': value.get('model') or None}


def public_state():
    value = resolve()
    return {'configured': configured(), 'base_url': value['base_url'], 'model': value['model'],
            'vision_model': value['vision_model'], 'key_present': bool(value['api_key']),
            'source': value['source'], 'saved': settings_path().exists(), 'vision_verified': False}


def save(value):
    if not isinstance(value, dict) or set(value) - {'base_url', 'model', 'vision_model', 'api_key'}:
        raise ValueError('模型配置字段无效。')
    fields = {}
    for key, limit in (('base_url', 1000), ('model', 200), ('vision_model', 200), ('api_key', 4096)):
        field = value.get(key, '')
        if not isinstance(field, str) or len(field) > limit or any(ord(c) < 32 for c in field):
            raise ValueError('模型配置含无效字符或超出长度限制。')
        fields[key] = field.strip()
    fields['base_url'] = fields['base_url'].rstrip('/')
    try:
        url = urlsplit(fields['base_url'])
        valid = url.scheme in ('http', 'https') and url.hostname and url.port != 0 and not url.username and not url.password and not url.query and not url.fragment
    except ValueError:
        valid = False
    if not valid or fields['base_url'].endswith('/chat/completions') or not fields['model']:
        raise ValueError('请填写HTTP(S)基础地址和模型名；地址不要包含密钥、查询参数或/chat/completions。')
    with _lock:
        previous = resolve()
        if not fields['api_key']:
            if fields['base_url'] != previous['base_url']:
                raise ValueError('更换服务地址时请重新输入API Key，避免把旧密钥发给其他服务。')
            fields['api_key'] = previous['api_key']
        if not fields['api_key']:
            raise ValueError('请输入API Key；无认证的本地服务可填写local。')
        path = settings_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix='.model-settings-', dir=path.parent)
        try:
            with os.fdopen(descriptor, 'w', encoding='utf-8') as file:
                json.dump({'schema': 1, **fields}, file, ensure_ascii=False)
                file.flush()
                os.fsync(file.fileno())
            if os.name != 'nt':
                os.chmod(temporary, 0o600)
            os.replace(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)
    return public_state()


def clear():
    with _lock:
        settings_path().unlink(missing_ok=True)
    return public_state()


def model_session(function):
    """Keep an in-progress task on its original endpoint/key/model."""
    @wraps(function)
    def run(*args, **kwargs):
        token = _session.set(resolve())
        try:
            return function(*args, **kwargs)
        finally:
            _session.reset(token)
    return run


def contextual(function):
    context = copy_context()
    return lambda value: context.copy().run(function, value)
