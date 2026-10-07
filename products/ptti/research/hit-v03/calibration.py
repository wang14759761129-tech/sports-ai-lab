"""Fail-closed helpers for the one-game Hit Event v0.3 calibration study."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


CALIBRATION_GAME = "game_4"
CALIBRATION_ROLE = "calibration"
MAX_CALIBRATION_VARIANTS = 5


def enforce_calibration_scope(game: str, role: str, official_split: str) -> None:
    if game != CALIBRATION_GAME or role.lower() != CALIBRATION_ROLE or official_split.upper() != "TRAIN":
        raise ValueError("ONLY_GAME_4_TRAIN_CALIBRATION_IS_ALLOWED")


def immutable_json(path: Path, value: Any) -> str:
    """Create a JSON artifact once; never replace a calibration result."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8")
    with target.open("xb") as stream:
        stream.write(payload)
    return hashlib.sha256(payload).hexdigest()


def canonical_config_sha256(config: dict[str, Any]) -> str:
    payload = json.dumps(config, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def validate_calibration_variants(variants: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = list(variants)
    if len(rows) > MAX_CALIBRATION_VARIANTS:
        raise ValueError("CALIBRATION_VARIANT_BUDGET_EXCEEDED")
    names = [row.get("name") for row in rows]
    if any(not isinstance(name, str) or not name.strip() for name in names):
        raise ValueError("CALIBRATION_VARIANT_NAME_REQUIRED")
    if len(set(names)) != len(names):
        raise ValueError("CALIBRATION_VARIANT_NAMES_MUST_BE_UNIQUE")
    return rows


def build_frozen_config_record(*, config: dict[str, Any], source_commit: str,
                               dev_metrics: dict[str, Any], calibration_metrics: dict[str, Any],
                               calibration_passed: bool, dev_backcheck_passed: bool,
                               frozen_at: str) -> dict[str, Any]:
    if not calibration_passed or not dev_backcheck_passed:
        raise ValueError("CONFIG_FREEZE_REQUIRES_CALIBRATION_AND_DEV_BACKCHECK")
    if not source_commit or not frozen_at:
        raise ValueError("CONFIG_FREEZE_PROVENANCE_REQUIRED")
    return {
        "schema": "ptti-hit-event-v0.3-frozen-config-v1",
        "status": "FROZEN_FOR_GAME_5_INTERNAL_HOLDOUT",
        "config": config,
        "config_sha256": canonical_config_sha256(config),
        "source_commit": source_commit,
        "dev_metrics": dev_metrics,
        "calibration_metrics": calibration_metrics,
        "official_test": "NOT_ACCESSED",
        "game_5": "LOCKED_NOT_ACCESSED",
        "frozen_at": frozen_at,
    }
