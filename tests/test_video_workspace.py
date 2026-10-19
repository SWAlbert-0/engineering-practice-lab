"""Actual FFmpeg media tests; model responses below are protocol stubs, not inference."""
import base64
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from shared.video_workspace import VideoWorkspace, FINAL, WorkspaceError

SAMPLE = Path(__file__).resolve().parents[1] / 'demos/04-video-understanding/sample.webm'


class VideoTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.w = VideoWorkspace(self.tmp.name)

    def tearDown(self):
        self.w.close()
        self.tmp.cleanup()

    def wait(self, job, expected='succeeded'):
        for _ in range(400):
            j = self.w.job(job['id'])
            if j['status'] in FINAL:
                self.assertEqual(j['status'], expected, j)
                return j
            time.sleep(.025)
        self.fail('Video job timed out')

    def asset(self):
        result = self.w.upload({'name': '真实解码教学样片', 'content': base64.b64encode(SAMPLE.read_bytes()).decode()})
        self.wait(result['job'])
        return self.w.state()['assets'][0]

    def sample(self, asset, count=4):
        j = self.wait(self.w.sample(asset['id'], {'count': count}))
        with self.w.lock:
            return self.w.get(j['result']['sample_id'], 'sample')

    def test_actual_sampling_reproducibility_restart_export_and_delete(self):
        a = self.asset()
        s = self.sample(a)
        s2 = self.sample(a)
        self.assertEqual(s['plan_sha256'], s2['plan_sha256'])
        self.assertEqual(s['frames'], s2['frames'])
        self.assertEqual(len(s['frames']), 4)
        for f, target in zip(s['frames'], s['requested_times']):
            self.assertLess(abs(f['time'] - target), 1)
            self.assertEqual(self.w.media(a['id'], s['id'], f['id'])[1], 'image/jpeg')
        j = self.wait(self.w.analyze({'sample_id': s['id'], 'question': '画面中有哪些操作？', 'mode': 'offline'}))
        aid = j['result']['analysis_id']
        exported = json.loads(self.w.export(aid)[0])
        self.assertTrue(exported['stale'])
        self.assertFalse(exported['analysis']['evidence'])
        self.assertIsNone(exported['analysis']['model'])
        self.w.close()
        self.w = VideoWorkspace(self.tmp.name)
        self.assertEqual(self.w.media(a['id'])[0], SAMPLE.read_bytes())
        self.assertEqual(json.loads(self.w.export(aid)[0])['analysis']['sample_id'], s['id'])
        self.w.delete(a['id'])
        self.assertEqual(list(self.w.files.iterdir()), [])
        self.assertEqual(self.w.state()['analyses'], [])
        with self.assertRaises(WorkspaceError):
            self.w.export(aid)

    def test_corrupt_video_missing_decoder_and_manual_retry(self):
        with self.assertRaises(WorkspaceError):
            self.w.upload({'name': 'bad', 'content': base64.b64encode(b'bad').decode()})
        x = self.w.upload({'name': '损坏WebM', 'content': base64.b64encode(b'\x1aE\xdf\xa3junk').decode()})
        self.wait(x['job'], 'failed')
        self.wait(self.w.action(x['job']['id'], 'retry'), 'failed')
        with patch('shared.video_workspace.shutil.which', return_value=None):
            with self.assertRaises(WorkspaceError) as e:
                self.w.upload({'name': 'x', 'content': ''})
            self.assertEqual(e.exception.status, 503)
        self.w.delete(x['asset']['id'])

    def test_model_protocol_valid_invalid_reviews_and_conflict(self):
        a = self.asset()
        s = self.sample(a)
        response = {'answer': '协议桩回答，非真实模型推理', 'uncertainty': '仅协议校验', 'evidence': [{'frame_id': 'f1', 'observation': '协议桩描述'}]}
        with patch('shared.video_workspace.configured', return_value=True), patch('shared.video_workspace.ask_json', return_value=response):
            j = self.wait(self.w.analyze({'sample_id': s['id'], 'question': '协议测试', 'mode': 'llm'}))
        aid = j['result']['analysis_id']
        result = json.loads(self.w.export(aid)[0])['analysis']
        self.assertEqual(result['evidence'][0]['time'], s['frames'][0]['time'])
        data = {'revision': 0, 'index': 0, 'verdict': 'uncertain', 'reviewer': '测试核对人', 'note': '仅测试协议'}
        self.w.review(aid, data)
        with self.assertRaises(WorkspaceError) as e:
            self.w.review(aid, data)
        self.assertEqual(e.exception.status, 409)
        self.assertEqual(len(json.loads(self.w.export(aid)[0])['analysis']['review_history']), 1)
        response['evidence'][0]['frame_id'] = 'invented-frame'
        with patch('shared.video_workspace.configured', return_value=True), patch('shared.video_workspace.ask_json', return_value=response):
            self.wait(self.w.analyze({'sample_id': s['id'], 'question': '拒绝伪造证据', 'mode': 'llm'}), 'failed')
        self.assertEqual(len(self.w.state()['analyses']), 1)
        with patch('shared.video_workspace.configured', return_value=False):
            with self.assertRaises(WorkspaceError) as e:
                self.w.analyze({'sample_id': s['id'], 'question': '未配置模型', 'mode': 'llm'})
            self.assertEqual(e.exception.status, 503)

    def test_cancel_running_model_and_queued_job_never_publish(self):
        a = self.asset()
        s = self.sample(a)
        started, release = threading.Event(), threading.Event()
        def blocked(*args, **kwargs):
            started.set()
            release.wait(5)
            return {'answer': '协议桩', 'uncertainty': '协议测试', 'evidence': [{'frame_id': 'f1', 'observation': '协议桩'}]}
        with patch('shared.video_workspace.configured', return_value=True), patch('shared.video_workspace.ask_json', side_effect=blocked):
            job = self.w.analyze({'sample_id': s['id'], 'question': '测试取消', 'mode': 'llm'})
            self.assertTrue(started.wait(3))
            queued = self.w.sample(a['id'], {'count': 2})
            self.w.action(queued['id'], 'cancel')
            self.w.action(job['id'], 'cancel')
            with self.assertRaises(WorkspaceError):
                self.w.delete(a['id'])
            release.set()
            self.wait(job, 'cancelled')
            self.wait(queued, 'cancelled')
        self.assertFalse(self.w.state()['analyses'])
        self.assertEqual(len(self.w.state()['samples']), 1)
        self.wait(self.w.action(queued['id'], 'retry'))

    def test_restart_marks_unfinished_interrupted_and_hash_corruption(self):
        a = self.asset()
        with self.w.lock:
            self.w.save('job', {'id': 'simulated-crash', 'kind': 'sample', 'payload': {'asset_id': a['id'], 'count': 2, 'strategy': 'uniform-midpoint-v1'}, 'status': 'running', 'events': []})
        self.w.close()
        self.w = VideoWorkspace(self.tmp.name)
        self.assertEqual(self.w.job('simulated-crash')['status'], 'interrupted')
        self.wait(self.w.action('simulated-crash', 'retry'))
        (self.w.files / (a['id'] + a['suffix'])).write_bytes(b'changed')
        self.wait(self.w.sample(a['id'], {'count': 2}), 'failed')
        with self.assertRaises(WorkspaceError):
            self.w.media(a['id'])
