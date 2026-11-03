"""Read-only, fail-closed consumer interface for Web integrations.

The module consumes an already exported v0.2 contract. It never opens a
database, fetches a URL, reads media, or writes files. ``review`` is for a
trusted review surface; ``public`` additionally requires explicit listing and
external-viewing permission. Local assets and synthetic fixtures are omitted
from both views.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Literal

from jsonschema import Draft202012Validator, FormatChecker

from adapters import (
    CONTRACT_VERSION,
    UnsupportedContractVersion,
    _is_synthetic,
    require_exact_contract_version,
    to_web_safe_payload,
    validate_contract_integrity,
)


PACKAGE = Path(__file__).resolve().parent
SCHEMA_PATH = PACKAGE / "contracts" / "match-media-v0.2.schema.json"
View = Literal["review", "public"]


class InvalidContract(ValueError):
    """Contract failed schema or referential-integrity validation."""


def load_contract(path: str | Path) -> dict[str, Any]:
    """Read one JSON export. The caller retains ownership of the source file."""
    with Path(path).open("r", encoding="utf-8") as stream:
        payload = json.load(stream)
    if not isinstance(payload, dict):
        raise InvalidContract("Contract root must be an object")
    return payload


def _validate_contract(contract: dict[str, Any]) -> None:
    require_exact_contract_version(contract, CONTRACT_VERSION)
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(contract),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        first = errors[0]
        location = "/".join(str(part) for part in first.absolute_path) or "/"
        raise InvalidContract(f"Schema validation failed at {location}: {first.message}")
    try:
        validate_contract_integrity(contract)
    except (ValueError, TypeError, KeyError) as exc:
        raise InvalidContract(f"Contract integrity validation failed: {exc}") from exc


def consume_contract(
    contract: dict[str, Any],
    *,
    view: View,
    match_id: str | None = None,
    discipline: str | None = None,
    search: str | None = None,
) -> dict[str, Any]:
    """Return a new, read-only v0.2 payload suitable for the selected Web view.

    ``review`` retains real-record rights and evidence states, including
    UNKNOWN/NOT_TESTED, without implying publication permission. ``public``
    requires explicit metadata-listing and external-viewing ALLOWED statuses.
    Filters are applied after policy projection and never infer identities.
    """
    if view not in {"review", "public"}:
        raise ValueError("view must be exactly 'review' or 'public'")
    _validate_contract(contract)

    if view == "public":
        # The existing policy projector selects source dictionaries by
        # reference; detach it before any Web-specific filtering.
        projected = copy.deepcopy(to_web_safe_payload(contract))
    else:
        matches = [row for row in contract["matches"] if not _is_synthetic(row)]
        real_match_ids = {row["match_id"] for row in matches}
        sources = [
            row for row in contract["video_sources"]
            if not _is_synthetic(row)
            and (row["match_id"] is None or row["match_id"] in real_match_ids)
        ]
        source_ids = {row["source_id"] for row in sources}
        linked_match_ids = {row["match_id"] for row in sources if row["match_id"]}
        projected = {
            "contract_version": CONTRACT_VERSION,
            "matches": [row for row in matches if row["match_id"] in linked_match_ids],
            "video_sources": sources,
            # LocalVideoAsset contains a local locator and is never Web data.
            "local_video_assets": [],
            "timeline_mappings": [
                row for row in contract["timeline_mappings"]
                if row["from_source_id"] in source_ids
                and row["to_source_id"] in source_ids
                and row["status"] == "HUMAN_VERIFIED"
                and row["evidence_refs"]
            ],
        }

    # Detach review rows too; the review branch initially selects input rows
    # by reference, and downstream thumbnail policy must remain read-only.
    projected = copy.deepcopy(projected)

    # Never expose a thumbnail URL unless its separate display permission is
    # explicitly granted. The permission state itself remains unchanged.
    for source in projected["video_sources"]:
        if source["rights"]["thumbnail_display"] != "ALLOWED":
            source.pop("thumbnail_url", None)

    if match_id is not None:
        projected["matches"] = [row for row in projected["matches"] if row["match_id"] == match_id]
        projected["video_sources"] = [row for row in projected["video_sources"] if row["match_id"] == match_id]
        retained = {row["source_id"] for row in projected["video_sources"]}
        projected["timeline_mappings"] = [
            row for row in projected["timeline_mappings"]
            if row["from_source_id"] in retained and row["to_source_id"] in retained
        ]

    if discipline is not None:
        normalized = discipline.upper()
        if normalized not in {"MS", "WS", "MD", "WD", "XD", "UNKNOWN"}:
            raise ValueError("discipline must be MS, WS, MD, WD, XD, or UNKNOWN")
        match_rows = [row for row in projected["matches"] if row["discipline"] == normalized]
        retained_matches = {row["match_id"] for row in match_rows}
        projected["matches"] = match_rows
        projected["video_sources"] = [
            row for row in projected["video_sources"] if row["match_id"] in retained_matches
        ]
        retained_sources = {row["source_id"] for row in projected["video_sources"]}
        projected["timeline_mappings"] = [
            row for row in projected["timeline_mappings"]
            if row["from_source_id"] in retained_sources and row["to_source_id"] in retained_sources
        ]

    if search is not None:
        needle = search.strip().casefold()
        if not needle:
            raise ValueError("search must not be empty")
        sources_by_match: dict[str, list[dict[str, Any]]] = {}
        for source in projected["video_sources"]:
            if source["match_id"]:
                sources_by_match.setdefault(source["match_id"], []).append(source)
        selected = []
        for match in projected["matches"]:
            searchable = [match.get("match_id", ""), match.get("round") or "", match.get("result") or ""]
            searchable.extend(str(value) for value in match.get("participant_names_unassigned", []))
            event = match.get("event", {})
            searchable.extend(str(event.get(key) or "") for key in ("name", "year", "event_id"))
            for source in sources_by_match.get(match["match_id"], []):
                searchable.extend((source.get("platform", ""), source.get("publisher") or "", source.get("canonical_url", "")))
            if any(needle in value.casefold() for value in searchable):
                selected.append(match)
        projected["matches"] = selected
        selected_ids = {row["match_id"] for row in selected}
        projected["video_sources"] = [
            row for row in projected["video_sources"] if row["match_id"] in selected_ids
        ]
        selected_sources = {row["source_id"] for row in projected["video_sources"]}
        projected["timeline_mappings"] = [
            row for row in projected["timeline_mappings"]
            if row["from_source_id"] in selected_sources and row["to_source_id"] in selected_sources
        ]

    # Return detached data so a consumer cannot mutate the caller's export.
    return projected
