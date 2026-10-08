import json
import math
import os
import subprocess
from fractions import Fraction
from pathlib import Path

QUALITY_RULES = {'minimum_height': 720, 'vision_height': 1080,
                 'vision_fps': 50, 'high_speed_fps': 100}

def classify(meta):
    h, fps = meta['height'], meta['fps']
    level = 'LOW' if h < QUALITY_RULES['minimum_height'] else 'STANDARD'
    if h >= QUALITY_RULES['vision_height'] and fps >= QUALITY_RULES['vision_fps']:
        level = 'VISION'
    if h >= QUALITY_RULES['vision_height'] and fps >= QUALITY_RULES['high_speed_fps']:
        level = 'HIGH_SPEED'
    return {'level': level, 'suitability': 'LIMITED' if level in ('LOW', 'STANDARD') else 'GOOD',
            'explanation': '仅为输入条件分级，不保证模型追踪准确率。', 'rules': QUALITY_RULES}

def video_metadata(path):
    path = Path(path).resolve()
    if path.suffix.lower() not in {'.mp4', '.mov', '.mkv', '.avi'}:
        raise ValueError('支持 MP4、MOV、MKV、AVI 本地视频')
    if not path.is_file():
        raise ValueError('视频文件不存在')
    result = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format',
                             '-of', 'json', str(path)], capture_output=True, text=True, encoding='utf-8',
                            timeout=60, check=True, creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    try:
        data = json.loads(result.stdout)
        stream = next((s for s in data.get('streams', []) if s.get('codec_type') == 'video'), None)
    except (ValueError, TypeError, AttributeError):
        raise ValueError('无法读取有效的视频元数据') from None
    if not stream:
        raise ValueError('文件没有可读取的视频轨道')
    format_data = data.get('format') or {}
    try:
        fps = float(Fraction(stream.get('avg_frame_rate', '0/1')))
        duration_text = stream.get('duration')
        if duration_text in (None, '', 'N/A'):
            duration_text = format_data.get('duration', 0)
        duration = float(duration_text)
        width, height = int(stream['width']), int(stream['height'])
    except (ValueError, TypeError, KeyError, ZeroDivisionError, OverflowError):
        raise ValueError('无法读取有效的视频帧率、时长或分辨率') from None
    if not math.isfinite(fps) or fps <= 0:
        raise ValueError('无法读取有效帧率')
    if not math.isfinite(duration) or duration <= 0 or width <= 0 or height <= 0:
        raise ValueError('无法读取有效的视频时长或分辨率')
    try:
        bitrate = int(format_data.get('bit_rate', 0))
    except (ValueError, TypeError):
        bitrate = None
    rotation = next((item.get('rotation') for item in stream.get('side_data_list', [])
                     if item.get('rotation') is not None), stream.get('tags', {}).get('rotate', 0))
    try:
        orientation_degrees = int(round(float(rotation))) % 360
    except (TypeError, ValueError):
        orientation_degrees = None
    audio_streams = [dict(codec=item.get('codec_name'), sample_rate=item.get('sample_rate'),
                          channels=item.get('channels'), channel_layout=item.get('channel_layout'))
                     for item in data['streams'] if item.get('codec_type') == 'audio']
    return dict(width=width, height=height, fps=fps,
                duration=duration, codec=stream['codec_name'],
                bitrate=bitrate,
                frame_count=int(stream['nb_frames']) if stream.get('nb_frames', '').isdigit() else None,
                aspect_ratio=stream.get('display_aspect_ratio'),
                orientation_degrees=orientation_degrees,
                pixel_format=stream.get('pix_fmt'), profile=stream.get('profile'),
                format_name=format_data.get('format_name'), audio_streams=audio_streams,
                rate_variable=stream.get('r_frame_rate') != stream.get('avg_frame_rate'))

def normalize(path, destination, meta):
    # Preserve resolution; high quality encoding. Never modify the user's original file.
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(path), '-map', '0:v:0',
                    '-map', '0:a?', '-c:v', 'libx264', '-crf', '16', '-preset', 'fast',
                    '-r', str(meta['fps']), '-fps_mode', 'cfr', '-c:a', 'aac',
                    '-movflags', '+faststart', '-n', str(destination)], check=True, timeout=3600)
    return destination
