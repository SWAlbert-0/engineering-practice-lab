"""New projects: actual local computations and offline model protocol checks."""
import base64
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server
from shared import model_client


class RequirementsTests(unittest.TestCase):
    def test_trace_and_ambiguity_are_not_claimed_as_executed_tests(self):
        r = server.requirements.analyze(server.requirements.SAMPLE)
        ids = {q['id'] for q in r['requirements']}
        self.assertTrue(all(c['requirement'] in ids for c in r['cases']))
        self.assertTrue(any(i['kind'] == '可验证性' for i in r['issues']))
        self.assertTrue(all(c['status'] == '待完善' for c in r['cases']))

    def test_model_must_cover_exact_sources(self):
        with patch.object(server.requirements, 'ask_json', return_value={'requirements':[{'source':'不存在的需求','actor':'用户','title':'查看'}]}):
            with self.assertRaisesRegex(ValueError,'原文'):server.requirements.analyze('用户可以查看订单。','llm')

    def test_valid_model_extraction_is_checked_and_templated(self):
        with patch.object(server.requirements, 'ask_json', return_value={'requirements':[{'source':'用户可以查看订单','actor':'用户','title':'查看订单'}]}) as ask:
            r=server.requirements.analyze('用户可以查看订单。','llm')
        ask.assert_called_once();self.assertEqual(r['requirements'][0]['source'],'用户可以查看订单')
        self.assertEqual(r['cases'][0]['status'],'待完善')

    def test_compare_preserves_old_identifiers(self):
        r=server.requirements.compare('用户查看订单。\n管理员导出记录。','用户查看订单。\n管理员在5秒内导出记录。')
        self.assertEqual(r['changes'][0]['affected'],['REQ-002'])
        self.assertEqual(r['changes'][0]['kind'],'修改')

    def test_input_limits(self):
        for text in ['',None,'x\n'*41]:
            with self.subTest(text=str(text)[:20]):
                with self.assertRaises(ValueError):server.requirements.analyze(text)


class LiteratureTests(unittest.TestCase):
    def test_offline_does_not_call_a_model(self):
        with patch.object(server.literature,'ask_json',side_effect=AssertionError('network')):
            r=server.literature.run('外部反馈',['REACT-2022','REFLEXION-2023'])
        self.assertEqual(r['model_calls'],0)
        self.assertTrue(all(c['valid'] for c in r['claims']))
        self.assertTrue(all('review' not in c for c in r['claims']))

    def test_wrong_source_and_quote_are_detected(self):
        papers=server.literature.PAPERS[:1]
        checks=server.literature.validate_claims([{'text':'结论','paper':'missing','quote':'原文'},{'text':'结论','paper':papers[0]['id'],'quote':'不存在的内容'}],papers)
        self.assertFalse(any(c['valid'] for c in checks))

    def test_multi_calls_each_reader_then_synthesizes(self):
        def fake(system,payload):
            if 'paper' in payload:
                p=payload['paper'];return {'text':'关于'+p['title'],'paper':p['id'],'quote':p['note'].split('。')[0]}
            return {'claims':payload['evidence']}
        with patch.object(server.literature,'ask_json',side_effect=fake) as ask:
            r=server.literature.run('外部反馈',['REACT-2022','REFLEXION-2023'],'multi')
        self.assertEqual(ask.call_count,3);self.assertEqual(r['model_calls'],3)
        self.assertEqual(len(r['claims']),2)

    def test_single_call_rejects_unverifiable_citations(self):
        with patch.object(server.literature,'ask_json',return_value={'claims':[{'text':'内容','paper':'REACT-2022','quote':'编造的证据'}]}):
            with self.assertRaisesRegex(ValueError,'引用'):server.literature.run('反馈',['REACT-2022'],'single')


class VideoTests(unittest.TestCase):
    def frames(self):
        # The transport validator checks JPEG markers; decoding happens in browser.
        image='data:image/jpeg;base64,'+base64.b64encode(b'\xff\xd8transport fixture\xff\xd9').decode()
        return [{'time':1.0,'image':image},{'time':3.0,'image':image}]

    def test_offline_never_invents_a_visual_answer(self):
        with patch.object(server.video,'ask_json',side_effect=AssertionError('network')):
            r=server.video.run('是什么颜色？',self.frames(),duration=4)
        self.assertEqual(r['evidence'],[]);self.assertIn('不能回答',r['answer'])

    def test_model_must_cite_an_observed_time(self):
        with patch.object(server.video,'ask_json',return_value={'answer':'回答','evidence':[{'time':2,'observation':'事件'}]}):
            with self.assertRaisesRegex(ValueError,'时刻'):server.video.run('问题',self.frames(),'llm',4)

    def test_actual_multimodal_payload_is_forwarded(self):
        with patch.object(server.video,'ask_json',return_value={'answer':'回答','evidence':[{'time':1,'observation':'可见现象'}],'uncertainty':'帧间不确定'}) as ask:
            r=server.video.run('问题',self.frames(),'llm',4)
        self.assertEqual(len(ask.call_args.kwargs['images']),2)
        self.assertEqual(r['evidence'][0]['time'],1)

    def test_invalid_frames_and_duration(self):
        for frames,duration in [(self.frames(),float('nan')),([self.frames()[0]]*2,4),([{'time':1,'image':'https://example.com/a.jpg'}],4),([],4)]:
            with self.subTest(duration=duration):
                with self.assertRaises(ValueError):server.video.run('问题',frames,duration=duration)


class ClientTests(unittest.TestCase):
    def test_missing_configuration_is_explicit(self):
        with patch.dict('os.environ',{},clear=True):
            self.assertFalse(model_client.configured())
            with self.assertRaisesRegex(ValueError,'尚未配置'):model_client.ask_json('system',{})

    def test_capability_does_not_expose_keys(self):
        with patch.dict('os.environ',{'LAB_LLM_BASE_URL':'https://example.com/v1','LAB_LLM_MODEL':'model','LAB_LLM_API_KEY':'secret-not-public'},clear=True):
            self.assertTrue(model_client.configured())


if __name__=='__main__':unittest.main()
