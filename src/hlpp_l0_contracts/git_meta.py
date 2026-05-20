"""Git metadata helpers — auto-inject `builder_version` / `analysis_version`.

Per spec §7.1, §8 — builder_version and analysis_version MUST be auto-injected
from git commit hash of producing repo. Manual semver bumps for 1-person solo
dev get forgotten (Gemini critic feedback).
"""
from __future__ import annotations

import subprocess
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=32)
def git_commit_hash(cwd: str | Path | None = None, short: bool = True) -> str:
    """Return current HEAD commit hash for the repo containing cwd.

    Args:
        cwd: working directory (must be inside a git repo). If None, uses current.
        short: True returns 7-char hash; False returns full 40-char.

    Returns:
        Commit hash string. Returns 'unknown' if not in a git repo or git fails.
    """
    args = ["git", "rev-parse"]
    if short:
        args.append("--short")
    args.append("HEAD")
    try:
        result = subprocess.run(
            args,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return "unknown"


def git_dirty(cwd: str | Path | None = None) -> bool:
    """Return True if working tree has uncommitted changes.

    Use to gate production builds — builders should refuse to write
    if cwd is dirty (would produce non-reproducible builder_version).
    """
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=2,
        )
        return bool(result.stdout.strip())
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


__all__ = ["git_commit_hash", "git_dirty"]
