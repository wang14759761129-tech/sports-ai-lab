from __future__ import annotations

import copy
import json
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from quick_annotation import QuickAnnotationError, adapt_quick_annotation, summarize_quick_annotation


def simulated_game(winners, first_server='player'):
    payload = json.loads((ROOT / 'fixtures/quick-annotation-v0.2-valid-simulated.json').read_text(encoding='utf-8'))
    payload['dataset_id'] = 'SIMULATED_ONLY:goal10-4-training-acceptance'
    payload['rules_context']['games'][0]['first_server'] = first_server
    payload['points'] = [{
        'point_id': f'SIMULATED_ONLY%3Aquick-match-v02-001/g01/p{index:03d}',
        'server': 'unknown', 'winner': winner, 'observed_tactics': {},
        'rally_start_ms': None, 'rally_end_ms': None,
    } for index, winner in enumerate(winners, 1)]
    return payload


class TrainingAcceptanceTests(unittest.TestCase):
    def test_seeded_100_complete_games_against_score_and_service_state_machine(self):
        rng = random.Random(104)
        for case in range(100):
            first_server = 'player' if case % 2 else 'opponent'
            server, remaining = first_server, 2
            a, b = 0, 0
            winners, expected = [], []
            for _ in range(100):
                expected.append(({'player': a, 'opponent': b}, server))
                winner = rng.choice(['player', 'opponent'])
                winners.append(winner)
                a += int(winner == 'player')
                b += int(winner == 'opponent')
                if max(a, b) >= 11 and abs(a-b) >= 2:
                    break
                remaining -= 1
                if remaining == 0:
                    server = 'opponent' if server == 'player' else 'player'
                    remaining = 1 if a >= 10 and b >= 10 else 2
            else:
                self.fail('bounded synthetic generator did not complete a game')
            payload = simulated_game(winners, first_server)
            if case % 2:
                payload['contract_version'] = 'ptti.quick-annotation/0.1'
            draft = adapt_quick_annotation(payload)
            self.assertEqual([(p['score_before_player_opponent'], p['protocol_fields']['server'])
                              for p in draft['points']], expected)
            counts = summarize_quick_annotation(draft)['sample']['game_counts']['1']
            self.assertEqual((counts['player_wins'], counts['opponent_wins']), (a, b))

    def test_complete_11_9_game_from_zero(self):
        draft = adapt_quick_annotation(simulated_game(['player', 'opponent'] * 9 + ['player', 'player']))
        self.assertEqual(draft['points'][0]['score_before_player_opponent'], {'player': 0, 'opponent': 0})
        self.assertEqual(draft['points'][-1]['score_before_player_opponent'], {'player': 10, 'opponent': 9})
        self.assertEqual([p['protocol_fields']['server'] for p in draft['points']], ['player', 'player', 'opponent', 'opponent'] * 5)
        stats = summarize_quick_annotation(draft)
        self.assertEqual(stats['sample']['game_counts']['1'], {
            'point_count': 20, 'known_winner_count': 20, 'player_wins': 11, 'opponent_wins': 9})

    def test_deuce_12_10_and_first_server_recalculation(self):
        payload = simulated_game(['player', 'opponent'] * 10 + ['player', 'player'])
        before = adapt_quick_annotation(payload)
        self.assertEqual([p['protocol_fields']['server'] for p in before['points'][20:]], ['player', 'opponent'])
        self.assertEqual(before['points'][20]['score_before_player_opponent'], {'player': 10, 'opponent': 10})
        payload['rules_context']['games'][0]['first_server'] = 'opponent'
        after = adapt_quick_annotation(payload)
        self.assertEqual([p['protocol_fields']['server'] for p in after['points']],
                         ['opponent', 'opponent', 'player', 'player'] * 5 + ['opponent', 'player'])
        self.assertEqual([p['score_before_player_opponent'] for p in before['points']],
                         [p['score_before_player_opponent'] for p in after['points']])
        self.assertEqual(summarize_quick_annotation(after)['sample']['game_counts']['1']['player_wins'], 12)
        normal = simulated_game(['player', 'opponent'] * 9 + ['player', 'player'])
        original_rate = summarize_quick_annotation(adapt_quick_annotation(normal))['metrics']['server_point_win_rate']
        normal['rules_context']['games'][0]['first_server'] = 'opponent'
        flipped_rate = summarize_quick_annotation(adapt_quick_annotation(normal))['metrics']['server_point_win_rate']
        self.assertEqual((original_rate['numerator'], original_rate['denominator']), (9, 20))
        self.assertEqual((flipped_rate['numerator'], flipped_rate['denominator']), (11, 20))

    def test_no_points_after_known_game_end(self):
        for winners in (['player'] * 11 + ['opponent'], ['opponent'] * 11 + ['player'],
                        ['player', 'opponent'] * 10 + ['player', 'player', 'opponent']):
            with self.subTest(winners=winners):
                with self.assertRaises(QuickAnnotationError) as caught:
                    adapt_quick_annotation(simulated_game(winners))
                self.assertEqual(caught.exception.code, 'GAME_ALREADY_ENDED')

    def test_missing_score_chain_never_invents_game_completion(self):
        payload = simulated_game(['player'] * 11 + ['opponent'])
        payload['points'].pop(4)
        draft = adapt_quick_annotation(payload)
        self.assertFalse(draft['protocol']['sequence_valid'])
        self.assertTrue(all(p['score_before_player_opponent'] is None for p in draft['points'][4:]))

    def test_missing_point_backfill_and_historical_winner_edit(self):
        payload = simulated_game(['player', 'opponent'] * 9 + ['player', 'player'])
        original = adapt_quick_annotation(payload)
        saved = payload['points'].pop(5)
        missing = adapt_quick_annotation(payload)
        self.assertFalse(missing['protocol']['sequence_valid'])
        self.assertEqual(summarize_quick_annotation(missing)['sample']['score_known_count'], 19)
        self.assertTrue(all(p['score_before_player_opponent'] is None for p in missing['points'][5:]))
        payload['points'].insert(5, saved)
        self.assertEqual(adapt_quick_annotation(payload), original)
        payload['points'][0]['winner'] = 'opponent'
        changed = adapt_quick_annotation(payload)
        self.assertEqual(changed['points'][1]['score_before_player_opponent'], {'player': 0, 'opponent': 1})
        counts = summarize_quick_annotation(changed)['sample']['game_counts']['1']
        self.assertEqual((counts['player_wins'], counts['opponent_wins']), (10, 10))

    def test_score_time_range_and_independent_evidence_are_separate(self):
        payload = simulated_game(['player', 'opponent'] * 9 + ['player', 'player'])
        for index, point in enumerate(payload['points'][:12]):
            point.update(rally_start_ms=index*1000, rally_end_ms=index*1000+500)
        draft = adapt_quick_annotation(payload)
        stats = summarize_quick_annotation(draft)
        self.assertEqual(stats['sample']['score_known_count'], 20)
        self.assertEqual((stats['metrics']['time_range_coverage']['numerator'], stats['metrics']['time_range_coverage']['denominator']), (12, 20))
        self.assertEqual(stats['metrics']['timeline_bound_review_coverage']['numerator'], 0)
        self.assertTrue(all(p['timestamp']['timeline_binding'] == 'UNBOUND' for p in draft['points']))
        self.assertEqual(stats['dataset']['rights_status'], 'UNKNOWN')
        self.assertEqual(stats['dataset']['vision_status'], 'NOT_TESTED')

    def test_unknown_tactics_and_sample_threshold_boundaries(self):
        for n, status in ((0, 'NOT_ESTIMABLE'), (4, 'INSUFFICIENT_SAMPLE'), (5, 'DESCRIPTIVE_ONLY')):
            payload = simulated_game(['player', 'opponent'] * 4)
            for point in payload['points']:
                point['observed_tactics'] = {'serve_length': 'unknown', 'third_ball_attack': 'unknown'}
            for point in payload['points'][:n]:
                point['observed_tactics']['serve_length'] = 'short'
            stats = summarize_quick_annotation(adapt_quick_annotation(payload))
            metric = stats['metrics']['tactical_fields']['serve_length']
            self.assertEqual(metric['denominator'], n)
            self.assertEqual(metric['missing_count'], 8-n)
            self.assertEqual(metric['sample_status'], status)
            self.assertFalse(metric['threshold_is_significance_test'])
            self.assertEqual(stats['metrics']['third_ball_attack_rate']['denominator'], 0)

    def test_delete_and_restore_input_recomputes_without_cached_statistics(self):
        payload = simulated_game(['player', 'opponent'] * 4)
        before = summarize_quick_annotation(adapt_quick_annotation(payload))
        deleted = copy.deepcopy(payload)
        deleted['points'].pop(3)
        after = summarize_quick_annotation(adapt_quick_annotation(deleted))
        self.assertEqual(before['sample']['score_known_count'], 8)
        self.assertEqual(after['sample']['score_known_count'], 7)
        self.assertFalse(after['sample']['protocol_sequence_valid'])
        self.assertEqual(summarize_quick_annotation(adapt_quick_annotation(payload)), before)
