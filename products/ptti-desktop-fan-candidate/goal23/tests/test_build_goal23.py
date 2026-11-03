import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import types
from pathlib import Path
import socket
import tempfile
import unittest

import build_goal23 as builder


class Goal23BuilderTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(builder.CONFIG_PATH.read_text(encoding="utf-8"))

    def test_fixed_identity_and_candidate_parameters(self):
        builder.validate_config(self.config)
        self.assertEqual(self.config["san_commit"], "4d24c130cbe9dbdd66390423605c29f26a7ee792")
        self.assertEqual(self.config["main_commit"], "753edfbd1b95bc85881bdc7632e6df14a09fdc24")
        self.assertEqual(self.config["qa_port"], 4208)
        self.assertEqual(self.config["version"], "0.1.8-fan-4d24c13")

    def test_each_identity_mismatch_fails_closed(self):
        base = dict(san_commit=self.config["san_commit"], main_commit=self.config["main_commit"],
                    main_json_sha256=self.config["main_inspiration_json_sha256"],
                    static_sha256=self.config["static_artifact_sha256"])
        for key, wrong in (("san_commit", "0" * 40), ("main_commit", "1" * 40),
                           ("main_json_sha256", "2" * 64), ("static_sha256", "3" * 64)):
            with self.subTest(key=key):
                candidate = dict(base)
                candidate[key] = wrong
                with self.assertRaises(builder.BuildError):
                    builder.exact_identity(self.config, **candidate)

    def test_config_rejects_lowered_ram_and_protected_port(self):
        for field, value in (("minimum_available_gib", 2.0), ("qa_port", 4183),
                             ("native_bridge_status", "ENABLED")):
            with self.subTest(field=field):
                bad = dict(self.config)
                bad[field] = value
                with self.assertRaises(builder.BuildError):
                    builder.validate_config(bad)

    def test_resource_gate_boundary(self):
        with self.assertRaises(builder.BuildBlocked):
            builder.require_ram_guard(2.499)
        builder.require_ram_guard(2.5)

    def test_static_tree_hash_is_byte_sensitive_and_canonical(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "b.txt").write_text("B", encoding="utf-8")
            (root / "a.txt").write_text("A", encoding="utf-8")
            one = builder.canonical_tree_sha256(root)
            (root / "a.txt").write_text("A2", encoding="utf-8")
            self.assertNotEqual(one, builder.canonical_tree_sha256(root))

    def test_allowlisted_utf8_hash_distinguishes_raw_and_canonical_lf(self):
        lf = b'{"ok":true}\n'
        crlf = lf.replace(b"\n", b"\r\n")
        entry = {
            "path": "src/internal-review/evidence.json",
            "encoding": "utf-8",
            "canonical_lf_sha256": hashlib.sha256(lf).hexdigest(),
            "allowed_raw_sha256": sorted({hashlib.sha256(lf).hexdigest(), hashlib.sha256(crlf).hexdigest()}),
        }
        lf_result = builder.verify_allowlisted_utf8_text(lf, entry)
        crlf_result = builder.verify_allowlisted_utf8_text(crlf, entry)
        self.assertEqual(lf_result["raw_sha256"], hashlib.sha256(lf).hexdigest())
        self.assertEqual(crlf_result["raw_sha256"], hashlib.sha256(crlf).hexdigest())
        self.assertNotEqual(lf_result["raw_sha256"], crlf_result["raw_sha256"])
        self.assertEqual(lf_result["canonical_lf_sha256"], crlf_result["canonical_lf_sha256"])
        self.assertEqual(lf_result["line_endings"], "LF")
        self.assertEqual(crlf_result["line_endings"], "CRLF")

    def test_allowlisted_text_rejects_content_drift_and_binary_or_invalid_encodings(self):
        canonical = b'{"ok":true}\n'
        expected = hashlib.sha256(canonical).hexdigest()

        def entry_for(raw):
            return {
                "path": "src/internal-review/evidence.json",
                "encoding": "utf-8",
                "canonical_lf_sha256": expected,
                "allowed_raw_sha256": [hashlib.sha256(raw).hexdigest()],
            }

        tampered = b'{"ok":false}\n'
        with self.assertRaisesRegex(builder.BuildError, "canonical-LF SHA-256 mismatch"):
            builder.verify_allowlisted_utf8_text(tampered, entry_for(tampered))
        for label, invalid in (("invalid UTF-8", b"\xff\n"), ("binary NUL", b'{"ok":\x00}\n'),
                               ("bare CR", b'{"ok":true}\r'), ("mixed line endings", b'{"ok":true}\r\n\n')):
            with self.subTest(label=label):
                with self.assertRaises(builder.BuildError):
                    builder.verify_allowlisted_utf8_text(invalid, entry_for(invalid))

    def test_allowlisted_text_path_must_exist_and_be_the_reviewed_path(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaisesRegex(builder.BuildError, "missing"):
                builder.verify_allowlisted_text_inputs(root, self.config)
            wrong = dict(self.config)
            wrong["canonical_lf_text_inputs"] = [dict(entry) for entry in self.config["canonical_lf_text_inputs"]]
            wrong["canonical_lf_text_inputs"][0]["path"] = "src/elsewhere.json"
            with self.assertRaisesRegex(builder.BuildError, "allowlist"):
                builder.validate_config(wrong)

    def test_static_tree_hash_detects_binary_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            asset = root / "asset.bin"
            asset.write_bytes(b"\x00\x01\xfe")
            before = builder.canonical_tree_sha256(root)
            asset.write_bytes(b"\x00\x01\xff")
            self.assertNotEqual(before, builder.canonical_tree_sha256(root))

    def test_parent_release_integrity_and_rollback_pin(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            payload = root / "payload.txt"
            payload.write_text("kept old release", encoding="utf-8")
            manifest = {"files": {"payload.txt": hashlib.sha256(payload.read_bytes()).hexdigest()}}
            path = root / "release.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            expected = builder.sha256_file(path)
            builder.verify_parent_release(root, expected)
            payload.write_text("changed", encoding="utf-8")
            with self.assertRaises(builder.BuildError):
                builder.verify_parent_release(root, expected)

    def test_package_path_traversal_rejected(self):
        with self.assertRaises(builder.BuildError):
            builder.safe_file_map({"../live.db": "0" * 64})
        with self.assertRaises(builder.BuildError):
            builder.safe_file_map({"<LOCAL_USER_ROOT>": "0" * 64})

    def test_port_preflight_does_not_take_an_occupied_port(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            sock.listen(1)
            port = sock.getsockname()[1]
            self.assertFalse(builder.port_is_free(port))

    def test_profile_is_scoped_under_temp_version_and_port(self):
        profile = builder.qa_profile_path(Path("C:/Temp"), self.config["host_version"], self.config["qa_port"])
        self.assertEqual(profile.parts[-4:], ("PTTI-GOAL23-DesktopFan-QA", "0.1.8-goal23", "Port-4208", "WebView2"))
        with self.assertRaises(builder.BuildError):
            builder.qa_profile_path(Path("C:/Temp"), self.config["host_version"], 4183)

    def test_new_host_contains_no_live_data_or_production_profile_code(self):
        source = builder.HOST_TEMPLATE.read_text(encoding="utf-8").casefold()
        for token in builder.FORBIDDEN_HOST_TOKENS:
            with self.subTest(token=token):
                self.assertNotIn(token.casefold(), source)

    def test_host_package_verifier_accepts_exact_synthetic_package_and_rejects_drift(self):
        identity = {
            "version": self.config["version"], "host_version": self.config["host_version"],
            "san_commit": self.config["san_commit"], "main_commit": self.config["main_commit"],
            "main_inspiration_json_sha256": "0" * 64,
            "static_artifact_sha256": "", "qa_port": self.config["qa_port"],
        }
        module = types.ModuleType("goal23_identity")
        module.PINS = identity
        prior = sys.modules.get("goal23_identity")
        sys.modules["goal23_identity"] = module
        try:
            spec = importlib.util.spec_from_file_location("goal23_host_test", builder.HOST_TEMPLATE)
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
            data = fan / "data"
            host_dir = root / "host"
            data.mkdir(parents=True)
            host_dir.mkdir()
            (fan / "index.html").write_text("<main>synthetic</main>", encoding="utf-8")
            main_json = data / "fan-inspiration-v0.1.json"
            main_json.write_text("synthetic Main JSON", encoding="utf-8")
            exe = host_dir / "PTTI-Desktop-Fan.exe"
            exe.write_bytes(b"new synthetic Host, not the 0.1.7 EXE")
            identity["main_inspiration_json_sha256"] = builder.sha256_file(main_json)
            identity["static_artifact_sha256"] = host.tree_sha256(fan)
            files = builder.tree_manifest(root)
            manifest = {
                "schema": "ptti.desktop-fan.release.v1", "version": identity["version"],
                "host_version": identity["host_version"], "san_commit": identity["san_commit"],
                "main_commit": identity["main_commit"], "main_json_sha256": identity["main_inspiration_json_sha256"],
                "web_static_build_sha256": identity["static_artifact_sha256"], "default_port": identity["qa_port"],
                "native_bridge_status": "DISABLED_NO_R4_BRIDGE", "profile_mode": "QA_ONLY_TEMP_VERSION_PORT_SCOPED",
                "files": files,
            }
            (root / "release.json").write_text(json.dumps(manifest), encoding="utf-8")
            host.verify_package(root)
            (fan / "index.html").write_text("tampered", encoding="utf-8")
            with self.assertRaises(host.CandidateError):
                host.verify_package(root)

    def test_staged_verify_only_does_not_mutate_hashed_package(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "package"
            source = root / "source"
            fan = root / "fan-universe"
            data = fan / "data"
            host_dir = root / "host"
            data.mkdir(parents=True)
            source.mkdir()
            host_dir.mkdir()
            host_script = source / "desktop_host.py"
            shutil.copy2(builder.HOST_TEMPLATE, host_script)
            (fan / "index.html").write_text("<main>synthetic</main>", encoding="utf-8")
            main_json = data / "fan-inspiration-v0.1.json"
            main_json.write_text("synthetic Main JSON", encoding="utf-8")
            exe = host_dir / "PTTI-Desktop-Fan.exe"
            exe.write_bytes(b"new synthetic Host")

            pins = {
                "version": self.config["version"],
                "host_version": self.config["host_version"],
                "san_commit": self.config["san_commit"],
                "main_commit": self.config["main_commit"],
                "main_inspiration_json_sha256": builder.sha256_file(main_json),
                "static_artifact_sha256": builder.canonical_tree_sha256(fan),
                "qa_port": self.config["qa_port"],
            }
            (source / "goal23_identity.py").write_text("PINS = " + repr(pins) + "\n", encoding="utf-8")
            files = builder.package_files(root)
            manifest = {
                "schema": "ptti.desktop-fan.release.v1",
                "version": pins["version"],
                "host_version": pins["host_version"],
                "san_commit": pins["san_commit"],
                "main_commit": pins["main_commit"],
                "main_json_sha256": pins["main_inspiration_json_sha256"],
                "web_static_build_sha256": pins["static_artifact_sha256"],
                "default_port": pins["qa_port"],
                "native_bridge_status": "DISABLED_NO_R4_BRIDGE",
                "profile_mode": "QA_ONLY_TEMP_VERSION_PORT_SCOPED",
                "files": files,
            }
            (root / "release.json").write_text(json.dumps(manifest), encoding="utf-8")

            env = os.environ.copy()
            env.pop("PYTHONDONTWRITEBYTECODE", None)
            unguarded = subprocess.run(
                [sys.executable, str(host_script), "--verify-only", "--package-root", str(root)],
                capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
            )
            self.assertNotEqual(unguarded.returncode, 0)
            self.assertIn("Candidate package file hash verification failed", unguarded.stderr)
            bytecode_dir = source / "__pycache__"
            self.assertTrue(bytecode_dir.is_dir())
            self.assertTrue(any(bytecode_dir.glob("goal23_identity.*.pyc")))

            shutil.rmtree(bytecode_dir)
            restored = builder.package_files(root)
            restored.pop("release.json", None)
            self.assertEqual(restored, files)
            guarded_command = builder.host_verification_command(sys.executable, host_script, root)
            self.assertEqual(guarded_command[1], "-B")
            guarded = subprocess.run(
                guarded_command, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
            )
            self.assertEqual(guarded.returncode, 0, guarded.stdout + guarded.stderr)
            self.assertFalse(bytecode_dir.exists())

    def test_old_candidate_exe_is_not_a_builder_input(self):
        source = builder.build_candidate.__code__.co_consts
        self.assertNotIn("host/PTTI-Desktop-Fan.exe", source)
        text = Path(builder.__file__).read_text(encoding="utf-8")
        self.assertIn('"--name", "PTTI-Desktop-Fan"', text)
        self.assertIn('dist_root / "PTTI-Desktop-Fan"', text)
        self.assertNotIn("parent_release / \"host\"", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
