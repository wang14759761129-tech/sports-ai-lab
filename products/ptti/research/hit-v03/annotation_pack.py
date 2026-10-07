"""Small evidence pack; no CVAT server, no invented human-confirmed labels."""
import json
import os
from pathlib import Path
import subprocess
import sys


def main(audit_folder, output):
    audit_folder, output = Path(audit_folder), Path(output)
    output.mkdir(parents=True, exist_ok=False)
    selected = {}
    dev = Path(os.environ['LOCALAPPDATA'])/'PTTI-Dev'
    for game in (1, 2, 3):
        data = json.loads((audit_folder/f'game_{game}_diagnostics.json').read_text(encoding='utf-8'))
        baseline_path = next((dev/f'evidence/hit_event_v0_2/full_dev/game_{game}').glob('*/full_dev_hit_evaluation.json'))
        baseline = json.loads(baseline_path.read_text(encoding='utf-8'))
        for fp in data['stages']['raw']['fp_diagnostics']:
            for label in fp['labels']:
                if label == 'PLAYER_PROXIMITY_UNKNOWN':
                    continue
                rows = selected.setdefault(f'RAW_FP_{label}', [])
                if sum(r['game'] == game for r in rows) < 2 and len(rows) < 5:
                    rows.append({'game': game, 'kind': label, 'timestamp_ms': fp['timestamp_ms'],
                                 'candidate_id': fp['candidate_id'], 'video_path': baseline['video_path'],
                                 'video_sha256': baseline['video_sha256'], 'annotation_state': 'REVIEW_REQUIRED',
                                 'interpretation': fp['interpretation']})
        for fn in data['raw_fn']:
            label = 'CONTEXT_PRESENT' if fn['ball_context']['ball_context_available'] else 'CONTEXT_MISSING'
            rows = selected.setdefault(f'RAW_FN_{label}', [])
            if sum(r['game'] == game for r in rows) < 2 and len(rows) < 5:
                rows.append({'game': game, 'kind': label, 'timestamp_ms': fn['event']['timestamp_ms'],
                             'event_id': fn['event']['event_id'], 'video_path': baseline['video_path'],
                             'video_sha256': baseline['video_sha256'], 'annotation_state': 'NATIVE_STROKE_GT'})
        for kind in ['STROKE', 'BOUNCE', 'NET']:
            rows = selected.setdefault(f'NATIVE_{kind}', [])
            for event in data['event_kinematics']:
                if event['event_type'] == kind and sum(r['game'] == game for r in rows) < 2 and len(rows) < 5:
                    rows.append({'game': game, 'kind': kind, 'timestamp_ms': event['timestamp_ms'],
                                 'event_id': event['event_id'], 'native_label': event['native_label'],
                                 'video_path': baseline['video_path'], 'video_sha256': baseline['video_sha256'],
                                 'annotation_state': 'NATIVE_EVENT_GT'})
    tasks = []
    for group, examples in selected.items():
        for index, example in enumerate(examples):
            filename = f'{group}-{index+1:02d}.mp4'
            start = max(0, example['timestamp_ms']/1000-.5)
            subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-threads', '1',
                            '-ss', str(start), '-i', example['video_path'], '-t', '1', '-an',
                            '-vf', 'scale=960:-2,fps=30', '-c:v', 'libx264', '-threads', '1',
                            '-preset', 'veryfast', '-crf', '23', str(output/filename)], check=True)
            tasks.append({**example, 'group': group, 'clip': filename, 'clip_start_ms': start*1000,
                          'event_clip_timestamp_ms': example['timestamp_ms']-start*1000,
                          'source_fps': 120, 'clip_fps': 30,
                          'warning': '30 FPS review clip is not frame-accurate source GT; use original timestamps'})
            print(filename, flush=True)
    pack = {'name': 'PTTI Annotation Pack v0.1', 'license': 'CC BY-NC-SA 4.0', 'commercial_use': False,
            'dataset': 'Extended OpenTTGames', 'split': 'TRAIN DEV game_1-3', 'cvat_server': 'NOT_INSTALLED',
            'labels': ['BALL', 'HIT', 'BOUNCE', 'NET', 'NEAR_PLAYER', 'FAR_PLAYER', 'UNCERTAIN'],
            'tasks': tasks, 'proximity_labels': 'DIAGNOSTIC_HINTS_NOT_CAUSAL_GROUND_TRUTH'}
    (output/'annotation_pack.json').write_text(json.dumps(pack, indent=2), encoding='utf-8')
    (output/'labels.json').write_text(json.dumps([{'name': label, 'attributes': [
        {'name': 'review_status', 'input_type': 'select', 'mutable': True,
         'values': ['SUGGESTED', 'CONFIRMED', 'REJECTED', 'UNCERTAIN']}]} for label in pack['labels']], indent=2), encoding='utf-8')
    (output/'START-HERE.txt').write_text('仅供非商业研究复核。视频属于 Extended OpenTTGames，CC BY-NC-SA 4.0。\n'
        '将各 MP4 导入 CVAT 视频任务，使用 labels.json 创建标签。annotation_pack.json 保留源时间与证据。\n'
        '邻近事件标签不是误报原因真值。请核查前后过程后再确认。30 FPS 预览不能替代 120 FPS 原视频的精确事件帧。\n', encoding='utf-8')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
