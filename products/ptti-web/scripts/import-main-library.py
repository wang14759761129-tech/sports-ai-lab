"""Read Main artifacts once; never mount the Main worktree into Vite."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker

parser = argparse.ArgumentParser()
parser.add_argument("main_workspace", type=Path)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
main = args.main_workspace.resolve() / "products/ptti-integration"
schema_bytes = (main / "contracts/match-library-index-v0.1.schema.json").read_bytes()
validator = Draft202012Validator(json.loads(schema_bytes), format_checker=FormatChecker())
artifacts = {}
for view, name in [("INTERNAL_REVIEW", "internal-review"), ("STRICT_PUBLIC", "strict-public")]:
    raw = (main / f"generated/goal11-match-library/match-library-{name}.json").read_bytes()
    document = json.loads(raw)
    validator.validate(document)
    if document["view"] != view:
        raise ValueError("Wrong artifact view")
    if view == "STRICT_PUBLIC" and any(document[key] for key in ["matches", "video_sources", "stars", "local_video_assets", "evidence_sources"]):
        raise ValueError("Public grant evidence needs a separately reviewed consumer update; no fallback allowed")
    ids = [source["source_id"] for source in document["video_sources"]]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate source IDs")
    artifacts[name] = (raw, document)

private = root / ".alpha-qa/match-library"
private.mkdir(parents=True, exist_ok=True)
(private / "internal-review.json").write_bytes(artifacts["internal-review"][0])
(root / "public/data/match-library-strict-public.json").write_bytes(artifacts["strict-public"][0])
contracts = root / "scripts/contracts"
contracts.mkdir(exist_ok=True)
(contracts / "match-library-index-v0.1.schema.json").write_bytes(schema_bytes)
receipt = {
    "main_commit": subprocess.check_output(["git", "-C", str(args.main_workspace), "rev-parse", "HEAD"], text=True).strip(),
    "schema_sha256": hashlib.sha256(schema_bytes).hexdigest(),
    "artifacts": {name: {"sha256": hashlib.sha256(raw).hexdigest(), "view": data["view"], "video_source_count": len(data["video_sources"])} for name, (raw, data) in artifacts.items()},
    "notice": "Byte hashes identify snapshots only; they do not verify rights, match identity or playback.",
}
(private / "import-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
print(json.dumps(receipt, indent=2))
