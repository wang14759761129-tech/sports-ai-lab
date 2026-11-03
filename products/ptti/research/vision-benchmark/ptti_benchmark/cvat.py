"""CVAT 1.1 XML -> canonical benchmark labels, retaining uncertainty and native evidence."""
from pathlib import Path
import xml.etree.ElementTree as ET

LABELS = {"BALL", "NEAR_PLAYER", "FAR_PLAYER", "REFEREE", "TABLE",
          "HIT", "BOUNCE", "NET", "RALLY_END", "BALL_ABSENT"}


def read_cvat_xml(path: Path, frame_map: dict[int, dict]) -> list[dict]:
    payload = Path(path).read_bytes()
    if b"<!DOCTYPE" in payload.upper() or b"<!ENTITY" in payload.upper():
        raise ValueError("UNSAFE_XML_DECLARATION")
    root = ET.fromstring(payload)
    result = []

    def append(node, local_frame, track_id=None):
        label = node.get("label")
        if label not in LABELS:
            raise ValueError("UNSUPPORTED_CVAT_LABEL")
        if local_frame not in frame_map:
            raise ValueError("CVAT_FRAME_MAPPING_REQUIRED")
        mapping = frame_map[local_frame]
        record = {**mapping, "label": label, "source": "CVAT_EXPORT",
                  "track_id": track_id, "native": dict(node.attrib),
                  "attributes": {a.get("name"): a.text for a in node.findall("attribute")},
                  "review_status": "NEEDS_REVIEW"}
        if label == "BALL":
            if node.get("outside") == "1":
                # A tracking disappearance is not proof that the ball is absent.
                record.update(visible=None, x=None, y=None)
            elif node.tag == "points":
                coords = node.get("points", "").split(";")
                if len(coords) != 1:
                    raise ValueError("BALL_REQUIRES_SINGLE_POINT")
                x, y = map(float, coords[0].split(","))
                record.update(visible=True, x=x, y=y)
            elif node.tag == "box":
                box = [float(node.get(k)) for k in ("xtl", "ytl", "xbr", "ybr")]
                if box[2] <= box[0] or box[3] <= box[1]:
                    raise ValueError("INVALID_CVAT_BOX")
                record.update(visible=True, x=(box[0]+box[2])/2, y=(box[1]+box[3])/2, bbox=box)
            else:
                raise ValueError("UNSUPPORTED_BALL_SHAPE")
        elif label == "BALL_ABSENT":
            record.update(visible=False, x=None, y=None)
        result.append(record)

    for image in root.findall("image"):
        for node in image:
            append(node, int(image.get("id")))
    for track in root.findall("track"):
        for node in track:
            node.set("label", track.get("label"))
            append(node, int(node.get("frame")), track.get("id"))
    return result
