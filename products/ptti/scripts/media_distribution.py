"""Distribution checks only. No application/backend imports or database access."""
import shutil
import subprocess
from pathlib import Path

ACTIVE_MANIFEST = "public-match-cover-manifest.v0.2.json"


def verify_media_distribution(root: Path, artifact: Path, *, package: bool = False) -> None:
    node = shutil.which("node")
    if not node:
        raise RuntimeError("Media distribution verification requires Node; refusing packaging")
    artifact_path = Path(artifact).expanduser().resolve(strict=False)
    if not artifact_path.is_dir():
        raise RuntimeError(f"Media distribution artifact path is not a directory: {artifact_path}")
    checker = (root / "frontend/scripts/check-media-distribution.mjs").resolve(strict=True)
    command = [node, str(checker), str(artifact_path), "--windows"]
    if package:
        command.append("--package")
    subprocess.run(command, cwd=root / "frontend", check=True)


def stage_professional_catalog(root: Path, target: Path) -> Path:
    """Preserve source evidence; stage only the active manifest at a flat package path."""
    destination = target / "distribution-data" / "professional"
    shutil.copytree(root / "data/professional", destination, ignore=shutil.ignore_patterns("cover_review"))
    shutil.copy2(root / "data/professional/cover_review" / ACTIVE_MANIFEST, destination / ACTIVE_MANIFEST)
    return destination
