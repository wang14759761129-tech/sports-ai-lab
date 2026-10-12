"""Resolve temporary storage consistently for local runs and GitHub Actions."""

import os
import tempfile
from pathlib import Path


def resolve_temp_root(environ=None) -> Path:
    env = os.environ if environ is None else environ
    runner_temp = env.get("RUNNER_TEMP") if env.get("GITHUB_ACTIONS") == "true" else None
    return Path(runner_temp or tempfile.gettempdir()).expanduser().resolve(strict=False)
