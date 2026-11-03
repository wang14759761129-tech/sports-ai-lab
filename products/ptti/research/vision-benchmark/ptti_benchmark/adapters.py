"""Format adapters only. Frameworks and model inference remain outside benchmark core."""
from .core import BallDetection, FrameObservation


def racketvision_rows(rows, fps, model="RacketVision Official RAW"):
    result = []
    for row in rows:
        frame = int(row["frame"])
        detections = ()
        if row["visible"]:
            # Older cache calls this confidence; retain value but never call it probability.
            detections = (BallDetection(float(row["pixel_x"]), float(row["pixel_y"]),
                                        row.get("confidence")),)
        result.append(FrameObservation(frame, frame * 1000 / fps, detections,
                                       model, "FROZEN_RAW_CACHE"))
    return result


def rfdetr_rows(rows):
    return [FrameObservation(int(row["source_frame"]), float(row["timestamp_ms"]),
                             tuple(BallDetection(**d) for d in row["detections"]),
                             "RF-DETR Nano", "PRETRAINED_SPORTS_BALL") for row in rows]
