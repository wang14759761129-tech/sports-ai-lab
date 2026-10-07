"""Pure observation-only features. No filesystem, dataset labels, or GT access."""
from __future__ import annotations

import math


def table_coordinates(point, bbox):
    if not bbox:
        return None
    x0, y0, x1, y1 = bbox
    if x1 <= x0 or y1 <= y0:
        raise ValueError('INVALID_TABLE_BOX')
    x, y = (point[0]-x0)/(x1-x0), (point[1]-y0)/(y1-y0)
    return {'x': x, 'y': y, 'inside_bbox': 0 <= x <= 1 and 0 <= y <= 1,
            'center_distance_proxy': abs(x-.5), 'scope': 'CAMERA_DEPENDENT',
            'physical_side': 'UNKNOWN', 'coordinate_system': 'COARSE_IMAGE_BBOX_NOT_TABLE_PLANE'}


def player_proximity(point, people, image_size):
    diagonal = math.hypot(*image_size)
    if min(image_size) <= 0 or not all(math.isfinite(float(v)) for v in [*image_size, *point]):
        raise ValueError('INVALID_PLAYER_EVIDENCE_GEOMETRY')
    rows = []
    for person in people:
        x0, y0, x1, y1 = person['bbox']
        if not all(math.isfinite(float(v)) for v in person['bbox']) or x1 <= x0 or y1 <= y0:
            raise ValueError('INVALID_PLAYER_BBOX')
        if not math.isfinite(person['detector_score']) or not 0 <= person['detector_score'] <= 1:
            raise ValueError('INVALID_DETECTOR_SCORE')
        dx = max(x0-point[0], 0, point[0]-x1)
        dy = max(y0-point[1], 0, point[1]-y1)
        rows.append({'candidate_id': person['candidate_id'], 'distance_normalized': math.hypot(dx, dy)/diagonal,
                     'bbox': person['bbox'], 'detector_score': person['detector_score'],
                     'player_center': [(x0+x1)/2, (y0+y1)/2],
                     'role': 'UNKNOWN', 'role_candidate': person.get('role_candidate', 'UNKNOWN'),
                     'role_evidence': person.get('role_evidence', []), 'identity_status': 'UNCONFIRMED',
                     'role_confidence': None, 'side_confidence': None})
    return {'people': rows, 'minimum_person_distance': min((r['distance_normalized'] for r in rows), default=None),
            'minimum_player_candidate_distance': min((r['distance_normalized'] for r in rows
                if r['role_candidate'] in {'NEAR_PLAYER', 'FAR_PLAYER'}), default=None),
            'distance_to_near_candidate': min((r['distance_normalized'] for r in rows
                if r['role_candidate'] == 'NEAR_PLAYER'), default=None),
            'distance_to_far_candidate': min((r['distance_normalized'] for r in rows
                if r['role_candidate'] == 'FAR_PLAYER'), default=None),
            'role': 'UNKNOWN', 'physical_side': 'UNKNOWN', 'scope': 'CAMERA_DEPENDENT'}


def soft_adjustment(candidate, *, ball_point, table=None, player=None, mode='A', config=None):
    if mode not in {'A', 'B', 'C', 'D'}:
        raise ValueError('UNKNOWN_ABLATION')
    config = config or {'table_center_penalty': .08, 'person_distance_penalty': .12,
                        'distance_scale': .12}
    row = dict(candidate)
    penalties = {}
    if mode in {'B', 'D'} and table and ball_point:
        coordinates = table_coordinates(ball_point, table)
        # Coarse image center is a soft camera-specific prior, never net truth.
        penalties['coarse_table_center'] = config['table_center_penalty']*max(0, 1-2*coordinates['center_distance_proxy'])
    if mode in {'C', 'D'} and player:
        distance = player.get('minimum_player_candidate_distance')
        if distance is not None:
            penalties['player_distance'] = config['person_distance_penalty']*min(1, distance/config['distance_scale'])
    row['original_evidence_score'] = candidate['evidence_score']
    row['evidence_score'] = max(0, candidate['evidence_score']-sum(penalties.values()))
    row['research_soft_penalties'] = penalties
    row['ablation'] = mode
    return row


def review_workload(count, duration_s, seconds_per_candidate=3):
    if duration_s <= 0 or count < 0 or seconds_per_candidate < 0:
        raise ValueError('INVALID_REVIEW_WORKLOAD_INPUT')
    per_minute = count*60/duration_s
    return {'candidates_per_minute': per_minute, 'estimated_review_minutes': count*seconds_per_candidate/60,
            'estimated_clicks_per_45_minute_match': per_minute*45,
            'estimated_review_minutes_per_45_minute_match': per_minute*45*seconds_per_candidate/60,
            'assumption_seconds_per_candidate': seconds_per_candidate, 'measured_human_time': False}
