import base64
import json
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch
import server
from shared.video_workspace import VideoWorkspace, FINAL
from pathlib import Path


class VideoHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.w = VideoWorkspace(cls.tmp.name)
        cls.override = patch.object(server, 'get_video_workspace', return_value=cls.w)
        cls.override.start()
        cls.s = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        cls.base = f'http://127.0.0.1:{cls.s.server_port}'
        cls.thread = threading.Thread(target=cls.s.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.s.shutdown(); cls.s.server_close(); cls.thread.join(); cls.override.stop(); cls.w.close(); cls.tmp.cleanup()

    def req(self, path, body=None, headers=None, method=None):
        return urllib.request.urlopen(urllib.request.Request(self.base + path, json.dumps(body).encode() if body is not None else None,
            {'Content-Type': 'application/json', **(headers or {})}, method=method))

    def test_upload_sampling_media_ranges_head_export_and_delete(self):
        raw = (Path(server.ROOT) / 'demos/04-video-understanding/sample.webm').read_bytes()
        root = '/api/video-workspace/'
        with self.req(root + 'assets', {'name': 'HTTP视频', 'content': base64.b64encode(raw).decode()}) as r:
            self.assertEqual(r.status, 202)
            x = json.load(r)
        for _ in range(400):
            if self.w.job(x['job']['id'])['status'] in FINAL:
                break
            time.sleep(.025)
        self.assertEqual(self.w.job(x['job']['id'])['status'], 'succeeded')
        aid = x['asset']['id']
        for method in ('GET', 'HEAD'):
            with self.req(root + 'assets/' + aid + '/media', headers={'Range': 'bytes=2-10'}, method=method) as r:
                self.assertEqual(r.status, 206)
                self.assertEqual(r.headers['Content-Range'], f'bytes 2-10/{len(raw)}')
                self.assertEqual(r.headers['Content-Length'], '9')
                self.assertEqual(r.read(), raw[2:11] if method == 'GET' else b'')
        with self.req(root + 'assets/' + aid + '/media', headers={'Range': 'bytes=-8'}) as r:
            self.assertEqual(r.read(), raw[-8:])
        with self.assertRaises(urllib.error.HTTPError) as e:
            self.req(root + 'assets/' + aid + '/media', headers={'Range': 'bytes=99999999-'})
        self.assertEqual(e.exception.code, 416)
        with self.req(root + 'assets/' + aid + '/sampling-jobs', {'count': 2}) as r:
            j = json.load(r)
        for _ in range(400):
            job = self.w.job(j['id'])
            if job['status'] in FINAL:
                break
            time.sleep(.025)
        self.assertEqual(job['status'], 'succeeded')
        with self.req(root + 'samples/' + job['result']['sample_id']) as r:
            sample = json.load(r)
        with self.req(root + f"assets/{aid}/frames/{sample['id']}/f1") as r:
            self.assertEqual(r.headers['Content-Type'], 'image/jpeg')
        with self.req(root + 'assets/' + aid + '/delete', {}) as r:
            self.assertEqual(r.status, 200)
        with self.assertRaises(urllib.error.HTTPError) as e:
            self.req(root + 'assets/' + aid + '/media')
        self.assertEqual(e.exception.code, 404)

    def test_invalid_origin_and_private_paths(self):
        for method in ('GET', 'HEAD'):
            for path in ('/data/video/video.sqlite3', '/shared/../data/video/video.sqlite3'):
                with self.assertRaises(urllib.error.HTTPError) as e:
                    self.req(path, method=method)
                self.assertEqual(e.exception.code, 404)
        with self.assertRaises(urllib.error.HTTPError) as e:
            self.req('/api/video-workspace/assets', {}, {'Origin': 'https://other.invalid'})
        self.assertEqual(e.exception.code, 403)
        with self.assertRaises(urllib.error.HTTPError) as e:
            self.req('/api/video-workspace/jobs/unknown')
        self.assertEqual(e.exception.code, 404)
