"""Sequential, resumable worker orchestration. No persistent model process."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time


def main(folder, jobs_filename='jobs.json'):
    folder = Path(folder)
    if jobs_filename not in {'jobs.json', 'jobs_with_event_diagnostics.json'}:
        raise ValueError('UNKNOWN_JOB_MANIFEST')
    jobs = json.loads((folder/jobs_filename).read_text(encoding='utf-8'))
    product = Path(__file__).resolve().parents[2]
    python = product/'vision_worker/.venv/Scripts/python.exe'
    verified_sources = set()
    for job in jobs:
        request = json.loads(Path(job['request']).read_text(encoding='utf-8'))
        source_path = Path(request['video_path'])
        source_key = (str(source_path), request['video_sha256'])
        if source_key in verified_sources:
            continue
        if request['game'] not in {'game_1', 'game_2', 'game_3'} or source_path.name != request['game']+'.mp4':
            raise ValueError('NON_DEV_INPUT_REJECTED')
        source_digest = hashlib.sha256()
        with source_path.open('rb') as source_stream:
            for block in iter(lambda: source_stream.read(1024*1024), b''):
                source_digest.update(block)
        if source_digest.hexdigest() != request['video_sha256']:
            raise ValueError('SOURCE_CHANGED_CACHE_REUSE_FORBIDDEN')
        verified_sources.add(source_key)
        print(f'SOURCE_VERIFIED {request["game"]}', flush=True)
    for index, job in enumerate(jobs):
        request = Path(job['request'])
        result = Path(job['output'])
        digest = hashlib.sha256(request.read_bytes()).hexdigest()
        if result.exists():
            cached = json.loads(result.read_text(encoding='utf-8'))
            if cached['status'] != 'COMPLETE' or cached['request_sha256'] != digest:
                raise RuntimeError('INVALID_CHECKPOINT_DO_NOT_REUSE')
            planned = json.loads(request.read_text(encoding='utf-8'))
            if [row['source_frame'] for row in cached['frames']] != sorted(set(planned['frames'])):
                raise RuntimeError('INCOMPLETE_OR_DUPLICATE_CACHED_FRAME_SEQUENCE')
            print(f'CACHE {index+1}/{len(jobs)}', flush=True)
            continue
        log = result.with_suffix(f'.attempt-{time.time_ns()}.log')
        with log.open('w', encoding='utf-8') as stream:
            completed = subprocess.run([str(python), str(Path(__file__).with_name('player_worker.py')),
                                        str(request), str(result)], stdout=stream, stderr=subprocess.STDOUT)
        if completed.returncode:
            print(f'BLOCKED {index+1}/{len(jobs)} log={log}', flush=True)
            raise RuntimeError('WORKER_FAILED_CHECKPOINT_PRESERVED')
        print(f'COMPLETE {index+1}/{len(jobs)}', flush=True)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else 'jobs.json')
