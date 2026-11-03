import copy
import json
import sys
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from quick_annotation import QuickAnnotationError, adapt_quick_annotation
from review_targets import build_review_targets


def sample():
    return json.loads((ROOT / 'fixtures/review-targets-11-8-input.json').read_text(encoding='utf-8'))


class ReviewTargetsTests(unittest.TestCase):
    def test_golden_full_game_and_two_perspectives(self):
        result = build_review_targets(sample())
        self.assertEqual(result, json.loads((ROOT / 'fixtures/review-targets-11-8-output.json').read_text(encoding='utf-8')))
        a, b = result['athletes']
        self.assertEqual((a['score']['won_count'], a['score']['lost_count'], a['score']['denominator']), (11, 8, 19))
        self.assertEqual((b['score']['won_count'], b['score']['lost_count']), (8, 11))
        self.assertEqual(a['score']['point_ids']['won'], b['score']['point_ids']['lost'])
        self.assertEqual(result['sample']['game_counts']['1']['point_count'], 19)
        self.assertEqual(result['time_range_coverage']['numerator'], 12)
        self.assertEqual(result['unknown_stage_count'], 2)
        self.assertEqual((a['service']['won_count'], a['service']['lost_count']), (6, 4))
        self.assertEqual((b['service']['won_count'], b['service']['lost_count']), (4, 5))
        target = next(t for t in result['review_targets'] if t['subject_role'] == 'player' and t['observed_rally_stage'] == 'END_AFTER_3_4_CONTACTS')
        self.assertEqual((target['lost_count'], target['denominator'], target['unknown_count']), (3, 3, 2))
        self.assertEqual(target['point_ids'], [sample()['points'][n-1]['point_id'] for n in (2, 4, 6)])
        self.assertLessEqual(len(result['observations']), 2)

    def test_every_count_is_traceable_partition_without_media_promotion(self):
        payload = sample()
        result = build_review_targets(payload)
        all_ids = {p['point_id'] for p in payload['points']}
        for athlete in result['athletes']:
            for metric in [athlete['score'], athlete['service'], *athlete['observed_stages'].values()]:
                ids = metric['point_ids']
                self.assertEqual(set(ids['valid']), set(ids['won']) | set(ids['lost']))
                self.assertFalse(set(ids['won']) & set(ids['lost']))
                self.assertEqual(set(ids['valid']) | set(ids['unknown']) | set(ids['excluded']), all_ids)
                self.assertEqual(metric['denominator'] + metric['unknown_count'] + metric['excluded_count'], 19)
                self.assertEqual(metric['won_count'] + metric['lost_count'], metric['denominator'])
        for target in result['review_targets']:
            self.assertEqual(target['lost_count'], len(target['point_ids']))
            self.assertEqual(target['playback_eligibility'], 'NOT_EVALUATED_CURRENT_SESSION')
            self.assertEqual(target['evidence_status'], 'SIMULATED_ONLY')
        self.assertEqual(result['dataset']['rights_status'], 'UNKNOWN')
        self.assertIsNone(result['dataset']['timeline_id'])
        self.assertEqual(result['dataset']['vision_status'], 'NOT_TESTED')

    def test_unknown_server_not_assigned_to_either_player(self):
        data = sample()
        data['rules_context']['games'][0].update(coverage='PARTIAL_OR_UNKNOWN', first_server='unknown')
        result = build_review_targets(data)
        self.assertEqual(result['unknown_server_count'], 19)
        for athlete in result['athletes']:
            self.assertEqual(athlete['service']['denominator'], 0)
            self.assertEqual(athlete['service']['unknown_count'], 19)
            self.assertEqual(athlete['score']['denominator'], 19)

    def test_deuce_service_rotation_uses_existing_rules(self):
        data = sample()
        base = data['points'][0]
        data['points'] = []
        for n in range(1, 23):
            p = copy.deepcopy(base)
            p.update(point_id=base['point_id'].rsplit('p', 1)[0] + f'p{n:03d}', winner='player' if n % 2 or n > 20 else 'opponent', rally_start_ms=None, rally_end_ms=None)
            data['points'].append(p)
        draft = adapt_quick_annotation(data)
        self.assertEqual([p['protocol_fields']['server'] for p in draft['points'][20:]], ['player', 'opponent'])
        result = build_review_targets(data)
        self.assertEqual([a['service']['denominator'] for a in result['athletes']], [11, 11])
        self.assertEqual(result['athletes'][0]['score']['won_count'], 12)

    def test_winner_edit_changes_counts_hash_and_target_membership(self):
        data = sample()
        before = build_review_targets(data)
        data['points'][0]['winner'] = 'opponent'
        after = build_review_targets(data)
        self.assertNotEqual(before['canonical_input_sha256'], after['canonical_input_sha256'])
        self.assertEqual(after['athletes'][0]['score']['denominator'], 19)
        self.assertEqual((after['athletes'][0]['score']['won_count'], after['athletes'][0]['score']['lost_count']), (10, 9))
        stage = after['athletes'][0]['observed_stages']['END_AFTER_1_2_CONTACTS']
        self.assertEqual((stage['won_count'], stage['lost_count']), (10, 1))
        self.assertIn(data['points'][0]['point_id'], stage['point_ids']['lost'])
        self.assertNotIn(data['points'][0]['point_id'], stage['point_ids']['won'])

    def test_zero_denominator_small_sample_and_configurable_threshold(self):
        data = sample()
        data['points'] = data['points'][:3]
        self.assertEqual(build_review_targets(data)['athletes'][0]['score']['sample_status'], 'INSUFFICIENT_SAMPLE')
        self.assertEqual(build_review_targets(data, display_caution_threshold=3)['athletes'][0]['score']['sample_status'], 'DESCRIPTIVE_ONLY')
        for point in data['points']:
            point['winner'] = 'unknown'
        result = build_review_targets(data)
        self.assertEqual(result['athletes'][0]['score']['sample_status'], 'NOT_ESTIMABLE')
        self.assertEqual(result['athletes'][0]['score']['unknown_count'], 3)
        self.assertEqual(result['review_targets'], [])

    def test_v01_has_no_inferred_stage_and_unknown_winner_excluded(self):
        data = sample()
        data['contract_version'] = 'ptti.quick-annotation/0.1'
        for point in data['points']:
            del point['observed_rally_stage']
        result = build_review_targets(data)
        self.assertEqual(result['unknown_stage_count'], 19)
        self.assertEqual(result['review_targets'], [])
        self.assertEqual(result['athletes'][0]['score']['denominator'], 19)

    def test_missing_times_do_not_delete_score_or_stage_records(self):
        data = sample()
        for point in data['points']:
            point['rally_start_ms'] = point['rally_end_ms'] = None
        result = build_review_targets(data)
        self.assertEqual(result['athletes'][0]['score']['denominator'], 19)
        self.assertEqual(result['athletes'][0]['observed_stages']['END_AFTER_3_4_CONTACTS']['denominator'], 3)
        self.assertEqual(result['time_range_coverage']['numerator'], 0)

    def test_unknown_winner_does_not_enter_stage_or_score_denominator(self):
        data = sample()
        data['points'][1]['winner'] = 'unknown'
        result = build_review_targets(data)
        stage = result['athletes'][0]['observed_stages']['END_AFTER_3_4_CONTACTS']
        self.assertEqual((stage['denominator'], stage['lost_count'], stage['unknown_count']), (2, 2, 3))
        self.assertEqual(result['athletes'][0]['score']['denominator'], 18)
        self.assertIn(data['points'][1]['point_id'], stage['point_ids']['unknown'])

    def test_cli_reproducible_output_and_input_protection(self):
        script = ROOT / 'scripts/run_review_targets.py'
        source = ROOT / 'fixtures/review-targets-11-8-input.json'
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / 'review.json'
            command = [sys.executable, str(script), '--input', str(source), '--output', str(out)]
            for _ in range(2):
                self.assertEqual(subprocess.run(command, capture_output=True).returncode, 0)
            self.assertEqual(json.loads(out.read_text(encoding='utf-8')), build_review_targets(sample()))
            out.write_text('different output', encoding='utf-8')
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 2)
            self.assertEqual(subprocess.run(command[:-1] + [str(source)], capture_output=True).returncode, 2)

    def test_bad_input_rejected_without_mutation(self):
        for mutate in (
            lambda d: d.update(contract_version='ptti.quick-annotation/99'),
            lambda d: d['points'].append(copy.deepcopy(d['points'][0])),
            lambda d: d['points'][0].update(observed_rally_stage='THIRD_BALL_ATTACK'),
            lambda d: d.update(rights_status='ALLOWED'),
        ):
            data = sample()
            mutate(data)
            with self.assertRaises(QuickAnnotationError):
                build_review_targets(data)
        data = sample()
        before = copy.deepcopy(data)
        build_review_targets(data)
        self.assertEqual(data, before)


if __name__ == '__main__':
    unittest.main()
