"""Stage only the pinned Extended OpenTTGames TRAIN videos under PTTI-Dev.

This downloader is deliberately allowlisted, resumable, and refuses to replace
an existing complete source. It never requests the official TEST split.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DATASET_REVISION = "36471a76b969a0340df59258a813bf8214e68e7c"
LICENSE = "CC BY-NC-SA 4.0"
URL_ROOT = "https://lab.osai.ai/datasets/openttgames/data"
EXPECTED_BYTES = {
    "game_1": 5_572_649_632,
    "game_2": 10_833_064_677,
    "game_3": 4_637_044_123,
    "game_4": 3_947_371_986,
    "game_5": 4_493_632_417,
}
CHUNK_BYTES = 1024 * 1024
DOWNLOAD_RANGE_BYTES = 16 * 1024 * 1024


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(CHUNK_BYTES), b""):
            digest.update(block)
    return digest.hexdigest()


def _stream_train_video(game: str, destination: Path, *, timeout_seconds: int = 60,
                        retries: int = 4) -> dict:
    if game not in EXPECTED_BYTES:
        raise ValueError("ONLY_ALLOWLISTED_TRAIN_GAMES_CAN_BE_STAGED")
    expected = EXPECTED_BYTES[game]
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".partial")
    if destination.exists():
        if destination.stat().st_size != expected:
            raise FileExistsError("EXISTING_TRAIN_VIDEO_SIZE_MISMATCH_REFUSING_OVERWRITE")
        return {"game": game, "path": str(destination), "size_bytes": expected,
                "sha256": _sha256(destination), "status": "ALREADY_STAGED"}
    if partial.exists() and partial.stat().st_size == expected:
        digest = _sha256(partial)
        partial.replace(destination)
        return {"game": game, "path": str(destination), "size_bytes": expected,
                "sha256": digest, "status": "RESUMED_COMPLETE_PARTIAL", "source": f"{URL_ROOT}/{game}.mp4"}
    if partial.exists() and partial.stat().st_size > expected:
        raise ValueError("PARTIAL_TRAIN_VIDEO_EXCEEDS_PINNED_SIZE")

    url = f"{URL_ROOT}/{game}.mp4"
    offset = partial.stat().st_size if partial.exists() else 0
    if offset > expected:
        raise ValueError("PARTIAL_TRAIN_VIDEO_EXCEEDS_PINNED_SIZE")
    completed_ranges = 0
    while offset < expected:
        end = min(expected - 1, offset + DOWNLOAD_RANGE_BYTES - 1)
        expected_range_bytes = end - offset + 1
        range_error = None
        for attempt in range(1, retries + 1):
            headers = {"User-Agent": "PTTI-research-evaluator/0.2",
                       "Range": f"bytes={offset}-{end}"}
            request = Request(url, headers=headers)
            try:
                with urlopen(request, timeout=timeout_seconds) as response:
                    content_range = response.headers.get("Content-Range", "")
                    match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", content_range)
                    if (getattr(response, "status", None) != 206 or not match or
                            (int(match.group(1)), int(match.group(2)), int(match.group(3))) !=
                            (offset, end, expected)):
                        raise ValueError("TRAIN_VIDEO_RANGE_RESPONSE_VALIDATION_FAILED")
                    body = bytearray()
                    while len(body) < expected_range_bytes:
                        block = response.read(min(CHUNK_BYTES, expected_range_bytes - len(body)))
                        if not block:
                            break
                        body.extend(block)
                    if len(body) != expected_range_bytes:
                        raise IOError(f"TRAIN_VIDEO_RANGE_INCOMPLETE:{len(body)}/{expected_range_bytes}")
                with partial.open("ab" if offset else "wb") as stream:
                    stream.write(body)
                    stream.flush()
                offset = end + 1
                completed_ranges += 1
                range_error = None
                if completed_ranges % 16 == 0 or offset == expected:
                    print(f"PROGRESS {game} {offset}/{expected} bytes", flush=True)
                break
            except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
                range_error = exc
                if attempt < retries:
                    time.sleep(min(2 ** (attempt - 1), 8))
        if range_error is not None:
            raise RuntimeError(f"TRAIN_VIDEO_DOWNLOAD_FAILED:{game}:{range_error}") from range_error
        if partial.stat().st_size != offset:
            raise RuntimeError("TRAIN_VIDEO_PARTIAL_SIZE_DID_NOT_ADVANCE")
    if partial.stat().st_size != expected:
        raise IOError(f"TRAIN_VIDEO_INCOMPLETE:{partial.stat().st_size}/{expected}")
    digest = _sha256(partial)
    partial.replace(destination)
    return {"game": game, "path": str(destination), "size_bytes": expected,
            "sha256": digest, "status": "STAGED", "source": url}


def stage(games: list[str], root: Path | None = None) -> list[dict]:
    root = root or (Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) /
                    "PTTI-Dev" / "research-datasets" / "ExtendedOpenTTGames" / "videos" / "train")
    root = root.resolve()
    allowed_root = (Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) /
                    "PTTI-Dev" / "research-datasets" / "ExtendedOpenTTGames" / "videos" / "train").resolve()
    if root != allowed_root:
        raise ValueError("TRAIN_VIDEO_STAGING_PATH_MUST_BE_PTTI_DEV_DATASET_ROOT")
    results = []
    for game in games:
        if game not in EXPECTED_BYTES:
            raise ValueError("ONLY_ALLOWLISTED_TRAIN_GAMES_CAN_BE_STAGED")
        result = _stream_train_video(game, root / f"{game}.mp4")
        results.append(result)
        print(json.dumps({"game": game, "status": result["status"],
                          "size_bytes": result["size_bytes"], "sha256": result["sha256"]},
                         ensure_ascii=False), flush=True)
    manifest_path = root.parent / "PTTI_TRAIN_STAGING_MANIFEST.json"
    existing = {}
    if manifest_path.exists():
        existing = {row["game"]: row for row in json.loads(manifest_path.read_text(encoding="utf-8")).get("videos", [])}
    for result in results:
        existing[result["game"]] = {**result, "dataset_revision": DATASET_REVISION,
                                     "license": LICENSE, "commercial_use": False,
                                     "staged_at_utc": datetime.now(timezone.utc).isoformat()}
    manifest = {"dataset": "Extended OpenTTGames", "dataset_revision": DATASET_REVISION,
                "license": LICENSE, "commercial_use": False,
                "official_test_split": "NOT_ACCESSED",
                "source_root": URL_ROOT,
                "videos": [existing[key] for key in sorted(existing)]}
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage allowlisted TRAIN videos outside the repository")
    parser.add_argument("--games", default="1,2,3,5", help="comma-separated TRAIN game numbers 1-5")
    args = parser.parse_args()
    games = [f"game_{int(value)}" for value in args.games.split(",") if value.strip()]
    stage(games)


if __name__ == "__main__":
    main()
