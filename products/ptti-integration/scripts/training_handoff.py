"""Local coach workflow: init -> append to NEW CSV -> human review -> pack -> verify."""
import argparse
import csv
import hashlib
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from annotation_audit import make_package, validate_package, field_guide, review_receipt
from match_intelligence import POINT_FIELDS, MANUAL_MANIFEST_VERSION, import_manual_csv, build_synthetic_demo, serialize_protocol_csv
from training_review import csv_template, REAL_BINDING_VERSION, _require_video_stream_metadata, synthetic_declaration


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def save(path, value):
    data = value if isinstance(value, bytes) else (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    with Path(path).open("xb") as stream:
        stream.write(data)


def file_sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    for name in ("source-file", "output-dir", "dataset-id", "match-id", "source-id", "annotator-ref"):
        init.add_argument("--" + name, required=True)
    append = sub.add_parser("append")
    for name in ("csv", "row-json", "manifest", "source-file", "output"):
        append.add_argument("--" + name, required=True)
    pack = sub.add_parser("pack")
    for name in ("csv", "manifest", "binding", "source-file", "output"):
        pack.add_argument("--" + name, required=True)
    pack.add_argument("--generated-at", required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("--package", required=True)
    verify.add_argument("--source-file")
    review = sub.add_parser("review")
    for name in ("package", "decisions", "output"):
        review.add_argument("--" + name, required=True)
    review.add_argument("--source-file")
    demo = sub.add_parser("demo")
    demo.add_argument("--output-dir", required=True)
    args = p.parse_args(argv)
    try:
        if args.command == "init":
            _require_video_stream_metadata(Path(args.source_file))
            digest = file_sha(args.source_file)
            now = datetime.now(timezone.utc).isoformat()
            manifest = dict(manifest_version=MANUAL_MANIFEST_VERSION, dataset_id=args.dataset_id,
                            match_id=args.match_id, source_id=args.source_id, source_sha256=digest,
                            annotator_ref=args.annotator_ref, annotated_at=now, evidence_ref="unknown",
                            timestamp_semantics="PROTOCOL_TEXT_ONLY_UNBOUND")
            binding = dict(binding_version=REAL_BINDING_VERSION, dataset_id=args.dataset_id,
                           match_id=args.match_id, source_id=args.source_id, source_sha256=digest,
                           local_asset_id="unknown", match_link_status="UNKNOWN",
                           local_analysis_permission="UNKNOWN", rights_basis_ref="unknown",
                           reviewer_ref="unknown", reviewed_at=now, analysis_method="HUMAN_MANUAL")
            out = Path(args.output_dir)
            out.mkdir(parents=True, exist_ok=False)
            save(out / "points.csv", csv_template())
            save(out / "manifest.json", manifest)
            save(out / "binding.json", binding)
            save(out / "field-guide.json", field_guide())
            row = {field: "unknown" for field in POINT_FIELDS}
            row.update(match_id=args.match_id, game_number=1, point_number=1,
                       notes="unknown: awaiting manual observation; replace with observation basis")
            save(out / "row-draft.json", row)
        elif args.command == "append":
            row = read(args.row_json)
            if not isinstance(row, dict) or set(row) != set(POINT_FIELDS):
                raise ValueError("Row must contain exactly 21 protocol fields")
            original = Path(args.csv).read_bytes()
            text = io.StringIO(newline="")
            csv.DictWriter(text, fieldnames=POINT_FIELDS, lineterminator="\n").writerow(row)
            updated = original + (b"" if original.endswith(b"\n") else b"\n") + text.getvalue().encode("utf-8")
            import_manual_csv(updated, read(args.manifest), args.source_file)
            save(args.output, updated)
        elif args.command == "pack":
            binding, manifest = read(args.binding), read(args.manifest)
            # Draft placeholders must be explicitly replaced by the human reviewer.
            for obj, keys in ((manifest, ("evidence_ref",)), (binding, ("local_asset_id", "rights_basis_ref", "reviewer_ref"))):
                if any(str(obj.get(k, "")).strip().lower() in {"", "unknown", "unclear"} for k in keys):
                    raise ValueError("Human review references are still unresolved")
            package = make_package(Path(args.csv).read_bytes(), generated_at=args.generated_at,
                                   manifest=manifest, binding=binding, source_file=args.source_file)
            validate_package(package, source_file=args.source_file)
            save(args.output, package)
        elif args.command == "verify":
            validate_package(read(args.package), source_file=args.source_file)
        elif args.command == "review":
            save(args.output, review_receipt(read(args.package), read(args.decisions), source_file=args.source_file))
        elif args.command == "demo":
            out = Path(args.output_dir)
            out.mkdir(parents=True, exist_ok=False)
            data = serialize_protocol_csv(build_synthetic_demo())
            package = make_package(data, generated_at="2026-10-14T00:00:00Z", declaration=synthetic_declaration(data))
            validate_package(package)
            save(out / "simulated-handoff.json", package)
            save(out / "points.csv", data)
            save(out / "field-guide.json", field_guide())
        print("PASS: local workflow completed; human accuracy/identity/rights and Vision remain NOT_TESTED")
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f"REJECTED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
