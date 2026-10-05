"""Explicit opt-in, bounded official test fixture and BallTrack checkpoint download."""
import hashlib
import json
import sys
import urllib.request
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vision.config import VisionConfig, DATA_REVISION, MODEL_REVISION

def download(repo, kind, revision, relative, destination):
    api = f'https://huggingface.co/api/{kind}/{repo}/tree/{revision}/{relative.rsplit("/", 1)[0]}'
    listing = json.load(urllib.request.urlopen(api, timeout=60))
    entry = next(x for x in listing if x['path'] == relative)
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
    config = VisionConfig.load()
    for relative in ('tabletennis/videos/match1_000.mp4', 'tabletennis/all/match1/csv/000_ball.csv',
                     'tabletennis/info/test.json'):
        download('linfeng302/RacketVision', 'datasets', DATA_REVISION, relative, config.dataset_root / relative)
    download('linfeng302/RacketVision-Models', 'models', MODEL_REVISION,
             'checkpoints/balltrack_best.pth', config.model_root / 'balltrack_best.pth')
    print('Bounded official fixture ready. No other videos or module weights downloaded.')
