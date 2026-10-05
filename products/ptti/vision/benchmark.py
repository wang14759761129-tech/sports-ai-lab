import csv
import math
import statistics

def read_ground_truth(path):
    with open(path, encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    if not rows or not {'Frame', 'Visibility', 'X', 'Y'}.issubset(rows[0]):
        raise ValueError('Ground truth requires Frame, Visibility, X, Y')
    result = {}
    for row in rows:
        frame, visibility = int(row['Frame']), int(row['Visibility'])
        if frame < 0 or frame in result or visibility not in (0, 1):
            raise ValueError('Invalid or duplicate GT frame')
        x, y = float(row['X']), float(row['Y'])
        if not math.isfinite(x) or not math.isfinite(y):
            raise ValueError('Non-finite GT coordinates')
        result[frame] = dict(visible=bool(visibility), x=x, y=y)
    return result

def percentile(values, p):
    if not values:
        return None
    values = sorted(values)
    n = (len(values) - 1) * p
    lo = math.floor(n); hi = math.ceil(n)
    return values[lo] + (values[hi] - values[lo]) * (n - lo)

def compare(prediction, ground_truth, width, height):
    if width <= 0 or height <= 0:
        raise ValueError('Invalid frame dimensions')
    pred = {p['frame']: p for p in prediction}
    if len(pred) != len(prediction):
        raise ValueError('Duplicate prediction frame')
    errors, normalized = [], []
    visible_gt = detected = missed = false = missing = 0
    for frame, gt in ground_truth.items():
        p = pred.get(frame)
        if p is None: missing += 1
        pv = bool(p and p['visible'])
        if gt['visible']:
            visible_gt += 1
            if pv:
                detected += 1
                dx, dy = p['pixel_x'] - gt['x'], p['pixel_y'] - gt['y']
                errors.append(math.hypot(dx, dy))
                normalized.append(math.hypot(dx / width, dy / height))
            else: missed += 1
        elif pv: false += 1
    return dict(annotated_frames=len(ground_truth), prediction_frames=len(prediction),
                unannotated_prediction_frames=len(set(pred) - set(ground_truth)),
                frames=len(ground_truth), visible_gt_frames=visible_gt,
                detected_visible_frames=detected, visible_recall=detected / visible_gt if visible_gt else None,
                missed_frames=missed, false_detections=false, missing_prediction_frames=missing,
                mean_position_error_px=statistics.mean(errors) if errors else None,
                median_position_error_px=statistics.median(errors) if errors else None,
                p90_position_error_px=percentile(errors, .90), p95_position_error_px=percentile(errors, .95),
                mean_normalized_position_error=statistics.mean(normalized) if normalized else None,
                status='BASELINE_ONLY',
                definition='Sparse annotated frames only; unannotated frames are not negatives. Visibility recall is not localization-threshold recall. Positional error on co-visible annotations; no official benchmark equivalence or F1 claimed.')
