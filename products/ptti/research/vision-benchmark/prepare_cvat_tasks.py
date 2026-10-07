"""Create local research annotation tasks and validate native XML round-trip; no CVAT/cloud upload."""
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET
import zipfile

from ptti_benchmark.core import file_sha256
from ptti_benchmark.cvat import read_cvat_xml


def main():
    root = Path.home() / "AppData/Local/PTTI-Dev/technology-foundation/benchmark-v0"
    manifest_path = root / "PTTI_VISION_BENCHMARK_V0_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    tasks_root = root / "cvat-tasks"
    tasks_root.mkdir(exist_ok=True)
    report_path = tasks_root / "task-preparation.json"
    if report_path.exists():
        raise FileExistsError("IMMUTABLE_TASK_REPORT_EXISTS")
    tasks, verified_rows = [], 0
    for clip in manifest["clips"]:
        labels = json.loads(Path(clip["canonical_labels"]).read_text(encoding="utf-8"))
        folder = Path(clip["canonical_labels"]).parent
        mapping = {int(k): v for k, v in json.loads((folder/"cvat_frame_map.json").read_text(encoding="utf-8")).items()}
        xml = ET.Element("annotations")
        ET.SubElement(xml, "version").text = "1.1"
        for local, label in enumerate(labels):
            image = ET.SubElement(xml, "image", id=str(local), name=Path(clip["images"][local]["path"]).name,
                                  width=str(clip["width"]), height=str(clip["height"]))
            if label["visible"]:
                ET.SubElement(image, "points", label="BALL", points=f"{label['x']},{label['y']}",
                              occluded="0", source="manual", z_order="0")
            else:
                ET.SubElement(image, "tag", label="BALL_ABSENT", source="manual")
        xml_path = tasks_root / (clip["id"].replace("/", "_")+".xml")
        ET.ElementTree(xml).write(xml_path, encoding="utf-8", xml_declaration=True)
        imported = read_cvat_xml(xml_path, mapping)
        for original, restored in zip(labels, imported):
            if any(original[field] != restored[field] for field in ("source_frame", "timestamp_ms", "visible")):
                raise ValueError("CVAT_ROUNDTRIP_TIMELINE_OR_VISIBILITY_CHANGED")
            if original["visible"] and (original["x"] != restored["x"] or original["y"] != restored["y"]):
                raise ValueError("CVAT_ROUNDTRIP_POINT_CHANGED")
        verified_rows += len(imported)
        zip_path = xml_path.with_suffix(".zip")
        if zip_path.exists():
            raise FileExistsError("TASK_ARCHIVE_EXISTS")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.write(xml_path, "annotations.xml")
            archive.write(folder/"cvat_frame_map.json", "PTTI-source-frame-map.json")
            for image in clip["images"]:
                archive.write(image["path"], "images/"+Path(image["path"]).name)
        with zipfile.ZipFile(zip_path) as archive:
            if archive.testzip() is not None:
                raise ValueError("CVAT_ARCHIVE_INTEGRITY_FAILED")
        tasks.append({"type": "SPARSE_NATIVE_GT_IMAGE_TASK", "id": clip["id"], "path": str(zip_path),
                      "sha256": file_sha256(zip_path), "images": len(imported),
                      "license": clip["license"], "commercial_use": False,
                      "annotation_origin": "EXISTING_NATIVE_GT_NOT_NEW_HUMAN_LABELS",
                      "CVAT_UI_IMPORT": "NOT_VERIFIED"})
    queue = json.loads((root/"annotation_queue.json").read_text(encoding="utf-8"))
    seen = set()
    for item in queue:
        game = item["task_id"].split(":")[0]
        if game in seen:
            continue
        if game not in {"game_1", "game_2", "game_3"}:
            raise ValueError("LOCKED_GAME_NOT_ALLOWED")
        seen.add(game)
        video = Path(item["video"])
        if file_sha256(video) != item["video_sha256"]:
            raise ValueError("SOURCE_CHANGED")
        source_start = max(0, item["source_frame"]-60)
        target = tasks_root/f"{game}-hit-fp-review.mp4"
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{source_start/120:.9f}",
                        "-i", str(video), "-frames:v", "120", "-an", "-c:v", "libx264", "-threads", "2",
                        "-crf", "20", "-pix_fmt", "yuv420p", "-n", str(target)], check=True)
        probe = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0",
                                                   "-show_streams", "-of", "json", str(target)]))
        frames = int(probe["streams"][0]["nb_frames"])
        if frames != 120:
            raise ValueError("ANNOTATION_CLIP_FRAME_COUNT_CHANGED")
        frame_map = {i: {"source_frame": source_start+i, "timestamp_ms": (source_start+i)*1000/120}
                     for i in range(frames)}
        map_path = target.with_suffix(".frame-map.json")
        map_path.write_text(json.dumps(frame_map, indent=2), encoding="utf-8")
        tasks.append({"type": "HIT_FP_CONTEXT_REVIEW", "id": game, "path": str(target),
                      "sha256": file_sha256(target), "frames": frames, "source_video_sha256": item["video_sha256"],
                      "frame_map": str(map_path), "license": "CC BY-NC-SA 4.0", "commercial_use": False,
                      "ball_negative_truth": "UNKNOWN_NOT_A_BALL_NEGATIVE_LABEL", "CVAT_UI_IMPORT": "NOT_VERIFIED"})
    report = {"status": "LOCAL_TASKS_READY_CVAT_SERVICE_NOT_AVAILABLE", "tasks": tasks,
              "native_annotation_rows_roundtripped": verified_rows, "queue_images": len(queue),
              "cvat_service": "NOT_RUN_NO_DOCKER", "actual_100_event_annotation_time": "NOT_MEASURED",
              "human_review": "PENDING", "automatic_cloud_upload": False,
              "original_evidence_modified": False, "production_database": "NOT_ACCESSED",
              "benchmark_manifest_sha256": file_sha256(manifest_path)}
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(report_path), "tasks": len(tasks), "roundtrip_rows": verified_rows}))


if __name__ == "__main__":
    main()
