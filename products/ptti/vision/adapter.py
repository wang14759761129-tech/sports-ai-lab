from .schema import BallPoint

def adapt_ball_rows(rows, width, height, fps):
    if min(width, height, fps) <= 0:
        raise ValueError('Invalid video dimensions / FPS')
    result = []
    for row in rows:
        visibility = int(row['Visibility'])
        if visibility not in (0, 1):
            raise ValueError('Invalid visibility')
        visible = bool(visibility)
        x, y = float(row['X']), float(row['Y'])
        point = BallPoint(frame=int(row['Frame']), timestamp_ms=int(row['Frame']) * 1000 / fps,
                          visible=visible, pixel_x=x if visible else None, pixel_y=y if visible else None,
                          normalized_x=x / width if visible else None,
                          normalized_y=y / height if visible else None,
                          confidence=float(row['Confidence']) if row.get('Confidence') is not None else None)
        result.append(point.model_dump())
    if len({p['frame'] for p in result}) != len(result):
        raise ValueError('Duplicate prediction frame')
    return result
