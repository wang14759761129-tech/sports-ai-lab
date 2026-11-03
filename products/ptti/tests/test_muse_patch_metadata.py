import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backend.source_metadata import metadata_status, partition_official_metadata

NOW = datetime(2026, 10, 26, tzinfo=timezone.utc)


@pytest.mark.parametrize("timestamp,expected", [
    (NOW.isoformat(), "CURRENT"),
    ((NOW - timedelta(days=30)).isoformat(), "CURRENT"),
    ((NOW - timedelta(days=30, microseconds=1)).isoformat(), "EXPIRED"),
    ((NOW + timedelta(microseconds=1)).isoformat(), "FUTURE_TIMESTAMP"),
    ("2026-10-26T08:00:00+08:00", "CURRENT"),
    ("2026-10-26T00:00:00Z", "CURRENT"),
    ("2026-10-26T00:00:00", "INVALID_TIMESTAMP"),
    ("bad date", "INVALID_TIMESTAMP"),
    (42, "INVALID_TIMESTAMP"),
    (None, "MISSING_TIMESTAMP"), ("", "MISSING_TIMESTAMP"),
])
def test_metadata_freshness_boundaries(timestamp, expected):
    assert metadata_status(timestamp, NOW) == expected


def test_metadata_partition_exposes_counts_only():
    rows = [{"video_id": "private-diagnostic", "metadata_verified_at": None}]
    visible, review = partition_official_metadata(rows, NOW)
    assert visible == []
    assert review["withheld_counts"]["MISSING_TIMESTAMP"] == 1
    assert "private-diagnostic" not in json.dumps(review)
