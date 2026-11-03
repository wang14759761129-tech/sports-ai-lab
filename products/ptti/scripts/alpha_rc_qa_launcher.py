"""Opt-in, fresh-session-only launcher for archived Run 38380192524.

Default execution is read-only preflight. --launch requires separate human
authorization; no resume, install, desktop shortcut or deployment operation.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys


SOURCE_COMMIT = "550a410e7fc71eb425f39a618277f209515a4ef8"
EXE_NAME = "PTTI-Video-First-R4-Preview.exe"
EXE_SHA256 = "a9928b798bda83e9a5dc5a8f111be503c4cd48723ffd73a65eb9eb721f7d0b23"
MANIFEST_SHA256 = "88fe54bdc3509471b943ff0035a943f83696b038746690c5dee54690381eb545"
BUILD_INFO_SHA256 = "3b620e9431a83d1609781aba4c3837d288cce71d296d2e92bfce55f4c5be3713"
BASE_LAUNCHER_SHA256 = "2ab47d127aeee1347567a8d9b987398564cde0706a06653ca3336fb8bce01f7f"


def load_base():
    path = Path(__file__).with_name("candidate_qa_launcher.py")
    # Git checkout line endings must not invalidate the reviewed text identity.
    if hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest() != BASE_LAUNCHER_SHA256:
        raise RuntimeError("RC_QA_BASE_LAUNCHER_CHANGED")
    name = "_ptti_verified_rc_qa_base"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def prepare(base, candidate_dir):
    pin = base.CandidatePin(SOURCE_COMMIT, EXE_NAME, EXE_SHA256,
                            MANIFEST_SHA256, BUILD_INFO_SHA256)
    plan = base.prepare_new_plan(candidate_dir, expected=pin)
    info = json.loads((plan.candidate.directory / "build-info.json").read_text(encoding="utf-8-sig"))
    if (info.get("environment") != "DEVELOPMENT" or info.get("source_tree_dirty") is not False
            or info.get("official_release") is not False):
        raise base.QALauncherError("RC_QA_PACKAGE_MODE_INVALID")
    manifest = json.loads((plan.candidate.directory / "manifest.json").read_text(encoding="utf-8-sig"))
    actual = {p.relative_to(plan.candidate.directory).as_posix()
              for p in plan.candidate.directory.rglob("*") if p.is_file()}
    if actual != set(manifest["files"]) | {"manifest.json"}:
        raise base.QALauncherError("RC_QA_UNEXPECTED_FILES")
    base._require_no_running_candidate(plan.candidate)
    base._require_resource_gate()
    return plan


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-dir", required=True)
    parser.add_argument("--launch", action="store_true", help="Explicitly start one fresh isolated QA session")
    args = parser.parse_args(argv)
    try:
        base = load_base()
        plan = prepare(base, args.candidate_dir)
        if not args.launch:
            print(f"RC_QA_PREFLIGHT_OK source={SOURCE_COMMIT} mode=new database=OS_TEMP NOT_STARTED")
            return 0
        # Recheck dynamic conditions immediately before the existing isolated launch.
        base._require_no_running_candidate(plan.candidate)
        base._require_resource_gate()
        pid = base._launch(plan)
        print(f"RC_QA_STARTED source={SOURCE_COMMIT} pid={pid} session={plan.session_directory.name}")
        return 0
    except Exception as exc:
        print(getattr(exc, "code", "RC_QA_PREFLIGHT_FAILED"), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
