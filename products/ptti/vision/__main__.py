import argparse
import json
from pathlib import Path
from .config import VisionConfig, DATA_REVISION
from .doctor import doctor
from .runner import run_analysis

def main():
    parser = argparse.ArgumentParser(description='PTTI isolated local vision tools')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('doctor')
    benchmark = sub.add_parser('benchmark')
    benchmark.add_argument('--device', choices=['cuda', 'cpu'], default='cuda')
    analyze = sub.add_parser('analyze')
    analyze.add_argument('video', type=Path)
    analyze.add_argument('--gt', type=Path)
    analyze.add_argument('--device', choices=['cuda', 'cpu'], default='cuda')
    args = parser.parse_args(); config = VisionConfig.load()
    if args.command == 'doctor': print(json.dumps(doctor(config), ensure_ascii=False, indent=2)); return
    if args.command == 'benchmark':
        video = config.dataset_root / 'tabletennis/videos/match1_000.mp4'
        gt = config.dataset_root / 'tabletennis/all/match1/csv/000_ball.csv'
        source = dict(type='racketvision', provider='linfeng302/RacketVision', source_id='tabletennis/match1/000',
                      rights='research', rights_notes='Official test split; sparse annotations; revision ' + DATA_REVISION)
    else:
        video, gt = args.video, args.gt
        source = dict(type='local', rights='user_provided')
    result = run_analysis(video, source, gt, config, args.device, stage=lambda s: print('STAGE ' + s, flush=True))
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == '__main__': main()
