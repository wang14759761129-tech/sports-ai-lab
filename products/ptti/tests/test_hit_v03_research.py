"""New research code tests; model inference and official TEST data are excluded."""
import ast
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]/'research/hit-v03'


def load(name):
    spec = importlib.util.spec_from_file_location(f'hitv03_{name}', ROOT/f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_runtime_has_no_gt_or_filesystem_access():
    tree = ast.parse((ROOT/'runtime.py').read_text(encoding='utf-8'))
    imports = [node.names[0].name for node in ast.walk(tree) if isinstance(node, ast.Import)]
    assert imports == ['math']
    assert not any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                   and node.func.id in {'open', 'eval', '__import__'} for node in ast.walk(tree))


def test_table_coordinates_camera_dependent():
    result = load('runtime').table_coordinates((50, 100), [0, 0, 100, 200])
    assert (result['x'], result['y']) == (.5, .5)
    assert result['physical_side'] == 'UNKNOWN'
    assert result['scope'] == 'CAMERA_DEPENDENT'


def test_missing_table_is_null():
    assert load('runtime').table_coordinates((50, 100), None) is None


def test_invalid_table_rejected():
    with pytest.raises(ValueError):
        load('runtime').table_coordinates((0, 0), [1, 2, 1, 3])


def test_player_role_never_promoted_from_detector():
    row = {'candidate_id': 'p', 'bbox': [0, 0, 100, 100], 'detector_score': .9,
           'role_candidate': 'NEAR_PLAYER'}
    result = load('runtime').player_proximity((20, 20), [row], (1920, 1080))
    assert result['minimum_player_candidate_distance'] == 0
    assert result['role'] == 'UNKNOWN'
    assert result['people'][0]['identity_status'] == 'UNCONFIRMED'


def test_no_people_does_not_invent_distance():
    assert load('runtime').player_proximity((20, 20), [], (1920, 1080))['minimum_person_distance'] is None


def test_ablation_a_unchanged_and_input_preserved():
    candidate = {'evidence_score': .7}
    result = load('runtime').soft_adjustment(candidate, ball_point=(50, 50), table=[0, 0, 100, 100], mode='A')
    assert result['evidence_score'] == .7
    assert candidate == {'evidence_score': .7}


def test_table_penalty_soft_not_delete():
    row = load('runtime').soft_adjustment({'evidence_score': .7}, ball_point=(50, 50),
                                          table=[0, 0, 100, 100], mode='B')
    assert 0 < row['evidence_score'] < .7
    assert 'coarse_table_center' in row['research_soft_penalties']


def test_unknown_player_feature_neutral():
    row = load('runtime').soft_adjustment({'evidence_score': .7}, ball_point=(0, 0),
        player={'minimum_player_candidate_distance': None}, mode='C')
    assert row['evidence_score'] == .7


def test_review_time_is_assumption():
    result = load('runtime').review_workload(100, 600)
    assert result['candidates_per_minute'] == 10
    assert result['estimated_review_minutes_per_45_minute_match'] == 22.5
    assert result['measured_human_time'] is False


def test_event_proximity_multilabel_not_causality():
    audit = load('audit')
    events = {kind: [{'event_id': kind, 'timestamp_ms': 100, 'native_label': kind}]
              for kind in ['STROKE', 'BOUNCE', 'NET', 'RALLY_ENDING']}
    result = audit.event_proximity({'timestamp_ms': 110, 'candidate_player': 'UNKNOWN'}, events)
    assert {'NEAR_BOUNCE', 'NEAR_NET', 'NEAR_STROKE_DUPLICATE'} <= set(result['labels'])
    assert result['interpretation'] == 'NONEXCLUSIVE_TEMPORAL_PROXIMITY_NOT_PROVEN_CAUSE'


def test_empty_event_distribution_not_zero_evidence():
    assert load('audit').distribution([])['quantiles_ms']['median'] is None


def test_nearest_delta_is_signed():
    result = load('audit').nearest([{'event_id': 'e', 'timestamp_ms': 100, 'native_label': 'bounce'}], [100], 90)
    assert result['delta_ms'] == -10


def test_kinematics_missing_does_not_make_motion():
    result = load('audit').local_kinematics([], [], 100)
    assert result['trajectory'] == [] and result['velocity'] == []
    assert result['missing_fraction_proxy'] == 1


def test_constant_velocity_has_zero_acceleration():
    rows = [{'timestamp_ms': i*10, 'x': i, 'y': i*2} for i in range(10)]
    result = load('audit').local_kinematics(rows, [r['timestamp_ms'] for r in rows], 50)
    assert all(r['magnitude_px_s2'] == 0 for r in result['acceleration_curvature_proxy'])


def test_context_without_visible_center_diagnosed_as_fragment():
    rows = [{'timestamp_ms': t, 'x': t, 'y': 0} for t in [0, 10, 90, 100]]
    result = load('audit').diagnose_fn_center(rows, [r['timestamp_ms'] for r in rows], 50, 16.667,
                                              {'max_ball_gap_ms': 120, 'minimum_kinematic_score': .18})
    assert result['center_observations_within_tolerance'] == 0
    assert result['mechanisms'] == ['BALL_FRAGMENT']


def test_fragment_boundary_proximity():
    assert load('audit').fragment_proximity(20, [0], [100]) == ['BALLTRACK_FRAGMENT_START', 'BALLTRACK_FRAGMENT_END']


def test_worker_rejects_calibration_before_model_import():
    with pytest.raises(ValueError, match='NON_DEV_GAME'):
        load('player_worker').validate_request({'game': 'game_4'})


def test_worker_rejects_gt_content_before_file_access():
    with pytest.raises(ValueError, match='GT_CONTENT_FORBIDDEN'):
        load('player_worker').validate_request({'game': 'game_1', 'fps': 120, 'frames': [0], 'bounce_gt': []})


def test_worker_rejects_duplicate_frames():
    with pytest.raises(ValueError, match='NONCANONICAL'):
        load('player_worker').validate_request({'game': 'game_1', 'fps': 120, 'frames': [0, 0]})


def test_worker_rejects_oversized_chunk():
    with pytest.raises(ValueError, match='UNSAFE_WORKER'):
        load('player_worker').validate_request({'game': 'game_1', 'fps': 120, 'frames': list(range(257))})


def test_ablation_features_are_deterministic_without_gt():
    runtime = load('runtime')
    for mode in 'ABCD':
        arguments = {'ball_point': (50, 50), 'table': [0, 0, 100, 100],
                     'player': {'minimum_player_candidate_distance': .1}, 'mode': mode}
        assert runtime.soft_adjustment({'evidence_score': .7}, **arguments) == runtime.soft_adjustment({'evidence_score': .7}, **arguments)


def test_player_schema_rejects_nonfinite_scores():
    with pytest.raises(ValueError, match='INVALID_DETECTOR_SCORE'):
        load('runtime').player_proximity((0, 0), [{'candidate_id': 'x', 'bbox': [0, 0, 10, 10],
                                               'detector_score': float('nan')}], (1920, 1080))


def test_unknown_roles_keep_null_confidence():
    result = load('runtime').player_proximity((0, 0), [{'candidate_id': 'x', 'bbox': [0, 0, 10, 10],
                                                     'detector_score': .5}], (1920, 1080))
    assert result['people'][0]['role_confidence'] is None
    assert result['people'][0]['side_confidence'] is None
