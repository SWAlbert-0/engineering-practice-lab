"""HTTP smoke test for the running image. No model requests or extra packages."""
import argparse
import base64
import json
import urllib.error
import urllib.request


def check(base):
    def get(path):
        with urllib.request.urlopen(base + path, timeout=15) as response:
            return response.read()

    def post(path, data):
        request = urllib.request.Request(base + path, json.dumps(data).encode(),
                                         {'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)

    assert json.loads(get('/healthz')) == {'status': 'ok', 'projects': 6}
    assert json.loads(get('/api/capabilities')) == {'llm': False}, 'Run smoke in offline mode'
    folders = ['01-repair-agent', '02-process-rag', '03-mlops',
               '04-video-understanding', '05-requirements', '06-literature']
    for path in ['/', '/report/index.html'] + [f'/demos/{f}/' for f in folders]:
        assert b'<html' in get(path).lower(), path
    assert get('/demos/04-video-understanding/sample.webm')[:4] == b'\x1aE\xdf\xa3'
    assert post('/api/repair', {'case': 'empty'})['accepted']
    assert not post('/api/repair', {'case': 'empty', 'candidate': 'wrong'})['accepted']
    assert post('/api/rag', {'query': '量具校准'})['hits']
    assert post('/api/mlops', {'noise': .65, 'labels': True})['rollback']
    assert post('/api/requirements', {'text': '用户可以查看本人订单。'})['cases']
    assert post('/api/requirements/compare', {'before': '用户查看订单。',
                'after': '用户只能查看本人订单。'})['changes']
    assert post('/api/literature', {'topic': '外部反馈', 'ids': ['REACT-2022']})['model_calls'] == 0
    # Transport fixture exercises offline input validation, not browser decoding or vision.
    frame = 'data:image/jpeg;base64,' + base64.b64encode(b'\xff\xd8transport fixture\xff\xd9').decode()
    video = post('/api/video', {'question': '采样是否就绪？', 'duration': 4,
                              'frames': [{'time': 1, 'image': frame}]})
    assert video['frame_count'] == 1 and video['mode'] == 'offline'
    for path in ['/.env', '/.git/config']:
        try:
            get(path)
        except urllib.error.HTTPError as error:
            assert error.code == 404, (path, error.code)
        else:
            raise AssertionError(f'Unexpected private file served: {path}')
    print('PASS: readiness, six project pages, report, media, offline APIs, private-file exclusion')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:8765')
    check(parser.parse_args().url.rstrip('/'))
