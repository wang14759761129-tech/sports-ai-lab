"""Same-input handoff checks. Test-only binding acceptance is not a shipped Web consumer."""
import copy
import hashlib
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from quick_annotation import QuickAnnotationError
from review_targets import build_review_targets

INPUT = ROOT / 'fixtures/review-targets-11-8-input.json'
SAN = Path(os.environ.get('PTTI_SAN_WEB_ROOT', r'C:\PTTI-Worktrees\web-mvp-v0-1\products\ptti-web'))


def load():
    return json.loads(INPUT.read_bytes())


def acceptance_binding_matches(raw_bytes, view, receipt):
    """Normative receiver test oracle only; San has no runtime view consumer yet."""
    expected = build_review_targets(json.loads(raw_bytes))
    return (view.get('contract_version') == 'ptti.review-targets/0.1'
            and receipt['raw_input_sha256'] == hashlib.sha256(raw_bytes).hexdigest()
            and view == expected)


class SanReviewTargetsAcceptance(unittest.TestCase):
    def cross_check(self, payload):
        if not (SAN / 'src/local-loss-insights.mjs').exists():
            self.skipTest(f'San source unavailable: {SAN}')
        review = build_review_targets(payload)
        result = subprocess.run(['node', str(ROOT / 'tests/check_review_targets_san_goal10_6.mjs'), str(SAN)],
                                input=json.dumps({'payload': payload, 'review': review}),
                                text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        return review, json.loads(result.stdout)

    def test_exact_golden_not_san_other_draft(self):
        review, san = self.cross_check(load())
        target = next(t for t in review['review_targets'] if t['subject_role'] == 'player'
                      and t['observed_rally_stage'] == 'END_AFTER_3_4_CONTACTS')
        ids = [load()['points'][n-1]['point_id'] for n in (2, 4, 6)]
        self.assertEqual(target['point_ids'], ids)
        self.assertEqual(san['summaries'][0]['three_four_loss_ids'], ids)
        self.assertEqual((target['denominator'], target['unknown_count']), (3, 2))
        self.assertEqual(san['imported_playable_count'], 0)

    def test_single_winner_edit_is_ongoing_10_9_not_finished(self):
        payload = load()
        original = build_review_targets(payload)
        payload['points'][0]['winner'] = 'opponent'
        review, san = self.cross_check(payload)
        self.assertEqual(san['summaries'][0]['score'], [10, 9])
        self.assertNotEqual(review['canonical_input_sha256'], original['canonical_input_sha256'])
        # Completion is NOT exported by either summary. COMPLETE_FROM_GAME_START means coverage.
        score = review['sample']['game_counts']['1']
        a, b = score['player_wins'], score['opponent_wins']
        self.assertFalse(max(a, b) >= 11 and abs(a-b) >= 2)
        self.assertNotIn('game_finished', review)
        self.assertEqual(payload['rules_context']['games'][0]['coverage'], 'COMPLETE_FROM_GAME_START')

    def test_unchanged_bytes_match_but_winner_byte_or_view_changes_reject(self):
        raw = INPUT.read_bytes()
        view = build_review_targets(json.loads(raw))
        receipt = {'raw_input_sha256': hashlib.sha256(raw).hexdigest()}
        self.assertTrue(acceptance_binding_matches(raw, view, receipt))
        changed = load()
        changed['points'][0]['winner'] = 'opponent'
        self.assertFalse(acceptance_binding_matches(json.dumps(changed).encode(), view, receipt))
        whitespace_changed = raw + b'\n'
        self.assertEqual(build_review_targets(json.loads(whitespace_changed))['canonical_input_sha256'], view['canonical_input_sha256'])
        self.assertFalse(acceptance_binding_matches(whitespace_changed, view, receipt))
        tampered = copy.deepcopy(view)
        tampered['athletes'][0]['score']['won_count'] += 1
        self.assertFalse(acceptance_binding_matches(raw, tampered, receipt))

    def test_unknown_values_and_v01_have_same_known_denominators(self):
        payload = load()
        payload['points'][1]['winner'] = 'unknown'
        self.cross_check(payload)
        payload['contract_version'] = 'ptti.quick-annotation/0.1'
        for point in payload['points']:
            del point['observed_rally_stage']
        view, _ = self.cross_check(payload)
        self.assertEqual(view['unknown_stage_count'], 19)
        self.assertEqual(view['review_targets'], [])

    def test_unknown_stage_population_difference_is_explicit(self):
        payload = load()
        payload['points'][13]['winner'] = 'unknown'  # p014 also has UNKNOWN stage.
        view, san = self.cross_check(payload)
        self.assertEqual(view['unknown_stage_count'], 2)  # all supplied rows
        self.assertEqual(san['summaries'][0]['unknown_stages_among_known_winners'], 1)
        self.assertEqual(view['athletes'][0]['score']['denominator'], 18)

    def test_real_input_schema_and_unknown_versions_rejected(self):
        from jsonschema import Draft202012Validator
        schema = json.loads((ROOT / 'contracts/quick-annotation-v0.2.schema.json').read_text(encoding='utf-8'))
        Draft202012Validator(schema).validate(load())
        payload = load()
        payload['contract_version'] = 'ptti.quick-annotation/999'
        with self.assertRaises(QuickAnnotationError):
            build_review_targets(payload)
        view = build_review_targets(load())
        view['contract_version'] = 'ptti.review-targets/999'
        self.assertFalse(acceptance_binding_matches(INPUT.read_bytes(), view,
                         {'raw_input_sha256': hashlib.sha256(INPUT.read_bytes()).hexdigest()}))


if __name__ == '__main__':
    unittest.main()
