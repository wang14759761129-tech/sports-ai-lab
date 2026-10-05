"""Compare measured runs; tolerances are engineering policy, not accuracy claims."""
def compare_runs(baseline, candidate, relative_tolerance=0.05):
    if not 0 <= relative_tolerance <= 1:
        raise ValueError('Tolerance must be between zero and one')
    identity = ('video_sha256', 'gt_sha256', 'checkpoint_sha256', 'worker_device')
    if any(baseline['provenance'].get(k) != candidate['provenance'].get(k) for k in identity):
        return dict(status='NOT_COMPARABLE', reason='Input, GT, checkpoint or device differs')
    changes = []
    for key, lower_is_better in [('visible_recall', False), ('mean_position_error_px', True), ('p95_position_error_px', True)]:
        old, new = baseline['metrics'].get(key), candidate['metrics'].get(key)
        if old is None or new is None:
            changes.append(dict(metric=key, status='UNAVAILABLE'))
            continue
        limit = abs(old) * relative_tolerance
        worse = new - old if lower_is_better else old - new
        changes.append(dict(metric=key, baseline=old, candidate=new, status='REGRESSION' if worse > limit else 'WITHIN_TOLERANCE'))
    return dict(status='REGRESSION' if any(c['status'] == 'REGRESSION' for c in changes) else 'NO_MEASURED_REGRESSION', relative_tolerance=relative_tolerance, metrics=changes)
