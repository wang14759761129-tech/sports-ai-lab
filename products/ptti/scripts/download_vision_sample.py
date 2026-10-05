"""Explicit opt-in, bounded official test fixture and BallTrack checkpoint download."""
import hashlib
import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vision.config import VisionConfig, DATA_REVISION, MODEL_REVISION

def tree_entry(repo, kind, revision, relative):
    api = f'https://huggingface.co/api/{kind}/{repo}/tree/{revision}/{relative.rsplit("/", 1)[0]}?expand=true'
    visited=set()
    while api and api not in visited:
        visited.add(api)
        with urllib.request.urlopen(api, timeout=60) as response:
            listing = json.load(response)
            link=response.headers.get('Link','')
        entry=next((x for x in listing if x.get('path')==relative),None)
        if entry:
            return entry
        match=re.search(r'<([^>]+)>;\s*rel="next"',link)
        api=match.group(1) if match else None
    raise RuntimeError(f'Official asset is missing at pinned revision: {relative}')

def download(repo, kind, revision, relative, destination):
    entry = tree_entry(repo, kind, revision, relative)
    expected = entry.get('lfs', {}).get('oid')
    if destination.exists():
        if destination.stat().st_size == entry['size'] and (not expected or hashlib.sha256(destination.read_bytes()).hexdigest() == expected):
            return
        raise RuntimeError(f'Existing file does not match official asset: {destination}')
    destination.parent.mkdir(parents=True, exist_ok=True)
    url = f'https://huggingface.co/{"datasets/" if kind == "datasets" else ""}{repo}/resolve/{revision}/{relative}'
    temporary = destination.with_suffix(destination.suffix + '.partial')
    print(f'Download {relative}: {entry["size"] / 1024**2:.1f} MiB', flush=True)
    digest = hashlib.sha256()
    with urllib.request.urlopen(url, timeout=120) as response, temporary.open('wb') as output:
        while chunk := response.read(1024 * 1024):
            output.write(chunk); digest.update(chunk)
    if temporary.stat().st_size != entry['size'] or (expected and digest.hexdigest() != expected):
        raise RuntimeError('Download size / SHA256 mismatch; partial file retained')
    temporary.rename(destination)

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description='Download only pinned, hash-verified RacketVision fixtures')
    parser.add_argument('--benchmark-suite',action='store_true',help='download a bounded test-split suite')
    parser.add_argument('--suite-clips',type=int,default=5,choices=range(5,11),metavar='5..10')
    args=parser.parse_args()
    config = VisionConfig.load()
    repo='linfeng302/RacketVision'
    info='tabletennis/info/test.json'
    if args.benchmark_suite:
        download(repo,'datasets',DATA_REVISION,info,config.dataset_root/info)
        split=json.loads((config.dataset_root/info).read_text(encoding='utf-8'))
        grouped={}
        for match,rally in split:
            grouped.setdefault(match,[]).append(rally)
        selected=[]
        # Round-robin across test-set matches before adding a second rally from any match.
        for round_index in range(max(map(len,grouped.values()))):
            for match,rallies in grouped.items():
                if round_index < len(rallies):
                    selected.append((match,rallies[round_index]))
                    if len(selected)==args.suite_clips:
                        break
            if len(selected)==args.suite_clips:
                break
        if len(selected)<args.suite_clips:
            raise RuntimeError(f'Test split contains only {len(selected)} selectable clips')
        for match,rally in selected:
            video=f'tabletennis/videos/{match}_{rally}.mp4'
            gt=f'tabletennis/all/{match}/csv/{rally}_ball.csv'
            download(repo,'datasets',DATA_REVISION,video,config.dataset_root/video)
            download(repo,'datasets',DATA_REVISION,gt,config.dataset_root/gt)
        manifest={'provider':repo,'dataset_revision':DATA_REVISION,'split':'tabletennis/info/test.json',
                  'selection_policy':'round-robin by match, then rally order','source_ids':[f'tabletennis/{m}/{r}' for m,r in selected]}
        config.dataset_root.joinpath('benchmark-suite-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
        print(json.dumps(manifest,indent=2))
    else:
        for relative in ('tabletennis/videos/match1_000.mp4', 'tabletennis/all/match1/csv/000_ball.csv', info):
            download(repo, 'datasets', DATA_REVISION, relative, config.dataset_root / relative)
        print('Bounded official fixture ready. No other videos or module weights downloaded.')
    # The BallTrack checkpoint remains a separate explicit download even for a suite.
    download('linfeng302/RacketVision-Models', 'models', MODEL_REVISION,
             'checkpoints/balltrack_best.pth', config.model_root / 'balltrack_best.pth')
