import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from review_evidence_pack import build_review_evidence_pack, render_markdown

GOLDEN = ROOT / "fixtures/review-targets-11-8-input.json"
WINNER_EDITED = ROOT / "fixtures/goal10-7-review-evidence/winner-edited-10-9.json"
UNKNOWN_WINNER = ROOT / "fixtures/goal10-7-review-evidence/unknown-winner-p014.json"


def load_golden():
    return json.loads(GOLDEN.read_text(encoding="utf-8"))


def pack(payload, raw=None):
    return build_review_evidence_pack(
        payload, generated_at_utc="2026-10-15T00:00:00Z", raw_input_bytes=raw,
        input_name="review-targets-11-8-input.json",
    )


class ReviewEvidencePackGoal10_7Tests(unittest.TestCase):
    def test_golden_numbers_and_complete_p002_p004_p006_trace(self):
        payload = load_golden()
        result = pack(payload, GOLDEN.read_bytes())
        self.assertEqual(result["contract_version"], "ptti.review-evidence-pack/0.1")
        self.assertEqual(result["match"]["game"]["score"], {"A": 11, "B": 8})
        self.assertEqual(result["match"]["game"]["score_status"], "ENDED_BY_RULE_SCORE")
        self.assertEqual(result["sample"]["point_count"], 19)
        self.assertEqual(result["sample"]["score_by_role"]["A"]["denominator"], 19)
        self.assertEqual((result["sample"]["score_by_role"]["A"]["won_count"],
                          result["sample"]["score_by_role"]["A"]["lost_count"]), (11, 8))
        self.assertEqual((result["sample"]["service_by_role"]["A"]["won_count"],
                          result["sample"]["service_by_role"]["A"]["lost_count"],
                          result["sample"]["service_by_role"]["A"]["denominator"]), (6, 4, 10))
        self.assertEqual((result["sample"]["service_by_role"]["B"]["won_count"],
                          result["sample"]["service_by_role"]["B"]["lost_count"],
                          result["sample"]["service_by_role"]["B"]["denominator"]), (4, 5, 9))
        self.assertEqual(result["sample"]["service_basis"], "RULE_DERIVED_FROM_DECLARED_GAME_START_AND_FIRST_SERVER")
        self.assertEqual(len(result["sample"]["raw_unknown_server_point_ids"]), 19)
        self.assertEqual((result["sample"]["time_range_coverage"]["numerator"],
                          result["sample"]["time_range_coverage"]["denominator"],
                          result["sample"]["time_range_coverage"]["missing_count"]), (12, 19, 7))
        self.assertEqual(result["sample"]["unknown_stage"]["count"], 2)
        self.assertEqual(len(result["review_candidates"]), 2)
        target = next(t for t in result["review_candidates"]
                      if t["subject_role"] == "player" and t["observed_rally_stage"] == "END_AFTER_3_4_CONTACTS")
        full_ids = [payload["points"][n - 1]["point_id"] for n in (2, 4, 6)]
        self.assertEqual(target["point_ids"], full_ids)
        self.assertEqual((target["lost_count"], target["denominator"], target["unknown_count"]), (3, 3, 2))
        self.assertEqual(target["sample_status"], "INSUFFICIENT_SAMPLE")
        self.assertEqual(target["playback_eligibility"], "NOT_EVALUATED_CURRENT_SESSION")
        self.assertEqual(result["source_and_rights"]["rights_status"], "UNKNOWN")
        self.assertEqual(result["source_and_rights"]["vision_status"], "NOT_TESTED")
        self.assertEqual(result["source_and_rights"]["playback_eligibility"], "NOT_EVALUATED_CURRENT_SESSION")
        ranges = result["sample"]["time_range_coverage"]
        self.assertEqual(set(ranges["range_checked_point_ids"]) | set(ranges["missing_range_point_ids"]),
                         set(result["sample"]["point_ids"]))
        self.assertFalse(set(ranges["range_checked_point_ids"]) & set(ranges["missing_range_point_ids"]))
        self.assertEqual([pid.rsplit("/", 1)[-1] for pid in ranges["missing_range_point_ids"]],
                         [f"p{n:03d}" for n in range(13, 20)])
        for point_id in result["match"]["game"]["point_ids"]:
            self.assertIn(point_id, result["sample"]["point_ids"])

    def test_winner_change_rehashes_and_10_9_is_not_complete(self):
        original = load_golden()
        edited = json.loads(WINNER_EDITED.read_text(encoding="utf-8"))
        before, after = pack(original), pack(edited)
        self.assertNotEqual(before["input"]["canonical_input_sha256"], after["input"]["canonical_input_sha256"])
        self.assertEqual(after["match"]["game"]["score"], {"A": 10, "B": 9})
        self.assertEqual(after["match"]["game"]["score_status"], "IN_PROGRESS")
        changed_report = render_markdown(after)
        self.assertIn("10:9（当前序列尚未达到规则终局）", changed_report)
        self.assertNotIn("11:8", changed_report)

    def test_unknown_winner_preserves_unknown_and_blocks_terminal_claim(self):
        edited = json.loads(UNKNOWN_WINNER.read_text(encoding="utf-8"))
        result = pack(edited)
        self.assertEqual(result["sample"]["score_by_role"]["A"]["denominator"], 18)
        self.assertEqual(result["sample"]["unknown_winner"]["count"], 1)
        self.assertEqual(result["sample"]["unknown_stage"]["count"], 2)
        self.assertEqual(result["match"]["game"]["score_status"], "INDETERMINATE")

    def test_canonical_hash_ignores_formatting_raw_hash_does_not(self):
        raw = GOLDEN.read_bytes()
        pretty_only = raw + b"\n"
        payload_a, payload_b = json.loads(raw), json.loads(pretty_only)
        a, b = pack(payload_a, raw), pack(payload_b, pretty_only)
        self.assertEqual(a["input"]["canonical_input_sha256"], b["input"]["canonical_input_sha256"])
        self.assertNotEqual(a["input"]["raw_input_sha256"], b["input"]["raw_input_sha256"])

    def test_pack_omits_private_media_paths_and_video_bytes(self):
        result = build_review_evidence_pack(load_golden(), generated_at_utc="2026-10-15T00:00:00Z",
                                            input_name=r"C:\private\annotations\points.csv")
        wire = json.dumps(result, ensure_ascii=False)
        self.assertNotIn("C:\\", wire)
        self.assertNotIn("video_bytes", wire)
        self.assertEqual(result["input"]["input_name"], "points.csv")
        self.assertIsNone(result["source_and_rights"]["source_video_sha256"])
        self.assertIsNone(result["source_and_rights"]["timeline_id"])

    def test_cli_generates_json_and_markdown_and_protects_existing_outputs(self):
        script = ROOT / "scripts/export_review_evidence_pack.py"
        with tempfile.TemporaryDirectory() as folder:
            json_out, md_out = Path(folder) / "pack.json", Path(folder) / "pack.md"
            args = [sys.executable, str(script), "--input", str(GOLDEN),
                    "--json-output", str(json_out), "--markdown-output", str(md_out),
                    "--generated-at-utc", "2026-10-15T00:00:00Z"]
            first = subprocess.run(args, capture_output=True, text=True, check=False)
            self.assertEqual(first.returncode, 0, first.stderr)
            data = json.loads(json_out.read_text(encoding="utf-8"))
            report = md_out.read_text(encoding="utf-8")
            self.assertEqual(data["input"]["canonical_input_sha256"], pack(load_golden())["input"]["canonical_input_sha256"])
            self.assertIn("p002", report)
            self.assertIn("p004", report)
            self.assertIn("p006", report)
            second = subprocess.run(args, capture_output=True, text=True, check=False)
            self.assertEqual(second.returncode, 0, second.stderr)
            md_out.write_text("different", encoding="utf-8")
            collision = subprocess.run(args, capture_output=True, text=True, check=False)
            self.assertEqual(collision.returncode, 2)


if __name__ == "__main__":
    unittest.main()
