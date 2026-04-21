"""Context object: target repo state + resolved config + tool availability."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class RepoInfo:
    current_branch: str = ""
    head_sha: str = ""
    visibility: str = "unknown"  # private | public | unknown
    remote_url: str = ""
    commit_count: int = 0
    contributor_email_count: int = 0
    has_remote: bool = False


@dataclass
class Context:
    target: Path
    iw_dir: Path
    config: dict[str, Any]
    tools: dict[str, str | None]  # tool_name -> version string (None = missing)
    repo: RepoInfo
    ecosystems: set[str] = field(default_factory=set)
    mode: str = "scan"

    # Cached derived data
    _tracked_files_cache: list[str] | None = None

    def has_tool(self, name: str) -> bool:
        return self.tools.get(name) is not None

    def tracked_files(self) -> list[str]:
        """Return `git ls-files` output, cached."""
        if self._tracked_files_cache is None:
            try:
                result = subprocess.run(
                    ["git", "ls-files"],
                    cwd=self.target,
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=30,
                )
                self._tracked_files_cache = result.stdout.strip().splitlines()
            except (subprocess.SubprocessError, FileNotFoundError):
                self._tracked_files_cache = []
        return self._tracked_files_cache

    def path(self, relative: str) -> Path:
        """Resolve a path relative to the target repo."""
        return self.target / relative

    def read_text(self, relative: str, limit: int = 1_000_000) -> str | None:
        """Read a file relative to target; return None if missing."""
        p = self.path(relative)
        if not p.exists() or not p.is_file():
            return None
        try:
            return p.read_text(encoding="utf-8", errors="replace")[:limit]
        except OSError:
            return None

    def exists(self, *candidates: str) -> str | None:
        """Return the first existing path from candidates, or None."""
        for c in candidates:
            if self.path(c).exists():
                return c
        return None


def detect_repo_info(target: Path) -> RepoInfo:
    """Probe git + gh to populate RepoInfo."""
    info = RepoInfo()

    def _git(*args: str) -> str:
        try:
            r = subprocess.run(
                ["git", *args],
                cwd=target,
                capture_output=True,
                text=True,
                check=False,
                timeout=15,
            )
            return r.stdout.strip()
        except (subprocess.SubprocessError, FileNotFoundError):
            return ""

    info.current_branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    info.head_sha = _git("rev-parse", "HEAD")
    info.remote_url = _git("config", "--get", "remote.origin.url")
    info.has_remote = bool(info.remote_url)

    count_str = _git("rev-list", "--count", "HEAD")
    if count_str.isdigit():
        info.commit_count = int(count_str)

    emails = _git("log", "--all", "--format=%ae")
    if emails:
        info.contributor_email_count = len({e for e in emails.splitlines() if e})

    # Visibility via gh (best-effort)
    try:
        r = subprocess.run(
            ["gh", "repo", "view", "--json", "isPrivate,visibility"],
            cwd=target,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        if r.returncode == 0 and r.stdout:
            import json

            data = json.loads(r.stdout)
            is_private = data.get("isPrivate")
            if is_private is True:
                info.visibility = "private"
            elif is_private is False:
                info.visibility = "public"
    except (subprocess.SubprocessError, FileNotFoundError, ValueError):
        pass

    return info


def detect_ecosystems(target: Path) -> set[str]:
    """Detect programming-language ecosystems present in the target."""
    eco: set[str] = set()
    if (
        (target / "pyproject.toml").exists()
        or (target / "setup.py").exists()
        or (target / "requirements.txt").exists()
    ):
        eco.add("python")
    if (target / "package.json").exists():
        eco.add("node")
    if (target / "go.mod").exists():
        eco.add("go")
    if (target / "Cargo.toml").exists():
        eco.add("rust")
    if (
        (target / "pom.xml").exists()
        or (target / "build.gradle").exists()
        or (target / "build.gradle.kts").exists()
    ):
        eco.add("java")
    if (target / "Dockerfile").exists() or any(target.glob("Dockerfile*")):
        eco.add("docker")
    return eco
