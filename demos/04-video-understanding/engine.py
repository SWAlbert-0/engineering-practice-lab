"""Validate sampled frames and optionally ask a configured multimodal model."""
import base64
import math
import time
from shared.model_client import ask_json


def run(question, frames, mode='offline', duration=0):
    if not isinstance(question, str) or not 1 <= len(question.strip()) <= 500:
        raise ValueError('问题应为1–500字。')
    if mode not in ('offline', 'llm'):
        raise ValueError('未知分析模式。')
    if not isinstance(duration, (int, float)) or isinstance(duration, bool) or not math.isfinite(duration) or not 0 < duration <= 600:
        raise ValueError('视频长度应在0–600秒之间。')
    if not isinstance(frames, list) or not 1 <= len(frames) <= 6:
        raise ValueError('请提交1–6张采样帧。')
    seen = set()
    for f in frames:
        if not isinstance(f, dict):
            raise ValueError('采样帧格式错误。')
        t, image = f.get('time'), f.get('image')
        if not isinstance(t, (int, float)) or isinstance(t, bool) or not math.isfinite(t) or not 0 <= t <= duration or t in seen:
            raise ValueError('采样时间无效或重复。')
        seen.add(t)
        if not isinstance(image, str) or not image.startswith('data:image/jpeg;base64,') or len(image) > 30000:
            raise ValueError('只接受不超过30KB的JPEG数据URL。')
        try:
            raw = base64.b64decode(image.split(',', 1)[1], validate=True)
        except ValueError:
            raise ValueError('帧图像编码无效。') from None
        if not raw.startswith(b'\xff\xd8') or not raw.endswith(b'\xff\xd9'):
            raise ValueError('帧图像不是有效的JPEG文件。')
    started = time.perf_counter()
    if mode == 'llm':
        data = ask_json('你是视频采样帧分析者。只依据提供的图像回答问题。返回 {"answer":回答,"evidence":[{"time":所提供采样秒数,"observation":可见现象}],"uncertainty":无法判断的部分}。'
                        '采样之间的事件、音频和不可见信息应说明无法确定。不要推断未展示的因果。',
                        {'question': question, 'duration': duration, 'sampled_times': sorted(seen)}, images=frames)
        if not isinstance(data.get('answer'), str) or not data['answer'].strip() or len(data['answer']) > 4000:
            raise ValueError('模型回答字段不完整。')
        evidence = data.get('evidence')
        if not isinstance(evidence, list) or len(evidence) > 12:
            raise ValueError('模型证据格式错误。')
        for e in evidence:
            if not isinstance(e, dict) or not isinstance(e.get('time'), (int, float)) or isinstance(e.get('time'), bool) or not math.isfinite(e['time']) or not any(abs(e['time']-t)<.1 for t in seen) or not isinstance(e.get('observation'), str) or not e['observation'].strip() or len(e['observation']) > 1500:
                raise ValueError('模型证据没有定位到已提供的采样时刻。')
        if not isinstance(data.get('uncertainty', ''), str):
            raise ValueError('模型不确定性字段错误。')
    else:
        data = {'answer': '已完成采样与时间戳校验。离线模式没有视觉模型，不能回答视频内容问题。',
                'evidence': [], 'uncertainty': '尚未执行内容理解；采样间事件、音频与因果均未判断。'}
    return {**data, 'question': question, 'mode': mode, 'provider': '多模态模型采样帧问答' if mode=='llm' else '离线采样校验（无视觉推理）',
            'sampled_times': sorted(seen), 'frame_count': len(frames), 'duration': duration,
            'duration_ms': round((time.perf_counter()-started)*1000, 2),
            'boundary': '只处理浏览器抽出的JPEG帧，不上传完整视频、不分析音频。尚未进行3B–7B本地模型轻量化、训练或两基准评测。'}
