"""Resolve temporary storage consistently for local runs and GitHub Actions."""

import os
import tempfile
from pathlib import Path


def resolve_temp_root(environ=None) -> Path:
    env = os.environ if environ is None else environ
    runner_temp = env.get("RUNNER_TEMP") if env.get("GITHUB_ACTIONS") == "true" else None
    return Path(runner_temp or tempfile.gettempdir()).expanduser().resolve(strict=False)


def is_within_test_temp(path, environ=None) -> bool:
    """Return whether a test DB is in OS temp or this Actions runner's temp."""
    env = os.environ if environ is None else environ
    candidate = Path(path).expanduser().resolve(strict=False)
    roots = [Path(tempfile.gettempdir()).expanduser().resolve(strict=False)]
    runner_temp = env.get("RUNNER_TEMP") if env.get("GITHUB_ACTIONS") == "true" else None
    if runner_temp:
        roots.append(Path(runner_temp).expanduser().resolve(strict=False))
    for root in roots:
        try:
            candidate.relative_to(root)
            return True
        except ValueError:
            continue
    return False
