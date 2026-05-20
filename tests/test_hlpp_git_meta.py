"""Tests for hlpp_l0_contracts.git_meta — auto-inject builder_version/analysis_version."""
from __future__ import annotations

import subprocess
from pathlib import Path

from hlpp_l0_contracts import git_meta


def test_git_commit_hash_short_default():
    git_meta.git_commit_hash.cache_clear()
    sha = git_meta.git_commit_hash()
    assert isinstance(sha, str)
    # Either a real 7-char hash, or 'unknown' if not in a git repo
    assert len(sha) == 7 or sha == "unknown"
    if sha != "unknown":
        assert all(c in "0123456789abcdef" for c in sha)


def test_git_commit_hash_full_form():
    git_meta.git_commit_hash.cache_clear()
    sha = git_meta.git_commit_hash(short=False)
    assert isinstance(sha, str)
    assert len(sha) in (40, 7) or sha == "unknown"


def test_git_commit_hash_outside_repo_returns_unknown(tmp_path: Path):
    git_meta.git_commit_hash.cache_clear()
    sha = git_meta.git_commit_hash(cwd=tmp_path)
    assert sha == "unknown"


def test_git_dirty_returns_bool():
    result = git_meta.git_dirty()
    assert isinstance(result, bool)


def test_git_dirty_clean_worktree(tmp_path: Path):
    # Initialize empty repo with one commit so working tree is clean
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    (tmp_path / "README.md").write_text("hello\n")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "init"],
        cwd=tmp_path,
        check=True,
    )
    assert git_meta.git_dirty(cwd=tmp_path) is False

    # Add untracked file → dirty
    (tmp_path / "untracked.txt").write_text("x\n")
    assert git_meta.git_dirty(cwd=tmp_path) is True
