"""Metadata discovery freshness; never grants media or playback permission."""
from datetime import datetime, timezone

METADATA_MAX_AGE_SECONDS = 30 * 86400


def metadata_status(value, now):
    if value is None or value == "":
        return "MISSING_TIMESTAMP"
    if not isinstance(value, str):
        return "INVALID_TIMESTAMP"
    try:
        checked = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if checked.tzinfo is None or checked.utcoffset() is None:
            return "INVALID_TIMESTAMP"
        age = (now - checked.astimezone(timezone.utc)).total_seconds()
    except (TypeError, ValueError, OverflowError):
        return "INVALID_TIMESTAMP"
    if age < 0:
        return "FUTURE_TIMESTAMP"
    return "CURRENT" if age <= METADATA_MAX_AGE_SECONDS else "EXPIRED"


def partition_official_metadata(rows, now):
    visible, withheld = [], {key: 0 for key in ("EXPIRED", "FUTURE_TIMESTAMP", "INVALID_TIMESTAMP", "MISSING_TIMESTAMP")}
    for row in rows:
        state = metadata_status(row.get("metadata_verified_at"), now)
        if state == "CURRENT":
            visible.append(row)
        else:
            withheld[state] += 1
    return visible, {"policy_days": 30, "withheld_counts": withheld}
