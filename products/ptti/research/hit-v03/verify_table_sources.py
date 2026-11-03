"""Link existing DEV table keyframes to now-complete, hash-verified local videos."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def main(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    dev = Path(os.environ['LOCALAPPDATA'])/'PTTI-Dev'
    scene_root = dev/'vision-v2/scene-bootstrap'
    scene = json.loads((scene_root/'scene_bootstrap_eval_manifest.json').read_text(encoding='utf-8'))
    download = json.loads((dev/'research-datasets/ExtendedOpenTTGames/DEV_VIDEO_DOWNLOAD_MANIFEST.json').read_text(encoding='utf-8'))
    entries = {e['game']: e for e in download['games'] if e['game'] in {'game_1', 'game_2', 'game_3'}}
    rows = []
    seen = set()
    for sample in scene['frame_results']:
        if sample['game'] not in entries:
            continue
        key = (sample['game'], sample['slot'])
        if key in seen:
            continue
        seen.add(key)
        source = entries[sample['game']]
        image = scene_root/sample['image']
        original_sha = hashlib.sha256(image.read_bytes()).hexdigest()
        if original_sha.upper() != sample['frame_sha256'].upper():
            raise ValueError('SCENE_KEYFRAME_CHANGED')
        target = output/f'{sample["game"]}-s{sample["slot"]:02d}.jpg'
        subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-nostdin', '-n', '-threads', '1', '-ss',
            f'{sample["timestamp_seconds"]:.3f}', '-i', source['video_path'], '-frames:v', '1',
            '-q:v', '2', '-threads', '1', str(target)], check=True)
        extracted_sha = hashlib.sha256(target.read_bytes()).hexdigest()
        rows.append({'game': sample['game'], 'slot': sample['slot'], 'timestamp_seconds': sample['timestamp_seconds'],
                     'original_image_sha256': original_sha, 'local_extraction_sha256': extracted_sha,
                     'video_sha256': source['sha256'], 'exact_jpeg_match': extracted_sha == original_sha,
                     'status': 'SOURCE_KEYFRAME_EXACTLY_VERIFIED' if extracted_sha == original_sha else 'NOT_VERIFIED'})
    report = {'scope': 'DEV_ONLY_TABLE_SOURCE_LINKAGE', 'rows': rows,
              'exact_matches': sum(r['exact_jpeg_match'] for r in rows), 'samples': len(rows),
              'limitation': 'Links detection frames to source; does not validate coarse bbox as physical table geometry'}
    (output/'table_source_verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({'exact_matches': report['exact_matches'], 'samples': report['samples']}))


if __name__ == '__main__':
    main(sys.argv[1])
