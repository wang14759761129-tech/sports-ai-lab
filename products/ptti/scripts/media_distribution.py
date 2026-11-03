"""Distribution checks only. No application/backend imports or database access."""
import shutil
import subprocess
from pathlib import Path

ACTIVE_MANIFEST = "public-match-cover-manifest.v0.2.json"


def verify_media_distribution(root: Path, artifact: Path, *, package: bool = False) -> None:
    node = shutil.which("node")
    if not node:
        raise RuntimeError("Media distribution verification requires Node; refusing packaging")
    command = [node, str(root / "frontend/scripts/check-media-distribution.mjs"), str(artifact), "--windows"]
    if package:
        command.append("--package")
    subprocess.run(command, cwd=root / "frontend", check=True)


def stage_professional_catalog(root: Path, target: Path) -> Path:
    """Preserve all source evidence; exclude historical/internal cover reviews from delivery."""
    destination = target / "distribution-data" / "professional"
    shutil.copytree(root / "data/professional", destination, ignore=shutil.ignore_patterns("cover_review"))
    current = destination / "cover_review"
    current.mkdir()
    shutil.copy2(root / "data/professional/cover_review" / ACTIVE_MANIFEST, current / ACTIVE_MANIFEST)
    return destination
