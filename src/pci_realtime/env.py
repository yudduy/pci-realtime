from __future__ import annotations

import os
from pathlib import Path


def load_local_env(path: Path | None = None, *, override: bool = False) -> None:
    """Load simple KEY=VALUE pairs from .env for local CLI/MCP commands."""
    env_path = path or Path.cwd() / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        clean_key = key.strip()
        clean_value = value.strip().strip('"').strip("'")
        if not clean_key:
            continue
        if override or clean_key not in os.environ:
            os.environ[clean_key] = clean_value
