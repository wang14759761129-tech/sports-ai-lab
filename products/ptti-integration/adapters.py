"""Conservative adapters for the PTTI match/media interchange contract.

Only explicitly supplied, allow-listed fields cross a boundary. This module
uses the standard library and never opens a database or a local media file.
"""

from __future__ import annotations

from datetime import date, datetime
import math
import re
from typing import Any
from urllib.parse import parse_qs, urlparse


CONTRACT_VERSION = "ptti.match-media/0.2"
DISCIPLINES = {"MS", "WS", "MD", "WD", "XD", "UNKNOWN"}
PERMISSIONS = {"ALLOWED", "DENIED", "UNKNOWN", "PENDING_REVIEW"}
REVIEW_STATES = {"VERIFIED", "REVIEW_REQUIRED", "UNKNOWN", "NOT_TESTED", "BLOCKED"}
CONTENT_TYPES = {"FULL_MATCH", "HIGHLIGHTS", "SESSION", "CLIP", "ARTICLE", "UNKNOWN"}
RESOURCE_KINDS = {
    "OFFICIAL_EVENT_PAGE",
    "OFFICIAL_MATCH_PAGE",
    "VIDEO_PAGE",
    "BROADCAST_SESSION",
    "CLIP",
    "UNKNOWN",
}


class UnsupportedContractVersion(ValueError):
    """Raised when a consumer receives a contract version it did not declare."""

    code = "UNSUPPORTED_CONTRACT_VERSION"

    def __init__(self, expected_version: str, received_version: Any):
        self.expected_version = expected_version
        self.received_version = (
            received_version if isinstance(received_version, str) else None
        )
        received = self.received_version or "<missing-or-invalid>"
        super().__init__(
            f"{self.code}: expected {expected_version}; received {received}"
        )


def require_exact_contract_version(payload: Any, expected_version: str) -> str:
    """Fail closed before a consumer interprets a payload from another version."""
    received = payload.get("contract_version") if isinstance(payload, dict) else None
    if not isinstance(expected_version, str) or not expected_version.strip():
        raise ValueError("expected_version must be a non-empty string")
    if received != expected_version:
        raise UnsupportedContractVersion(expected_version, received)
    return received


def _text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _safe_id(value: Any) -> str | None:
    text = _text(value)
    if text and len(text) <= 160 and re.fullmatch(r"[A-Za-z0-9._:-]+", text):
        return text
    return None


def _https_url(value: Any) -> str | None:
    text = _text(value)
    if not text:
        return None
    try:
        parsed = urlparse(text)
        if parsed.scheme == "https" and parsed.hostname and not parsed.username and not parsed.password:
            return text
    except ValueError:
        pass
    return None


def _safe_urls(values: Any) -> list[str]:
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, (list, tuple)):
        return []
    output: list[str] = []
    for value in values:
        url = _https_url(value)
        if url and url not in output:
            output.append(url)
    return output


def _date_or_datetime(value: Any) -> str | None:
    text = _text(value)
    if not text:
        return None
    try:
        date.fromisoformat(text)
        return text
    except ValueError:
        pass
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return None
        return text
    except ValueError:
        return None


def _finite_number(value: Any) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(value)
    except (OverflowError, TypeError, ValueError):
        return False


def _nonnegative_time(value: Any) -> int | float | None:
    return value if _finite_number(value) and value >= 0 else None


def _verified_at(value: Any) -> str | None:
    """Accept only an ISO calendar date or timezone-qualified ISO datetime."""
    text = _text(value)
    if not text:
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        try:
            date.fromisoformat(text)
            return text
        except ValueError:
            return None
    if not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})",
        text,
    ):
        return None
    return _date_or_datetime(text)


def _is_wtt_official_url(value: Any) -> bool:
    url = _https_url(value)
    if not url:
        return False
    hostname = (urlparse(url).hostname or "").casefold()
    return hostname == "worldtabletennis.com" or hostname.endswith(".worldtabletennis.com")


def _event_id_from_record(record: dict[str, Any]) -> str | None:
    explicit = _safe_id(record.get("eventId"))
    raw_evidence = record.get("sourceEvidence")
    evidence_urls = raw_evidence if isinstance(raw_evidence, (list, tuple)) else []
    candidate_urls = _safe_urls([record.get("platformUrl"), *evidence_urls])
    event_ids: set[str] = set()
    for url in candidate_urls:
        if not _is_wtt_official_url(url):
            continue
        for value in parse_qs(urlparse(url).query).get("eventId", []):
            if re.fullmatch(r"\d{1,16}", value):
                event_ids.add(value)
    if explicit:
        return explicit if not event_ids or event_ids == {explicit} else None
    return next(iter(event_ids)) if len(event_ids) == 1 else None


def _source_evidence_verified(record: dict[str, Any], target_url: str | None, source_urls: list[str]) -> bool:
    """Require the exact target plus an official WTT event page for this event."""
    if not target_url or target_url not in source_urls:
        return False
    event_id = _event_id_from_record(record)
    if not event_id:
        return False
    for url in source_urls:
        if not _is_wtt_official_url(url):
            continue
        parsed = urlparse(url)
        if parsed.path.rstrip("/").casefold() != "/eventinfo":
            continue
        if event_id in parse_qs(parsed.query).get("eventId", []):
            return True
    return False


def _title_matches_match(record: dict[str, Any], page_title: str | None) -> bool | None:
    if not page_title:
        return None
    event = _text(record.get("event"))
    players = record.get("players")
    names = [name.strip() for name in players if isinstance(name, str) and name.strip()] if isinstance(players, list) else []
    title = page_title.casefold()
    return bool(event and len(names) >= 2 and event.casefold() in title and all(name.casefold() in title for name in names))


def _permission(value: Any) -> str:
    if value is True:
        return "ALLOWED"
    if value is False:
        return "DENIED"
    if isinstance(value, str) and value.upper() in PERMISSIONS:
        return value.upper()
    if isinstance(value, str) and value.upper() in {"EMBED_BLOCKED", "FORBIDDEN"}:
        return "DENIED"
    return "UNKNOWN"


def _review_state(value: Any) -> str:
    return value.upper() if isinstance(value, str) and value.upper() in REVIEW_STATES else "UNKNOWN"


def _discipline(value: Any) -> str:
    return value.upper() if isinstance(value, str) and value.upper() in DISCIPLINES else "UNKNOWN"


def _resource_kind(value: Any) -> str:
    return value.upper() if isinstance(value, str) and value.upper() in RESOURCE_KINDS else "UNKNOWN"


def _content_type(value: Any) -> str:
    return value.upper() if isinstance(value, str) and value.upper() in CONTENT_TYPES else "UNKNOWN"


def _rational(value: Any) -> dict[str, int] | None:
    if not isinstance(value, dict):
        return None
    numerator = value.get("numerator", value.get("num"))
    denominator = value.get("denominator", value.get("den"))
    if (
        isinstance(numerator, int)
        and not isinstance(numerator, bool)
        and numerator > 0
        and isinstance(denominator, int)
        and not isinstance(denominator, bool)
        and denominator > 0
    ):
        return {"numerator": numerator, "denominator": denominator}
    return None


def _rights(values: dict[str, Any]) -> dict[str, Any]:
    basis_urls = _safe_urls(values.get("basis_urls"))
    reviewed_at = _date_or_datetime(values.get("reviewed_at"))
    return {
        "metadata_listing": _permission(values.get("metadata_listing")),
        "thumbnail_display": _permission(values.get("thumbnail_display")),
        "external_viewing": _permission(values.get("external_viewing")),
        "embedding": _permission(values.get("embedding")),
        "local_analysis": _permission(values.get("local_analysis")),
        "model_training": _permission(values.get("model_training")),
        "redistribution": _permission(values.get("redistribution")),
        "basis_urls": basis_urls,
        "reviewed_at": reviewed_at,
    }


def _provenance(
    method: str,
    source_urls: Any,
    *,
    recorded_at: Any = None,
    review_status: Any = None,
    reviewer_ref: Any = None,
    evidence_refs: Any = None,
) -> dict[str, Any]:
    refs = evidence_refs if isinstance(evidence_refs, (list, tuple)) else []
    return {
        "method": method,
        "source_urls": _safe_urls(source_urls),
        "recorded_at": _date_or_datetime(recorded_at),
        "review_status": _review_state(review_status),
        "reviewer_ref": _safe_id(reviewer_ref),
        "evidence_refs": list(dict.fromkeys(ref for item in refs if (ref := _safe_id(item)))),
    }


def _adapter_method(base: str, source: dict[str, Any]) -> str:
    """Keep test-only fixture provenance visible to every downstream policy."""
    if source.get("fixture_only") is True:
        return f"synthetic-fixture:{base}"
    return base


def _is_synthetic(record: Any) -> bool:
    if not isinstance(record, dict):
        return False
    provenance = record.get("provenance")
    method = provenance.get("method") if isinstance(provenance, dict) else None
    return isinstance(method, str) and method.startswith("synthetic-fixture:")


def validate_contract_integrity(contract: dict[str, Any]) -> dict[str, int]:
    """Validate explicit IDs and links without inferring identity from labels."""
    require_exact_contract_version(contract, CONTRACT_VERSION)
    matches = contract.get("matches")
    sources = contract.get("video_sources")
    assets = contract.get("local_video_assets")
    mappings = contract.get("timeline_mappings")
    if not all(isinstance(value, list) for value in (matches, sources, assets, mappings)):
        raise ValueError("Contract collections must be arrays")

    def indexed(rows: list[Any], key: str, label: str) -> dict[str, dict[str, Any]]:
        output: dict[str, dict[str, Any]] = {}
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError(f"{label} rows must be objects")
            identifier = row.get(key)
            if not isinstance(identifier, str) or not identifier:
                raise ValueError(f"{label} requires a stable {key}")
            if identifier in output:
                raise ValueError(f"Duplicate {label} id: {identifier}")
            output[identifier] = row
        return output

    match_by_id = indexed(matches, "match_id", "Match")
    source_by_id = indexed(sources, "source_id", "VideoSource")
    asset_by_id = indexed(assets, "local_asset_id", "LocalVideoAsset")

    def check_match_reference(row: dict[str, Any], entity: str) -> None:
        match_id = row.get("match_id")
        if match_id is None:
            return
        match = match_by_id.get(match_id)
        if match is None:
            raise ValueError(f"{entity} references missing Match id: {match_id}")
        if _is_synthetic(row) != _is_synthetic(match):
            raise ValueError(f"Synthetic/real Match link rejected for {entity}: {match_id}")

    for source in sources:
        check_match_reference(source, "VideoSource")
        source_provenance = source.get("provenance")
        source_method = (
            source_provenance.get("method")
            if isinstance(source_provenance, dict)
            else None
        )
        if source.get("match_id") is not None and source_method not in {
            "web-match-record-adapter",
            "synthetic-fixture:web-match-record-adapter",
        }:
            match = match_by_id[source["match_id"]]
            provenance = source_provenance if isinstance(source_provenance, dict) else {}
            if (
                match.get("identity_status") != "VERIFIED"
                or source.get("match_link_status") != "VERIFIED"
                or provenance.get("review_status") != "VERIFIED"
                or not provenance.get("evidence_refs")
            ):
                raise ValueError(
                    "Cross-system VideoSource Match association requires verified identity and reviewed evidence refs"
                )
    for asset in assets:
        check_match_reference(asset, "LocalVideoAsset")
        if asset.get("match_id") is not None:
            match = match_by_id[asset["match_id"]]
            provenance = asset.get("provenance", {})
            if (
                match.get("identity_status") != "VERIFIED"
                or provenance.get("review_status") != "VERIFIED"
                or not provenance.get("evidence_refs")
            ):
                raise ValueError(
                    "LocalVideoAsset Match association requires a verified Match identity and reviewed evidence refs"
                )
            if not any(source.get("match_id") == asset["match_id"] for source in sources):
                raise ValueError("LocalVideoAsset Match association has no matching VideoSource")

    for mapping in mappings:
        if not isinstance(mapping, dict):
            raise ValueError("Timeline mappings must be objects")
        from_id = mapping.get("from_source_id")
        to_id = mapping.get("to_source_id")
        if from_id not in source_by_id or to_id not in source_by_id:
            raise ValueError("Timeline mapping references a missing VideoSource")
        if mapping.get("status") == "HUMAN_VERIFIED":
            left = source_by_id[from_id]
            right = source_by_id[to_id]
            if not left.get("match_id") or left.get("match_id") != right.get("match_id"):
                raise ValueError("Verified timeline mapping requires one explicit shared Match id")
            if _is_synthetic(left) != _is_synthetic(right):
                raise ValueError("Verified timeline mapping cannot cross synthetic/real records")

    return {
        "matches": len(matches),
        "video_sources": len(sources),
        "local_video_assets": len(assets),
        "timeline_mappings": len(mappings),
    }


def _empty_page(status: str = "NOT_TESTED") -> dict[str, Any]:
    return {
        "status": status,
        "checked_at": None,
        "final_url": None,
        "http_status": None,
        "notes": "",
    }


def _empty_external(status: str = "NOT_TESTED") -> dict[str, Any]:
    return {
        "status": status,
        "checked_at": None,
        "requested_url": None,
        "final_url": None,
        "url_exact_match": None,
        "time_first_seconds": None,
        "time_last_seconds": None,
        "visual_frames_changed": None,
        "page_title": None,
        "title_matches_match": None,
        "publisher": None,
        "publisher_verified": None,
        "source_evidence_urls": [],
        "source_evidence_verified": None,
        "login_prompt_seen": None,
        "region_prompt_seen": None,
        "verification_prompt_seen": None,
        "audio_status": "UNKNOWN",
        "audio_confirmation_observed": None,
        "territory": None,
        "evidence_ref": None,
        "validation_failures": [],
        "notes": "",
    }


def _empty_embed(status: str = "NOT_TESTED") -> dict[str, Any]:
    return {
        "status": status,
        "checked_at": None,
        "error_code": None,
        "evidence_ref": None,
        "notes": "",
    }


def _empty_native(status: str = "NOT_TESTED") -> dict[str, Any]:
    return {
        "status": status,
        "checked_at": None,
        "app_git_sha": None,
        "package_sha256": None,
        "source_sha256": None,
        "evidence_ref": None,
        "notes": "",
    }


def _external_evidence_from_web(record: dict[str, Any], target_url: str | None) -> dict[str, Any]:
    claimed = str(record.get("playbackStatus") or "NOT_TESTED").upper()
    tested = record.get("playbackTested") is True
    evidence = record.get("playbackEvidence")
    if not isinstance(evidence, dict):
        evidence = {}

    first = evidence.get("timeAtFirstObservationSeconds")
    last = evidence.get("timeAtFinalObservationSeconds")
    final_url = _https_url(evidence.get("finalUrl"))
    target = _https_url(target_url)
    checked_at = _verified_at(evidence.get("testedAt"))
    page_title = _text(evidence.get("pageTitle"))
    publisher = _text(evidence.get("publisher"))
    source_urls = _safe_urls(record.get("sourceEvidence"))
    exact_url_match = final_url == target if final_url and target else None
    source_evidence_verified = _source_evidence_verified(record, target, source_urls) if source_urls else None
    publisher_verified = (
        bool(
            "world table tennis" in publisher.casefold()
            and "verified youtube channel" in publisher.casefold()
            and source_evidence_verified is True
        )
        if publisher is not None else None
    )
    title_matches_match = _title_matches_match(record, page_title)
    audio_claim = evidence.get("audibleOutputConfirmed")
    # The Web field says whether audible output was confirmed. A false or
    # missing value means audio remains unknown; it is not proof of silence.
    audio_status = "AUDIO_CONFIRMED" if audio_claim is True else "UNKNOWN"
    failures: list[str] = []
    eligible_route = record.get("routeType") == "video-page"

    if claimed == "PLAYBACK_PASS":
        if not tested:
            failures.append("PLAYBACK_NOT_MARKED_TESTED")
        if not eligible_route:
            failures.append("ROUTE_NOT_VIDEO_PAGE")
        if not target:
            failures.append("TARGET_URL_MISSING")
        if not final_url:
            failures.append("FINAL_URL_MISSING")
        elif exact_url_match is not True:
            failures.append("FINAL_URL_MISMATCH")
        if target and target not in source_urls:
            failures.append("SOURCE_EVIDENCE_MISSING_TARGET")
        elif source_evidence_verified is not True:
            failures.append("OFFICIAL_MATCH_SOURCE_MISSING")
        if not _finite_number(first) or not _finite_number(last) or first < 0 or last < first:
            failures.append("TIMELINE_OBSERVATION_INVALID")
        elif last - first < 5:
            failures.append("TIMELINE_ADVANCE_LT_5_SECONDS")
        if evidence.get("visualFramesChanged") is not True:
            failures.append("VISUAL_FRAMES_UNCHANGED")
        if not checked_at:
            failures.append("VERIFICATION_TIME_MISSING")
        if not page_title:
            failures.append("PAGE_TITLE_MISSING")
        elif title_matches_match is not True:
            failures.append("PAGE_TITLE_MISMATCH")
        if publisher_verified is not True:
            failures.append("PUBLISHER_UNVERIFIED")
        for field, failure_code in (
            ("loginPromptSeen", "LOGIN_PROMPT"),
            ("regionPromptSeen", "REGION_PROMPT"),
            ("verificationPromptSeen", "VERIFICATION_PROMPT"),
        ):
            if evidence.get(field) is not False:
                failures.append(f"{failure_code}_NOT_EXPLICITLY_CLEAR")
        if not isinstance(audio_claim, bool):
            failures.append("AUDIO_STATUS_MISSING")
        if not isinstance(evidence.get("territory"), str):
            failures.append("TERRITORY_STATUS_MISSING")
    if claimed == "PLAYBACK_PASS":
        status = "EXTERNAL_VIDEO_PAGE_VISUAL_PASS" if not failures else "REVIEW_REQUIRED"
    elif claimed == "PLAYBACK_FAIL":
        status = "EXTERNAL_VIDEO_PAGE_VISUAL_FAIL" if tested else "REVIEW_REQUIRED"
    elif claimed == "RESTRICTED":
        status = "RESTRICTED"
    elif claimed == "BLOCKED":
        status = "BLOCKED"
    elif claimed == "NOT_TESTED":
        status = "NOT_TESTED"
    else:
        status = "REVIEW_REQUIRED" if tested else "UNKNOWN"

    return {
        "status": status,
        "checked_at": checked_at,
        "requested_url": target,
        "final_url": final_url,
        "url_exact_match": exact_url_match,
        "time_first_seconds": _nonnegative_time(first),
        "time_last_seconds": _nonnegative_time(last),
        "visual_frames_changed": evidence.get("visualFramesChanged") is True
        if evidence.get("visualFramesChanged") is not None
        else None,
        "page_title": page_title,
        "title_matches_match": title_matches_match,
        "publisher": publisher,
        "publisher_verified": publisher_verified,
        "source_evidence_urls": source_urls,
        "source_evidence_verified": source_evidence_verified,
        "login_prompt_seen": evidence.get("loginPromptSeen") if isinstance(evidence.get("loginPromptSeen"), bool) else None,
        "region_prompt_seen": evidence.get("regionPromptSeen") if isinstance(evidence.get("regionPromptSeen"), bool) else None,
        "verification_prompt_seen": evidence.get("verificationPromptSeen") if isinstance(evidence.get("verificationPromptSeen"), bool) else None,
        "audio_status": audio_status,
        "audio_confirmation_observed": audio_claim if isinstance(audio_claim, bool) else None,
        "territory": _text(evidence.get("territory")),
        "evidence_ref": None,
        "validation_failures": failures,
        "notes": "" if not failures else "Claimed external playback did not satisfy every Web visual-evidence gate.",
    }


def _web_rights(record: dict[str, Any]) -> dict[str, Any]:
    explicit = {
        "metadata_listing": record.get("metadataListingPermission"),
        "thumbnail_display": record.get("thumbnailDisplayPermission"),
        "external_viewing": record.get("externalViewingPermission"),
        "embedding": record.get("embedAllowed"),
        "local_analysis": record.get("localAnalysisPermission"),
        "model_training": record.get("modelTrainingPermission"),
        "redistribution": record.get("redistributionPermission"),
        # A content/source URL proves provenance, not a permission grant.
        "basis_urls": record.get("rightsBasisUrls"),
        "reviewed_at": record.get("rightsReviewedAt"),
    }
    return _rights(explicit)


def _web_content_type(record: dict[str, Any]) -> str:
    explicit = _content_type(record.get("contentType"))
    if explicit != "UNKNOWN":
        return explicit
    # The current Chongqing source-only record explicitly labels itself a WTT
    # result article and points at WTT's article route. This classifies the
    # source format only; it does not create a video route or any rights.
    platform = (_text(record.get("platform")) or "").casefold()
    urls = _safe_urls(record.get("sourceEvidence"))
    article_evidence = any(
        _is_wtt_official_url(url)
        and urlparse(url).path.rstrip("/").casefold() == "/description"
        and any(
            re.fullmatch(r"\d{1,16}", article_id)
            for article_id in parse_qs(urlparse(url).query).get("artId", [])
        )
        for url in urls
    )
    if record.get("routeType") == "source-only" and "article" in platform and article_evidence:
        return "ARTICLE"
    return "UNKNOWN"


def _web_page_access(record: dict[str, Any], external: dict[str, Any]) -> dict[str, Any]:
    if external["status"] == "EXTERNAL_VIDEO_PAGE_VISUAL_PASS":
        page = _empty_page("OFFICIAL_PAGE_ACCESS_PASS")
        page["checked_at"] = external["checked_at"]
        page["final_url"] = external["final_url"]
        return page
    explicit = record.get("pageAccessStatus")
    if explicit == "OFFICIAL_PAGE_ACCESS_PASS":
        page = _empty_page("OFFICIAL_PAGE_ACCESS_PASS")
        page["checked_at"] = _date_or_datetime(record.get("pageAccessCheckedAt"))
        page["final_url"] = _https_url(record.get("pageAccessFinalUrl"))
        if not page["checked_at"] or not page["final_url"]:
            page["status"] = "REVIEW_REQUIRED"
        return page
    if explicit in {"FAIL", "RESTRICTED", "NOT_TESTED", "UNKNOWN", "BLOCKED", "REVIEW_REQUIRED"}:
        page = _empty_page(explicit)
        page["checked_at"] = _date_or_datetime(record.get("pageAccessCheckedAt"))
        return page
    return _empty_page()


def _web_resource_kind(route_type: Any) -> str:
    return {
        "event-page": "OFFICIAL_EVENT_PAGE",
        "video-page": "VIDEO_PAGE",
        "source-only": "UNKNOWN",
    }.get(route_type, "UNKNOWN")


def _web_canonical_url(record: dict[str, Any]) -> str:
    route = record.get("routeType")
    if route == "video-page":
        candidates = [record.get("videoOriginalUrl"), record.get("platformUrl")]
    elif route == "event-page":
        candidates = [record.get("platformUrl")]
    else:
        candidates = []
    source_evidence = record.get("sourceEvidence")
    if route not in {"video-page", "event-page"} and isinstance(source_evidence, list):
        candidates.extend(source_evidence)
    for candidate in candidates:
        url = _https_url(candidate)
        if url:
            return url
    raise ValueError("Web MatchRecord has no safe HTTPS source URL")


def adapt_web_match_record(record: dict[str, Any]) -> dict[str, Any]:
    """Map one Web MatchRecord to a Match and VideoSource without status uplift."""
    if not isinstance(record, dict):
        raise ValueError("Web MatchRecord must be an object")
    raw_id = _safe_id(record.get("id"))
    if not raw_id:
        raise ValueError("Web MatchRecord requires a safe stable id")

    canonical_url = _web_canonical_url(record)
    source_evidence = record.get("sourceEvidence")
    source_evidence = source_evidence if isinstance(source_evidence, list) else []
    source_urls = _safe_urls(
        [record.get("platformUrl"), record.get("videoOriginalUrl"), *source_evidence]
    )
    source_id = f"web-source:{raw_id}"
    match_id = f"web-match:{raw_id}"
    raw_names = record.get("players")
    names = (
        [name.strip() for name in raw_names if isinstance(name, str) and name.strip()]
        if isinstance(raw_names, list)
        else []
    )
    year = record.get("eventYear")
    if not isinstance(year, int) or isinstance(year, bool) or not 1900 <= year <= 2200:
        year = None
    result = _text(record.get("result"))
    external = _external_evidence_from_web(record, canonical_url)
    source_rights = _web_rights(record)
    thumbnail_candidate = _https_url(record.get("thumbnailUrl"))
    thumbnail_url = (
        thumbnail_candidate
        if source_rights["thumbnail_display"] == "ALLOWED"
        else None
    )

    match = {
        "match_id": match_id,
        "identity_status": _review_state(record.get("identityStatus")),
        "event": {
            "event_id": _event_id_from_record(record),
            "name": _text(record.get("event")),
            "year": year,
        },
        "match_date": _date_or_datetime(record.get("matchDate")),
        "discipline": _discipline(record.get("discipline")),
        "round": _text(record.get("round")),
        "participants": [],
        "participant_names_unassigned": names,
        "result": result,
        "provenance": _provenance(
            _adapter_method("web-match-record-adapter", record),
            source_urls,
            recorded_at=record.get("recordedAt"),
            review_status=record.get("identityStatus"),
        ),
    }
    page_access = _web_page_access(record, external)
    source = {
        "source_id": source_id,
        "match_id": match_id,
        "match_link_status": _review_state(record.get("matchLinkStatus")),
        "resource_kind": _web_resource_kind(record.get("routeType")),
        "platform": _text(record.get("platform")) or "UNKNOWN",
        "canonical_url": canonical_url,
        "publisher": _text(record.get("publisher")) or external.get("publisher"),
        "published_at": _date_or_datetime(record.get("publishedAt")),
        "verified_at": _date_or_datetime(record.get("lastVerifiedAt")),
        "discipline": _discipline(record.get("discipline")),
        "content_type": _web_content_type(record),
        "rights": source_rights,
        "thumbnail_url": thumbnail_url,
        "territory": {
            "status": "UNKNOWN",
            "territories": [],
            "notes": _text(record.get("regionRestriction")) or "",
        },
        "evidence": {
            "page_access": page_access,
            "external_video_page": external,
            # embedAllowed is permission only, never proof that an embed played.
            "embed_playback": _empty_embed(),
            # The Web MatchRecord has no Desktop-native playback evidence field.
            "desktop_native_playback": _empty_native(),
        },
        "provenance": _provenance(
            _adapter_method("web-match-record-adapter", record),
            source_urls,
            recorded_at=record.get("recordedAt"),
            review_status=record.get("matchLinkStatus"),
        ),
    }
    return {"match": match, "video_source": source}


def adapt_web_match_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(records, list):
        raise ValueError("Web fixture must be a list")
    matches: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    seen: set[str] = set()
    for record in records:
        adapted = adapt_web_match_record(record)
        if adapted["match"]["match_id"] in seen:
            raise ValueError("Duplicate Web MatchRecord id; refusing implicit merge")
        seen.add(adapted["match"]["match_id"])
        matches.append(adapted["match"])
        sources.append(adapted["video_source"])
    return {
        "contract_version": CONTRACT_VERSION,
        "matches": matches,
        "video_sources": sources,
        "local_video_assets": [],
        "timeline_mappings": [],
    }


def _desktop_permission(
    source: dict[str, Any], video_source: dict[str, Any], contract_key: str, raw_key: str
) -> str | None:
    """Resolve duplicate permission declarations without preferring a grant."""
    source_rights = source.get("rights") if isinstance(source.get("rights"), dict) else {}
    nested_rights = video_source.get("rights") if isinstance(video_source.get("rights"), dict) else {}
    candidates = [
        container[key]
        for container, key in (
            (source_rights, contract_key),
            (nested_rights, contract_key),
            (source, raw_key),
            (video_source, raw_key),
            (source.get("provenance") if isinstance(source.get("provenance"), dict) else {}, raw_key),
            (video_source.get("provenance") if isinstance(video_source.get("provenance"), dict) else {}, raw_key),
        )
        if key in container
    ]
    normalized = [_permission(value) for value in candidates]
    if not normalized:
        return None
    if "DENIED" in normalized:
        return "DENIED"
    distinct = set(normalized)
    if len(distinct) == 1:
        return normalized[0]
    if "PENDING_REVIEW" in distinct:
        return "PENDING_REVIEW"
    return "UNKNOWN"


def _desktop_source_rights(source: dict[str, Any], video_source: dict[str, Any], urls: list[str]) -> dict[str, Any]:
    nested_rights = video_source.get("rights") if isinstance(video_source.get("rights"), dict) else {}
    top_rights = source.get("rights") if isinstance(source.get("rights"), dict) else {}
    local_analysis = _desktop_permission(source, video_source, "local_analysis", "local_analysis_permission")
    rights_status = source.get("rights_status")
    if local_analysis is None and rights_status == "LICENSED_FOR_ANALYSIS":
        local_analysis = "ALLOWED"
    elif local_analysis is None and rights_status == "PERSONAL_VIEW_ONLY":
        local_analysis = "DENIED"

    basis_urls = nested_rights.get("basis_urls") or top_rights.get("basis_urls")
    reviewed_at = nested_rights.get("reviewed_at") or top_rights.get("reviewed_at")
    rights = _rights(
        {
            "metadata_listing": _desktop_permission(source, video_source, "metadata_listing", "metadata_listing_permission"),
            "thumbnail_display": _desktop_permission(source, video_source, "thumbnail_display", "thumbnail_display_permission"),
            "external_viewing": _desktop_permission(source, video_source, "external_viewing", "external_viewing_permission"),
            "embedding": _desktop_permission(source, video_source, "embedding", "embed_permission"),
            "local_analysis": local_analysis,
            "model_training": _desktop_permission(source, video_source, "model_training", "model_training_permission"),
            "redistribution": _desktop_permission(source, video_source, "redistribution", "redistribution_permission"),
            "basis_urls": basis_urls,
            "reviewed_at": reviewed_at,
        }
    )
    return rights


def _territory(source: dict[str, Any], video_source: dict[str, Any]) -> dict[str, Any]:
    raw = video_source.get("territory") if isinstance(video_source.get("territory"), dict) else {}
    status = raw.get("status")
    if status not in {"ALLOWED", "RESTRICTED", "UNKNOWN", "NOT_TESTED"}:
        status = source.get("territory_status")
    if status not in {"ALLOWED", "RESTRICTED", "UNKNOWN", "NOT_TESTED"}:
        status = "UNKNOWN"
    territories = raw.get("territories") if isinstance(raw.get("territories"), list) else []
    return {
        "status": status,
        "territories": [t.strip() for t in territories if isinstance(t, str) and t.strip()],
        "notes": _text(raw.get("notes") or source.get("region_restriction")) or "",
    }


def _page_evidence_from_desktop(video_source: dict[str, Any]) -> dict[str, Any]:
    raw = video_source.get("page_access")
    if not isinstance(raw, dict):
        return _empty_page()
    status = raw.get("status")
    if status not in {"OFFICIAL_PAGE_ACCESS_PASS", "FAIL", "RESTRICTED", "NOT_TESTED", "UNKNOWN", "BLOCKED", "REVIEW_REQUIRED"}:
        return _empty_page()
    result = _empty_page(status)
    result.update(
        {
            "checked_at": _date_or_datetime(raw.get("checked_at")),
            "final_url": _https_url(raw.get("final_url")),
            "http_status": raw.get("http_status") if isinstance(raw.get("http_status"), int) else None,
            "notes": _text(raw.get("notes")) or "",
        }
    )
    if status == "OFFICIAL_PAGE_ACCESS_PASS" and (not result["checked_at"] or not result["final_url"]):
        result["status"] = "REVIEW_REQUIRED"
    return result


def _external_evidence_from_desktop(video_source: dict[str, Any], target_url: str) -> dict[str, Any]:
    raw = video_source.get("external_video_page")
    if not isinstance(raw, dict):
        return _empty_external()
    status = raw.get("status")
    allowed = {
        "EXTERNAL_VIDEO_PAGE_VISUAL_PASS",
        "EXTERNAL_VIDEO_PAGE_VISUAL_FAIL",
        "RESTRICTED",
        "NOT_TESTED",
        "UNKNOWN",
        "BLOCKED",
        "REVIEW_REQUIRED",
    }
    if status not in allowed:
        return _empty_external()
    final_url = _https_url(raw.get("final_url"))
    first = raw.get("time_first_seconds")
    last = raw.get("time_last_seconds")
    checked_at = _date_or_datetime(raw.get("checked_at"))
    target = _https_url(target_url)
    exact_url_match = final_url == target if final_url and target else None
    page_title = _text(raw.get("page_title"))
    title_matches_match = raw.get("title_matches_match") if isinstance(raw.get("title_matches_match"), bool) else None
    publisher = _text(raw.get("publisher"))
    publisher_verified = raw.get("publisher_verified") if isinstance(raw.get("publisher_verified"), bool) else None
    source_urls = _safe_urls(raw.get("source_evidence_urls"))
    source_evidence_verified = raw.get("source_evidence_verified") if isinstance(raw.get("source_evidence_verified"), bool) else None
    audio_claim = raw.get("audible_output_confirmed")
    failures: list[str] = []
    if status == "EXTERNAL_VIDEO_PAGE_VISUAL_PASS":
        if not checked_at:
            failures.append("VERIFICATION_TIME_MISSING")
        if exact_url_match is not True:
            failures.append("FINAL_URL_MISMATCH")
        if not _finite_number(first) or not _finite_number(last) or first < 0 or last < first:
            failures.append("TIMELINE_OBSERVATION_INVALID")
        elif last - first < 5:
            failures.append("TIMELINE_ADVANCE_LT_5_SECONDS")
        if raw.get("visual_frames_changed") is not True:
            failures.append("VISUAL_FRAMES_UNCHANGED")
        if not page_title:
            failures.append("PAGE_TITLE_MISSING")
        if title_matches_match is not True:
            failures.append("PAGE_TITLE_MISMATCH")
        if not publisher:
            failures.append("PUBLISHER_MISSING")
        if publisher_verified is not True:
            failures.append("PUBLISHER_UNVERIFIED")
        if target and target not in source_urls:
            failures.append("SOURCE_EVIDENCE_MISSING_TARGET")
        if source_evidence_verified is not True:
            failures.append("OFFICIAL_MATCH_SOURCE_MISSING")
        for field, code in (("login_prompt_seen", "LOGIN_PROMPT"), ("region_prompt_seen", "REGION_PROMPT"), ("verification_prompt_seen", "VERIFICATION_PROMPT")):
            if raw.get(field) is not False:
                failures.append(f"{code}_NOT_EXPLICITLY_CLEAR")
        if not _safe_id(raw.get("evidence_ref")):
            failures.append("EVIDENCE_REFERENCE_MISSING")
        if failures:
            status = "REVIEW_REQUIRED"
    audio_status = "AUDIO_CONFIRMED" if audio_claim is True else "UNKNOWN"
    return {
        "status": status,
        "checked_at": checked_at,
        "requested_url": target,
        "final_url": final_url,
        "url_exact_match": exact_url_match,
        "time_first_seconds": _nonnegative_time(first),
        "time_last_seconds": _nonnegative_time(last),
        "visual_frames_changed": raw.get("visual_frames_changed")
        if isinstance(raw.get("visual_frames_changed"), bool)
        else None,
        "page_title": page_title,
        "title_matches_match": title_matches_match,
        "publisher": publisher,
        "publisher_verified": publisher_verified,
        "source_evidence_urls": source_urls,
        "source_evidence_verified": source_evidence_verified,
        "login_prompt_seen": raw.get("login_prompt_seen") if isinstance(raw.get("login_prompt_seen"), bool) else None,
        "region_prompt_seen": raw.get("region_prompt_seen") if isinstance(raw.get("region_prompt_seen"), bool) else None,
        "verification_prompt_seen": raw.get("verification_prompt_seen") if isinstance(raw.get("verification_prompt_seen"), bool) else None,
        "audio_status": audio_status,
        "audio_confirmation_observed": audio_claim if isinstance(audio_claim, bool) else None,
        "territory": _text(raw.get("territory")),
        "evidence_ref": _safe_id(raw.get("evidence_ref")),
        "validation_failures": failures,
        "notes": _text(raw.get("notes")) or "",
    }


def _embed_evidence_from_desktop(video_source: dict[str, Any], embedding_permission: str) -> dict[str, Any]:
    raw = video_source.get("embed_playback")
    if not isinstance(raw, dict):
        return _empty_embed()
    status = raw.get("status")
    allowed = {
        "EMBED_PLAYBACK_PASS",
        "EMBED_PLAYBACK_FAIL",
        "DENIED",
        "NOT_TESTED",
        "UNKNOWN",
        "BLOCKED",
        "REVIEW_REQUIRED",
    }
    if status not in allowed:
        return _empty_embed()
    evidence_complete = bool(_date_or_datetime(raw.get("checked_at")) and _safe_id(raw.get("evidence_ref")))
    if status == "EMBED_PLAYBACK_PASS" and (
        embedding_permission != "ALLOWED" or not evidence_complete
    ):
        status = "REVIEW_REQUIRED"
    return {
        "status": status,
        "checked_at": _date_or_datetime(raw.get("checked_at")),
        "error_code": _safe_id(raw.get("error_code")),
        "evidence_ref": _safe_id(raw.get("evidence_ref")),
        "notes": _text(raw.get("notes")) or "",
    }


def _native_evidence(raw: Any, source_sha256: str | None = None) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return _empty_native()
    status = raw.get("status")
    if status not in {
        "DESKTOP_NATIVE_PLAYBACK_PASS",
        "DESKTOP_NATIVE_PLAYBACK_FAIL",
        "NOT_TESTED",
        "UNKNOWN",
        "BLOCKED",
        "REVIEW_REQUIRED",
    }:
        return _empty_native()
    app_sha = raw.get("app_git_sha")
    package_sha = raw.get("package_sha256")
    evidence_ref = _safe_id(raw.get("evidence_ref"))
    checked_at = _date_or_datetime(raw.get("checked_at"))
    evidence_sha = raw.get("source_sha256")
    complete = bool(
        checked_at
        and evidence_ref
        and isinstance(app_sha, str)
        and re.fullmatch(r"[0-9a-fA-F]{40}", app_sha)
        and isinstance(package_sha, str)
        and re.fullmatch(r"[0-9a-fA-F]{64}", package_sha)
        and isinstance(evidence_sha, str)
        and re.fullmatch(r"[0-9a-fA-F]{64}", evidence_sha)
    )
    if status == "DESKTOP_NATIVE_PLAYBACK_PASS" and (
        not complete or (source_sha256 is not None and evidence_sha.lower() != source_sha256.lower())
    ):
        status = "REVIEW_REQUIRED"
    return {
        "status": status,
        "checked_at": checked_at,
        "app_git_sha": app_sha.lower() if complete else None,
        "package_sha256": package_sha.lower() if complete else None,
        "source_sha256": evidence_sha.lower()
        if complete and (source_sha256 is None or evidence_sha.lower() == source_sha256.lower())
        else source_sha256,
        "evidence_ref": evidence_ref,
        "notes": _text(raw.get("notes")) or "",
    }


def adapt_desktop_video_source(source: dict[str, Any]) -> dict[str, Any]:
    """Expose allow-listed official-source metadata; drop paths and unknown payloads."""
    if not isinstance(source, dict):
        raise ValueError("Desktop VideoSource must be an object")
    nested = source.get("video_source") if isinstance(source.get("video_source"), dict) else {}
    raw_id = _safe_id(source.get("source_key") or source.get("video_id") or nested.get("video_id"))
    if not raw_id:
        raise ValueError("Desktop VideoSource requires a safe source id")
    candidate_url = (
        source.get("canonical_url")
        or source.get("official_url")
        or source.get("url")
        or nested.get("canonical_url")
        or nested.get("official_url")
    )
    canonical_url = _https_url(candidate_url)
    if not canonical_url:
        raise ValueError("Desktop VideoSource requires an HTTPS canonical URL")
    urls = _safe_urls([canonical_url, source.get("source_urls") or []])
    rights = _desktop_source_rights(source, nested, urls)
    raw_thumb = _https_url(source.get("thumbnail_url") or nested.get("thumbnail_url"))
    thumb = raw_thumb if rights["thumbnail_display"] == "ALLOWED" else None

    external = _external_evidence_from_desktop(nested, canonical_url)
    embed = _embed_evidence_from_desktop(nested, rights["embedding"])
    publisher_provenance = nested.get("provenance") if isinstance(nested.get("provenance"), dict) else {}
    provenance_urls = _safe_urls(
        [urls, source.get("source_urls") or [], publisher_provenance.get("source_urls") or []]
    )
    relation_status = _review_state(source.get("match_link_status"))
    raw_match_id = source.get("match_id")
    match_id = _safe_id(raw_match_id)
    if raw_match_id is not None and match_id is None:
        raise ValueError("Desktop VideoSource match_id must be a safe stable id")
    source_sha = source.get("source_sha256")
    if not isinstance(source_sha, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", source_sha):
        source_sha = None
    native = _native_evidence(nested.get("desktop_native_playback"), source_sha256=source_sha)

    return {
        "source_id": f"desktop-source:{raw_id}",
        "match_id": match_id,
        "match_link_status": relation_status,
        "resource_kind": _resource_kind(source.get("resource_kind") or nested.get("resource_kind")),
        "platform": _text(source.get("provider") or source.get("platform")) or "UNKNOWN",
        "canonical_url": canonical_url,
        "publisher": _text(source.get("source_publisher") or nested.get("publisher")),
        "published_at": _date_or_datetime(source.get("published_at") or nested.get("published_at")),
        "verified_at": _date_or_datetime(source.get("source_verified_at") or source.get("verified_at")),
        "discipline": _discipline(source.get("discipline") or source.get("match_type")),
        "content_type": _content_type(source.get("content_type")),
        "rights": rights,
        "thumbnail_url": thumb,
        "territory": _territory(source, nested),
        "evidence": {
            "page_access": _page_evidence_from_desktop(nested),
            "external_video_page": external,
            "embed_playback": embed,
            "desktop_native_playback": native,
        },
        "provenance": _provenance(
            _adapter_method("desktop-official-source-adapter", source),
            provenance_urls,
            recorded_at=source.get("created_at"),
            review_status=source.get("match_link_status"),
            reviewer_ref=source.get("match_link_reviewer_ref"),
            evidence_refs=source.get("match_link_evidence_refs"),
        ),
    }


def _local_rights(source: dict[str, Any]) -> dict[str, Any]:
    permissions = source.get("permissions") if isinstance(source.get("permissions"), dict) else {}
    rights_status = source.get("rights_status")
    analysis = permissions.get("local_analysis", source.get("local_analysis_permission"))
    if analysis is None and rights_status == "LICENSED_FOR_ANALYSIS":
        analysis = "ALLOWED"
    elif analysis is None and rights_status == "PERSONAL_VIEW_ONLY":
        analysis = "DENIED"
    urls = _safe_urls(source.get("source_urls"))
    return _rights(
        {
            "metadata_listing": permissions.get("metadata_listing"),
            "thumbnail_display": permissions.get("thumbnail_display"),
            "external_viewing": permissions.get("external_viewing"),
            "embedding": permissions.get("embedding"),
            "local_analysis": analysis,
            "model_training": permissions.get("model_training"),
            "redistribution": permissions.get("redistribution"),
            "basis_urls": source.get("rights_basis_urls"),
            "reviewed_at": source.get("rights_reviewed_at"),
        }
    )


def adapt_local_video_asset(source: dict[str, Any]) -> dict[str, Any]:
    """Build a local-only asset record without serializing its filesystem path."""
    if not isinstance(source, dict):
        raise ValueError("LocalVideoAsset must be an object")
    digest = source.get("source_sha256")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", digest):
        raise ValueError("LocalVideoAsset requires a valid SHA-256 identity")
    if source.get("hash_status") not in (None, "VERIFIED"):
        raise ValueError("LocalVideoAsset source SHA-256 is not verified")
    digest = digest.lower()
    raw_id = _safe_id(source.get("local_asset_id") or source.get("video_id"))
    asset_id = raw_id or f"sha256:{digest[:24]}"
    raw_match_id = source.get("match_id")
    match_id = _safe_id(raw_match_id)
    if raw_match_id is not None and match_id is None:
        raise ValueError("LocalVideoAsset match_id must be a safe stable id")
    timeline = source.get("timeline") if isinstance(source.get("timeline"), dict) else {}
    timeline_id = _safe_id(timeline.get("timeline_id")) or f"local-timeline:{digest[:24]}"
    availability = source.get("availability") or source.get("availability_status")
    if availability not in {"AVAILABLE", "MISSING", "ACCESS_DENIED", "UNKNOWN"}:
        availability = "UNKNOWN"
    playback = _native_evidence(source.get("desktop_playback"), source_sha256=digest)
    result = source.get("vision_result") if isinstance(source.get("vision_result"), dict) else None
    if result is None:
        vision = {
            "status": "NO_VERIFIED_RESULT",
            "checked_at": None,
            "source_sha256": digest,
            "timeline_id": timeline_id,
            "result_ref": None,
            "notes": "No matched Vision result was supplied by the source record.",
        }
    else:
        claimed = result.get("status")
        matching = (
            isinstance(result.get("source_sha256"), str)
            and result["source_sha256"].lower() == digest
            and result.get("timeline_id") == timeline_id
            and bool(_safe_id(result.get("result_ref")))
        )
        if claimed == "VERIFIED_RESULT_AVAILABLE" and matching:
            vision_status = "VERIFIED_RESULT_AVAILABLE"
        elif claimed == "VERIFIED_RESULT_AVAILABLE":
            vision_status = "REVIEW_REQUIRED"
        elif claimed in {"NO_VERIFIED_RESULT", "NOT_TESTED", "UNKNOWN", "BLOCKED", "REVIEW_REQUIRED"}:
            vision_status = claimed
        else:
            vision_status = "UNKNOWN"
        vision = {
            "status": vision_status,
            "checked_at": _date_or_datetime(result.get("checked_at")),
            "source_sha256": digest,
            "timeline_id": timeline_id,
            "result_ref": _safe_id(result.get("result_ref")) if matching else None,
            "notes": "" if matching or vision_status != "REVIEW_REQUIRED" else "Rejected mismatched source or timeline binding.",
        }

    return {
        "local_asset_id": asset_id,
        "match_id": match_id,
        "source_sha256": digest,
        "availability": availability,
        "local_locator_ref": f"local-asset:{asset_id}",
        "timeline": {
            "timeline_id": timeline_id,
            "time_base": _rational(timeline.get("time_base")),
            "frame_rate": _rational(timeline.get("frame_rate")),
            "duration_ms": timeline.get("duration_ms")
            if isinstance(timeline.get("duration_ms"), int)
            and not isinstance(timeline.get("duration_ms"), bool)
            and timeline.get("duration_ms") >= 0
            else None,
        },
        "rights": _local_rights(source),
        "desktop_playback": playback,
        "vision_result": vision,
        "provenance": _provenance(
            _adapter_method("desktop-local-asset-adapter", source),
            source.get("source_urls"),
            recorded_at=source.get("created_at"),
            review_status=(
                source.get("match_link_review_status")
                if source.get("match_id") is not None
                else source.get("review_status")
            ),
            reviewer_ref=source.get("match_link_reviewer_ref"),
            evidence_refs=source.get("match_link_evidence_refs"),
        ),
    }


def adapt_timeline_mapping(source: dict[str, Any]) -> dict[str, Any]:
    """Never manufacture a verified mapping from an unreviewed offset."""
    if not isinstance(source, dict):
        raise ValueError("Timeline mapping must be an object")
    mapping_id = _safe_id(source.get("mapping_id"))
    from_id = _safe_id(source.get("from_source_id"))
    to_id = _safe_id(source.get("to_source_id"))
    if not mapping_id or not from_id or not to_id or from_id == to_id:
        raise ValueError("Timeline mapping requires distinct stable source ids")
    status = source.get("status")
    evidence = [item for item in source.get("evidence_refs", []) if _safe_id(item)]
    if status == "HUMAN_VERIFIED" and evidence:
        offset = source.get("offset_ms")
        scale = source.get("scale")
        verified_at = _date_or_datetime(source.get("verified_at"))
        if (
            _finite_number(offset)
            and _finite_number(scale)
            and scale > 0
            and verified_at
        ):
            mapped_status = "HUMAN_VERIFIED"
        else:
            mapped_status = "REVIEW_REQUIRED"
            offset = scale = None
    elif status == "HUMAN_VERIFIED":
        mapped_status = "REVIEW_REQUIRED"
        offset = scale = None
    else:
        mapped_status = _review_state(status)
        if mapped_status == "VERIFIED":
            mapped_status = "REVIEW_REQUIRED"
        offset = scale = None
    return {
        "mapping_id": mapping_id,
        "from_source_id": from_id,
        "to_source_id": to_id,
        "status": mapped_status,
        "verified_at": verified_at if mapped_status == "HUMAN_VERIFIED" else None,
        "offset_ms": offset,
        "scale": scale,
        "evidence_refs": evidence if mapped_status == "HUMAN_VERIFIED" else [],
    }


def build_contract(
    *,
    web_records: list[dict[str, Any]] | None = None,
    desktop_sources: list[dict[str, Any]] | None = None,
    local_assets: list[dict[str, Any]] | None = None,
    timeline_mappings: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    web = adapt_web_match_records(web_records or [])
    video_sources = list(web["video_sources"])
    for row in desktop_sources or []:
        video_sources.append(adapt_desktop_video_source(row))
    return {
        "contract_version": CONTRACT_VERSION,
        "matches": web["matches"],
        "video_sources": video_sources,
        "local_video_assets": [adapt_local_video_asset(row) for row in (local_assets or [])],
        "timeline_mappings": [adapt_timeline_mapping(row) for row in (timeline_mappings or [])],
    }


def to_web_safe_payload(contract: dict[str, Any]) -> dict[str, Any]:
    """Project explicitly listable, externally viewable sources; omit all local assets."""
    real_match_ids = {
        match.get("match_id")
        for match in contract.get("matches", [])
        if isinstance(match, dict) and not _is_synthetic(match)
    }

    def public_source(source: Any) -> bool:
        if not isinstance(source, dict) or _is_synthetic(source):
            return False
        match_id = source.get("match_id")
        if match_id is not None and match_id not in real_match_ids:
            return False
        rights = source.get("rights")
        if not isinstance(rights, dict):
            return False
        return (
            rights.get("metadata_listing") == "ALLOWED"
            and rights.get("external_viewing") == "ALLOWED"
        )

    allowed_sources = [
        source
        for source in contract.get("video_sources", [])
        if public_source(source)
    ]
    public_source_ids = {source["source_id"] for source in allowed_sources}
    public_match_ids = {source.get("match_id") for source in allowed_sources if source.get("match_id")}
    public_matches = [
        match
        for match in contract.get("matches", [])
        if match.get("match_id") in public_match_ids
        and match.get("provenance", {}).get("method") == "web-match-record-adapter"
    ]
    public_mappings = [
        mapping
        for mapping in contract.get("timeline_mappings", [])
        if mapping.get("from_source_id") in public_source_ids
        and mapping.get("to_source_id") in public_source_ids
        and mapping.get("status") == "HUMAN_VERIFIED"
        and mapping.get("evidence_refs")
    ]
    return {
        "contract_version": CONTRACT_VERSION,
        "matches": public_matches,
        "video_sources": allowed_sources,
        "local_video_assets": [],
        "timeline_mappings": public_mappings,
    }
