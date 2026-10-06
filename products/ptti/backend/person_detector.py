"""Framework-neutral person observations; model runtimes live in a worker."""
from __future__ import annotations

import hashlib
import json
from math import isfinite
from pathlib import Path
from typing import Callable, Protocol

R18_MODEL = "PekingU/rtdetr_r18vd"
R18_REVISION = "ac77a11ff0170a41b771c03264987f8ce2b0d753"
R18_SHA256 = "fe87a5a30f5daf298d10794c7682a63b6107986f97d6a770ba948d89e4340093"
FROZEN_MANIFEST_SHA = "67bc35a5a1570d4610e524141030f1c93aa5b2a8516767f12023d4eb9f75276f"
R18_FILES = {
    "model.safetensors": R18_SHA256,
    "config.json": "8493be71f51a1c0a741f8f71ec151039227579379de7bcba047c0470d9320c3c",
    "preprocessor_config.json": "ffb4b9461a1dad746be8f0f9c8330ed7743a1ba5fba4f75c232cd281b3d4c64a",
}


def file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_r18(folder: Path) -> dict:
    for name, expected in R18_FILES.items():
        if file_sha(folder / name) != expected:
            raise ValueError(f"MODEL_ARTIFACT_SHA_MISMATCH:{name}")
    config = json.loads((folder / "config.json").read_text(encoding="utf-8"))
    if config.get("model_type") != "rt_detr" or config.get("id2label", {}).get("0") != "person":
        raise ValueError("MODEL_IDENTITY_MISMATCH")
    return {"model": R18_MODEL, "revision": R18_REVISION, "license": "Apache-2.0",
            "artifact_sha256": dict(R18_FILES), "architecture": config["architectures"]}


class PersonDetector(Protocol):
    def detect(self, image, *, frame: int, timestamp_ms: int) -> list[dict]: ...


def box_iou(a, b) -> float:
    area_a = max(0, a[2]-a[0]) * max(0, a[3]-a[1])
    area_b = max(0, b[2]-b[0]) * max(0, b[3]-b[1])
    inter = max(0, min(a[2], b[2])-max(a[0], b[0])) * max(0, min(a[3], b[3])-max(a[1], b[1]))
    return inter / (area_a + area_b - inter) if area_a + area_b > inter else 0.0


class RTDetrPredictionAdapter:
    """HF postprocessed boxes are already source-pixel xyxy, never resize twice."""
    def adapt(self, predictions, *, image_size, frame, timestamp_ms, threshold=.25):
        if not isfinite(threshold) or not 0 <= threshold <= 1:
            raise ValueError("invalid threshold")
        width, height = image_size
        if width <= 0 or height <= 0:
            raise ValueError("invalid image size")
        rows = []
        for p in predictions:
            if p.get("label") != "person" or not isfinite(float(p["score"])) or not threshold <= p["score"] <= 1:
                continue
            box = list(map(float, p["bbox"]))
            if len(box) != 4 or not all(map(isfinite, box)):
                raise ValueError("invalid detector box")
            box = [max(0, min(width, box[0])), max(0, min(height, box[1])),
                   max(0, min(width, box[2])), max(0, min(height, box[3]))]
            if box[2] <= box[0] or box[3] <= box[1]:
                continue
            rows.append({"candidate_id": f"rtdetr-f{frame}-d{len(rows)}", "frame": frame,
                         "timestamp_ms": timestamp_ms, "bbox": box, "detector_score": float(p["score"]),
                         "label": "person", "detector": "RT-DETR R18", "model": R18_MODEL,
                         "model_version": R18_REVISION, "role": "UNKNOWN", "status": "SUGGESTED"})
        return rows


class RTDetrPersonDetector:
    def __init__(self, infer: Callable, *, threshold=.25):
        self.infer, self.threshold = infer, threshold

    def detect(self, image, *, frame, timestamp_ms):
        return RTDetrPredictionAdapter().adapt(self.infer(image), image_size=image.size,
                                              frame=frame, timestamp_ms=timestamp_ms, threshold=self.threshold)


class GroundingDinoPersonDetector:
    def __init__(self, infer: Callable):
        self.infer = infer

    def detect(self, image, *, frame, timestamp_ms):
        return [{**p, "frame": frame, "timestamp_ms": timestamp_ms, "detector": "Grounding DINO",
                 "role": "UNKNOWN", "status": "SUGGESTED"} for p in self.infer(image)
                if p.get("label", "").lower() in {"person", "player", "table tennis player", "athlete"}]


def deduplicate_people(rows, threshold=.7):
    """Retain raw evidence separately; projection suppresses overlapping duplicates."""
    result = []
    for p in sorted(rows, key=lambda p: p["detector_score"], reverse=True):
        if not any(box_iou(p["bbox"], other["bbox"]) >= threshold for other in result):
            result.append(dict(p))
    return result


def evaluate_people(predictions, annotations, *, iou_threshold=.3):
    """One-to-one approximate-box evaluation, separate from role correctness."""
    gt = annotations.get("players", [])
    pairs = sorted(((box_iou(p["bbox"], g["bbox"]), pi, gi)
                    for pi, p in enumerate(predictions) for gi, g in enumerate(gt)), reverse=True)
    used_p, used_g, ious = set(), set(), []
    for overlap, pi, gi in pairs:
        if overlap >= iou_threshold and pi not in used_p and gi not in used_g:
            used_p.add(pi); used_g.add(gi); ious.append(overlap)
    referee_fp = sum(any(box_iou(p["bbox"], b) >= iou_threshold for b in annotations.get("referees", []))
                     for i, p in enumerate(predictions) if i not in used_p)
    return {"gt_players": len(gt), "matched_players": len(used_g), "both_visible": len(gt) == 2,
            "both_matched": len(gt) == 2 and len(used_g) == 2, "matched_ious": ious,
            "non_player_detections": len(predictions)-len(used_p), "referee_detections": referee_fp,
            "matched_prediction_indexes": sorted(used_p), "matched_gt_indexes": sorted(used_g)}


def select_person_detector(results):
    """Missing/failed new worker falls back without inventing a new observation."""
    if results and results.get("status") == "REAL_DEV_EVALUATED":
        return results.get("model", R18_MODEL)
    return "GROUNDING_DINO_PLAYER_BASELINE"


class TablePersonRoleResolver:
    """Side-view geometric candidates; physical depth/identity stay unverified.

    A central person above the table is OTHER, not a proven referee. Two
    opposing court candidates may be ordered by image footpoint as a display
    near/far proxy. Same-side, cropped, or closely competing boxes stay unknown.
    """
    def resolve(self, table_bbox, people, *, image_size):
        rows = [dict(p, role="UNKNOWN", role_candidate="UNKNOWN", role_evidence=[]) for p in people]
        if not table_bbox:
            for p in rows:
                p['role_evidence'] = ['TABLE_MISSING']
            return rows
        tx0, ty0, tx1, ty1 = table_bbox
        tw, cx = tx1-tx0, (tx0+tx1)/2
        if tw <= 0 or ty1 <= ty0 or min(image_size) <= 0:
            raise ValueError('invalid table/image geometry')
        sides = {'LEFT':[], 'RIGHT':[]}
        for p in rows:
            x0,y0,x1,y1 = p['bbox']; pcx=(x0+x1)/2
            if abs(pcx-cx) < .12*tw and y1 < ty0:
                p['role_candidate']='OTHER'
                p['role_evidence']=['CENTRAL_PERSON_ABOVE_TABLE','NOT_A_CONFIRMED_REFEREE']
            elif pcx < cx-.12*tw or pcx > cx+.12*tw:
                side='LEFT' if pcx < cx else 'RIGHT'
                sides[side].append(p)
                p['role_evidence']=[f'PERSON_{side}_OF_TABLE']
            else:
                p['role_evidence']=['CENTRAL_PERSON_ROLE_AMBIGUOUS']
        selected=[]
        for side in ('LEFT','RIGHT'):
            candidates=sorted(sides[side],key=lambda p:p['detector_score'],reverse=True)
            if candidates and (len(candidates)==1 or candidates[0]['detector_score']-candidates[1]['detector_score']>=.15):
                selected.append(candidates[0])
        if len(selected)==2:
            near,far=sorted(selected,key=lambda p:p['bbox'][3],reverse=True)
            if near['bbox'][3]-far['bbox'][3] >= image_size[1]*.02:
                near['role_candidate']='NEAR_PLAYER';far['role_candidate']='FAR_PLAYER'
                for p in selected:
                    p['role_evidence']+=['OPPOSING_TABLE_SIDES','IMAGE_FOOTPOINT_DEPTH_PROXY',
                                         'PHYSICAL_DEPTH_AND_IDENTITY_UNVERIFIED']
        return rows


def person_frame_review(rows, *, table_present=True):
    roles={p.get('role_candidate') for p in rows}
    reasons=[]
    if not table_present: reasons.append('TABLE_MISSING')
    if 'NEAR_PLAYER' not in roles: reasons.append('NEAR_PLAYER_MISSING')
    if 'FAR_PLAYER' not in roles: reasons.append('FAR_PLAYER_MISSING')
    if any(p.get('role_candidate')=='UNKNOWN' for p in rows): reasons.append('ROLE_AMBIGUITY')
    if len(rows)>3: reasons.append('TOO_MANY_PERSONS')
    return {'priority':'HIGH' if reasons else 'LOW','status':'REVIEW_REQUIRED' if reasons else 'LIKELY_OK',
            'reasons':reasons}
