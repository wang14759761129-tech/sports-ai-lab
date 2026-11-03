"""Offline release-boundary tests; never compile or open a GUI."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

import build_goal23 as builder


class Goal30Tests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((builder.HERE.parent / "goal30" / "goal30-build.json").read_text("utf-8"))

    def test_new_profile_is_explicit_and_legacy_profile_stays_valid(self):
        builder.validate_config(self.config)
        legacy = json.loads(builder.CONFIG_PATH.read_text("utf-8"))
        builder.validate_config(legacy)
        self.assertEqual(legacy["version"], "0.1.8-fan-4d24c13")
        self.assertEqual(self.config["qa_port"], 4209)
        self.assertEqual(self.config["parent_release_manifest_sha256"],
                         "e2503642757df215fc7b2234d2af01edf8fbfb8411f5886b4d9ef8a2d86a833d")
        new = builder.qa_profile_path(Path("C:/Temp"), self.config["host_version"], 4209)
        old = builder.qa_profile_path(Path("C:/Temp"), legacy["host_version"], 4208)
        self.assertNotEqual(new, old)

    def test_wrong_generation_source_port_or_lowered_guard_fails_closed(self):
        for field, value in (("version", "0.1.8-fan-4d24c13"), ("host_version", "0.1.8-goal23"),
                             ("san_commit", "0" * 40), ("main_commit", "1" * 40),
                             ("qa_port", 4208), ("minimum_available_gib", 2.499),
                             ("native_bridge_status", "ENABLED")):
            with self.subTest(field=field):
                bad = copy.deepcopy(self.config)
                bad[field] = value
                with self.assertRaises(builder.BuildError):
                    builder.validate_config(bad)

    def test_all_public_and_schema_pins_are_required(self):
        for key in ("public_package_hashes", "source_schema_hashes", "main_schema_hashes",
                    "public_package_contract_versions"):
            with self.subTest(key=key):
                bad = copy.deepcopy(self.config)
                bad[key].pop(next(iter(bad[key])))
                with self.assertRaises(builder.BuildError):
                    builder.validate_config(bad)

    def test_raw_pins_reject_missing_binary_or_non_line_ending_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            file = root / "input.bin"
            file.write_bytes(b"\x00\x01\xff")
            pins = {"input.bin": builder.sha256_file(file)}
            builder.verify_raw_pins(root, pins)
            file.write_bytes(b"\x00\x01\xfe")
            with self.assertRaises(builder.BuildError):
                builder.verify_raw_pins(root, pins)
            with self.assertRaises(builder.BuildError):
                builder.verify_raw_pins(root, {"missing.json": "0" * 64})
            with self.assertRaises(builder.BuildError):
                builder.verify_raw_pins(root, {"../escape.json": "0" * 64})

    def test_staged_config_is_selected_new_identity_not_legacy_default(self):
        with tempfile.TemporaryDirectory() as temp:
            builder.write_build_config(Path(temp), self.config)
            actual = json.loads((Path(temp) / "goal23-build.json").read_text("utf-8"))
            self.assertEqual(actual, self.config)
            self.assertEqual(actual["version"], "0.1.9-fan-03df597")
            self.assertEqual(actual["public_package_hashes"], self.config["public_package_hashes"])

    def test_low_ram_stops_before_tool_process_or_staging(self):
        with patch.object(builder, "available_gib", return_value=2.499), patch.object(builder, "run_checked") as run:
            with self.assertRaises(builder.BuildBlocked):
                builder.build_candidate(types.SimpleNamespace(python="not-executed"), self.config, {})
            run.assert_not_called()

    def test_public_contract_or_compiled_lounge_absence_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            web, main, static = root / "web", root / "main", root / "dist"
            config = copy.deepcopy(self.config)
            for relative in builder.GOAL30_PUBLIC_PACKAGES:
                raw = json.dumps({"contract_version": config["public_package_contract_versions"][relative]}).encode()
                config["public_package_hashes"][relative] = hashlib.sha256(raw).hexdigest()
                for base in (web / "public", static):
                    path = base / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(raw)
            for key, base in (("source_schema_hashes", web), ("main_schema_hashes", main)):
                for relative in config[key]:
                    path = base / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text("{}", encoding="utf-8")
                    config[key][relative] = builder.sha256_file(path)
            assets = static / "assets"
            assets.mkdir()
            (assets / "app.js").write_text('"collector-lounge";"data-collector-source-id"', encoding="utf-8")
            (assets / "app.css").write_text(".collector-card{}", encoding="utf-8")
            builder.verify_goal30_inputs(config, web, main, static)
            bad = copy.deepcopy(config)
            bad["public_package_contract_versions"][next(iter(builder.GOAL30_PUBLIC_PACKAGES))] = "wrong/9"
            with self.assertRaisesRegex(builder.BuildError, "contract version"):
                builder.verify_goal30_inputs(bad, web, main, static)
            (assets / "app.js").write_text("old UI", encoding="utf-8")
            with self.assertRaisesRegex(builder.BuildError, "lacks.*implementation"):
                builder.verify_goal30_inputs(config, web, main, static)

    def test_host_checks_new_public_and_schema_identity_metadata(self):
        pins = {key: self.config[key] for key in (
            "version", "host_version", "san_commit", "main_commit", "qa_port",
            "main_inspiration_json_sha256", "static_artifact_sha256",
            "public_package_hashes", "source_schema_hashes", "main_schema_hashes")}
        module = types.ModuleType("goal23_identity")
        module.PINS = pins
        prior = sys.modules.get("goal23_identity")
        sys.modules["goal23_identity"] = module
        try:
            spec = importlib.util.spec_from_file_location("goal30_host_test", builder.HOST_TEMPLATE)
            host = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(host)
        finally:
            if prior is None:
                sys.modules.pop("goal23_identity", None)
            else:
                sys.modules["goal23_identity"] = prior
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fan = root / "fan-universe"
            (fan / "data").mkdir(parents=True)
            (root / "host").mkdir()
            (fan / "index.html").write_text("Synthetic QA only", encoding="utf-8")
            main = fan / "data" / "fan-inspiration-v0.1.json"
            main.write_text("{}", encoding="utf-8")
            (root / "host" / "PTTI-Desktop-Fan.exe").write_bytes(b"synthetic, never executable")
            pins["main_inspiration_json_sha256"] = builder.sha256_file(main)
            pins["static_artifact_sha256"] = builder.canonical_tree_sha256(fan)
            release = {
                "schema": "ptti.desktop-fan.release.v1", **pins,
                "main_json_sha256": pins["main_inspiration_json_sha256"],
                "web_static_build_sha256": pins["static_artifact_sha256"],
                "default_port": pins["qa_port"], "native_bridge_status": "DISABLED_NO_R4_BRIDGE",
                "profile_mode": "QA_ONLY_TEMP_VERSION_PORT_SCOPED", "files": builder.tree_manifest(root),
            }
            path = root / "release.json"
            path.write_text(json.dumps(release), encoding="utf-8")
            host.verify_package(root)
            for key in ("public_package_hashes", "source_schema_hashes", "main_schema_hashes"):
                bad = copy.deepcopy(release)
                bad[key][next(iter(bad[key]))] = "0" * 64
                path.write_text(json.dumps(bad), encoding="utf-8")
                with self.assertRaisesRegex(host.CandidateError, key):
                    host.verify_package(root)


if __name__ == "__main__":
    unittest.main()
