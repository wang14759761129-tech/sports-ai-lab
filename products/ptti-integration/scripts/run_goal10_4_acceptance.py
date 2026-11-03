#!/usr/bin/env python3
"""Read-only San comparison and reproducible SIMULATED_ONLY training acceptance."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from quick_annotation import QuickAnnotationError, adapt_quick_annotation, summarize_quick_annotation

NODE_COMPARE = r'''
import {readFileSync} from 'node:fs';
import {pathToFileURL} from 'node:url';
const api = await import(pathToFileURL(process.argv[1]));
const payload = JSON.parse(readFileSync(process.argv[2], 'utf8'));
const imported = api.importQuickAnnotationDraft(payload);
if (!imported.ok) throw new Error(JSON.stringify(imported));
const points = imported.value.points;
const summary = api.summarizeLocalQuickPoints(points, []);
console.log(JSON.stringify({summary,
  imported_duration_checked_known_winner_ranges: points.filter(p => p.winner !== 'UNKNOWN'
    && p.start_seconds !== null && p.end_seconds !== null).length,
  imported_observed_stage_count: points.filter(p => p.observed_rally_stage && p.observed_rally_stage !== 'UNKNOWN').length,
  current_session_media_loaded: false}));
'''

NODE_VALIDATE = r'''
import {readFileSync} from 'node:fs';
import {pathToFileURL} from 'node:url';
const api = await import(pathToFileURL(process.argv[1]));
console.log(JSON.stringify(api.validateQuickAnnotationInput(JSON.parse(readFileSync(process.argv[2], 'utf8')))));
'''


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--san-worktree', type=Path, required=True, help='read-only local Web worktree')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'generated/goal10-4-acceptance')
    args = parser.parse_args()
    module = args.san_worktree / 'products/ptti-web/src/local-video-review.mjs'
    san_head = subprocess.check_output(['git', '-C', str(args.san_worktree), 'rev-parse', 'HEAD'], text=True).strip()
    san_status = subprocess.check_output(['git', '-C', str(args.san_worktree), 'status', '--porcelain'], text=True).strip()
    result = {'dataset_class': 'SIMULATED_ONLY', 'san': {'head': san_head, 'worktree_clean': not san_status,
              'consumer_module_sha256': sha(module)}, 'engine_sha256': sha(ROOT / 'quick_annotation.py'),
              'golden_comparisons': [], 'complete_games': [], 'unexpected_differences': []}
    for version in ('0.1', '0.2'):
        path = ROOT / f'fixtures/quick-annotation-v{version}-valid-simulated.json'
        payload = load(path)
        assert payload['dataset_class'] == 'SIMULATED_ONLY'
        draft = adapt_quick_annotation(payload)
        stats = summarize_quick_annotation(draft)
        actual = json.loads(subprocess.check_output(['node', '--input-type=module', '-e', NODE_COMPARE,
                                                     str(module.resolve()), str(path.resolve())], text=True))
        expected = {
            'total_points': stats['sample']['point_count'],
            'known_winner_points': stats['sample']['score_known_count'],
            'score_by_winner': {'PLAYER_A': stats['metrics']['recorded_point_wins']['numerator']['player'],
                                'PLAYER_B': stats['metrics']['recorded_point_wins']['numerator']['opponent']},
            'reviewable_points': 0, 'independently_verified_media_points': 0,
            'reviewable_by_winner': {'PLAYER_A': 0, 'PLAYER_B': 0},
            'known_serve_side': stats['metrics']['tactical_fields']['serve_side']['denominator'],
            'known_third_ball_attack': stats['metrics']['third_ball_attack_rate']['denominator'],
        }
        differences = {key: {'engine_expected': value, 'san_actual': actual['summary'].get(key)}
                       for key, value in expected.items() if actual['summary'].get(key) != value}
        for name, expected_value, actual_value in (
            ('imported_range_preservation', stats['metrics']['time_range_coverage']['numerator'], actual['imported_duration_checked_known_winner_ranges']),
            ('imported_stage_preservation', stats['rally_stage_distribution']['denominator'], actual['imported_observed_stage_count']),
        ):
            if expected_value != actual_value:
                differences[name] = {'engine_expected': expected_value, 'san_actual': actual_value}
        record = {'input_contract_version': payload['contract_version'], 'input_sha256': sha(path),
                  'input_fixture': path.relative_to(ROOT).as_posix(), 'status': 'PASS' if not differences else 'FAIL',
                  'expected_shared_counts': expected, 'san_result': actual,
                  'engine_duration_checked_ranges': stats['metrics']['time_range_coverage']['numerator'],
                  'engine_stage': stats['rally_stage_distribution'],
                  'independently_verified_source_count': 0,
                  'source_count_is_not_media_point_count': True,
                  'not_consumed_by_san': ['statistics sidecar', 'serve/receive win rates',
                    'third-ball success/conversion', 'key-point rates', 'configurable sample-status policy',
                    'aggregated observed-stage distribution']}
        result['golden_comparisons'].append(record)
        if differences:
            result['unexpected_differences'].append({'input': payload, 'differences': differences})
    for name in ('complete-11-9', 'deuce-12-10'):
        path = ROOT / f'fixtures/goal10-4-acceptance/{name}.json'
        payload = load(path)
        assert payload['dataset_class'] == 'SIMULATED_ONLY'
        draft = adapt_quick_annotation(payload)
        result['complete_games'].append({'name': name, 'input_sha256': sha(path),
            'stats': summarize_quick_annotation(draft),
            'trace': [{'point_id': p['point_id'], 'score_before': p['score_before_player_opponent'],
                       'server': p['protocol_fields']['server'], 'winner': p['protocol_fields']['point_winner']}
                      for p in draft['points']]})
    negative = ROOT / 'fixtures/goal10-4-acceptance/post-game-invalid.json'
    rejected_code = None
    try:
        adapt_quick_annotation(load(negative))
    except QuickAnnotationError as exc:
        rejected_code = exc.code
    san_negative = json.loads(subprocess.check_output(['node', '--input-type=module', '-e', NODE_VALIDATE,
                                                     str(module.resolve()), str(negative.resolve())], text=True))
    result['terminal_validation'] = {'input_fixture': negative.relative_to(ROOT).as_posix(),
        'input_sha256': sha(negative), 'integration_rejection': rejected_code, 'san_actual': san_negative,
        'aligned': rejected_code == 'GAME_ALREADY_ENDED' and san_negative.get('ok') is False,
        'minimum_handoff': 'San must reject a new point when a complete known prior score has ended the game; do not infer completion across gaps/unknown winners.'}
    result['status'] = ('FAIL' if result['unexpected_differences'] or rejected_code != 'GAME_ALREADY_ENDED'
                        else 'PASS' if result['terminal_validation']['aligned']
                        else 'COUNT_BASELINES_PASS_VALIDATION_ALIGNMENT_PENDING')
    result['limitations'] = ['All inputs are SIMULATED_ONLY; no actual video session was loaded.',
        'Range-valid, session-playable, independently verified sources and native playback are separate evidence.',
        'Quick snapshots are recomputed on demand; no DB score-to-Quick revision mapping is implemented.',
        'M2 active queues use 1s polling and 2.5s validation timeout; background throttling can delay detection.',
        'No browser rendering, Windows playback, Vision, public rights or release acceptance is inferred.']
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / 'acceptance.json'
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f"{result['status']}: 2 Golden comparisons, 2 full simulated games; output={output}")
    return 1 if result['status'] == 'FAIL' else 0


if __name__ == '__main__':
    raise SystemExit(main())
