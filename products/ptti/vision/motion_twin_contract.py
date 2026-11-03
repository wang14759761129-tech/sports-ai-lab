"""Local-only pose and coach evidence contracts. No inference or diagnosis."""
from __future__ import annotations
import math
import re

SCHEMA = 'ptti.pose-evidence/1'
TOPOLOGIES = {'MEDIAPIPE_POSE_33': 33, 'HALPE_26': 26}

def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)

def validate_pose(record):
    if not isinstance(record, dict) or record.get('schema') != SCHEMA:
        raise ValueError('Invalid pose schema')
    if record.get('source') != 'MODEL_INFERENCE' or record.get('coordinate_space') != 'NORMALIZED_IMAGE_2D':
        raise ValueError('Pose must be measured 2D inference, not simulated')
    identity = record.get('video_sha256')
    if not isinstance(identity, str) or not re.fullmatch(r'[a-f0-9]{64}', identity):
        raise ValueError('Invalid video identity')
    topology = record.get('topology')
    if topology not in TOPOLOGIES:
        raise ValueError('Unknown topology')
    model = record.get('model')
    if not isinstance(model, dict) or not isinstance(model.get('name'), str) or not model['name'].strip() or not re.fullmatch(r'[a-f0-9]{64}', model.get('sha256', '')):
        raise ValueError('Missing model provenance')
    duration = record.get('duration_seconds')
    if not _finite(duration) or duration <= 0:
        raise ValueError('Invalid duration')
    frames = record.get('frames')
    if not isinstance(frames, list) or not frames:
        raise ValueError('No measured frames')
    previous = -1
    for frame in frames:
        t = frame.get('time_seconds') if isinstance(frame, dict) else None
        if not _finite(t) or t < 0 or t > duration or t <= previous:
            raise ValueError('Invalid frame time')
        previous = t
        points = frame.get('landmarks')
        if not isinstance(points, list) or len(points) != TOPOLOGIES[topology]:
            raise ValueError('Topology and point count mismatch')
        for point in points:
            if point is None:
                continue
            if not isinstance(point, dict) or set(point) != {'x','y','confidence'}:
                raise ValueError('Invalid point')
            x, y, confidence = point['x'], point['y'], point['confidence']
            if not all(_finite(v) for v in (x,y,confidence)) or not 0 <= confidence <= 1:
                raise ValueError('Invalid point value')
    return record

def angle_degrees(a, vertex, b, width, height, minimum_confidence=0.5):
    """Image-plane angle only; invisible, missing or degenerate points return None."""
    if not _finite(width) or not _finite(height) or width <= 0 or height <= 0:
        raise ValueError('Invalid frame dimensions')
    if not _finite(minimum_confidence) or not 0 <= minimum_confidence <= 1:
        raise ValueError('Invalid threshold')
    for p in (a, vertex, b):
        if not isinstance(p, dict) or not all(_finite(p.get(k)) for k in ('x','y','confidence')) or not minimum_confidence <= p['confidence'] <= 1:
            return None
    u=((a['x']-vertex['x'])*width, (a['y']-vertex['y'])*height); v=((b['x']-vertex['x'])*width, (b['y']-vertex['y'])*height)
    n=math.hypot(*u)*math.hypot(*v)
    if n < 1e-12:
        return None
    return math.degrees(math.acos(max(-1,min(1,(u[0]*v[0]+u[1]*v[1])/n))))

def validate_rally(rally, duration, video_sha256):
    if not isinstance(rally,dict) or rally.get('video_sha256') != video_sha256:
        raise ValueError('Rally video mismatch')
    start,end=rally.get('start_seconds'),rally.get('end_seconds')
    if not all(_finite(x) for x in (start,end,duration)) or duration <= 0 or start < 0 or end <= start or end > duration:
        raise ValueError('Invalid rally bounds')
    if rally.get('source') != 'MANUAL_USER_RECORDED':
        raise ValueError('Rally provenance required')
    return start,end

def replay_action(current_time, start, end):
    if not all(_finite(x) for x in (current_time,start,end)) or start < 0 or end <= start:
        raise ValueError('Invalid replay time')
    return 'PAUSE' if current_time >= end else 'CONTINUE'

def evidence_limited_observation(points):
    if not points or any(p is None or p.get('confidence',0) < 0.5 for p in points):
        return '这个机位或关键点置信度不足，暂不能判断。'
    return '可查看检测到的二维关键点；技术原因和效果仍需人工复核。'
