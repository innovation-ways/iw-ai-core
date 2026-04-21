"""Tool availability detection."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable

# Map of tool_name -> (binary_name, version_command) pairs.
# version_command is a callable that, given the binary path, returns a version string or None.


def _simple_version(cmd: list[str]) -> str | None:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=5, check=False)
        output = (r.stdout or r.stderr or "").strip()
        return output.splitlines()[0] if output else None
    except (subprocess.SubprocessError, FileNotFoundError):
        return None


TIER1 = [
    "gitleaks",
    "git-filter-repo",
    "ripgrep",  # binary: rg
    "syft",
    "grant",
    "grype",
    "osv-scanner",
    "pinact",
    "gh",
    "pre-commit",
]

TIER2 = [
    "trufflehog",
    "semgrep",
    "licensee",
    "pip-licenses",
    "license-checker",
    "go-licenses",
    "cosign",
    "git-sizer",
    "reuse",
    "detect-secrets",
    "pip-audit",
    "cargo-audit",
    "govulncheck",
]

# Binary names that differ from the logical tool name
BINARY_ALIAS = {
    "ripgrep": "rg",
    "cargo-audit": "cargo",  # invoked as `cargo audit`
}

VERSION_CMDS: dict[str, Callable[[str], str | None]] = {
    "gitleaks": lambda b: _simple_version([b, "version"]),
    "git-filter-repo": lambda b: _simple_version([b, "--version"]),
    "ripgrep": lambda _b: _simple_version(["rg", "--version"]),
    "syft": lambda b: _simple_version([b, "version"]),
    "grant": lambda b: _simple_version([b, "--version"]),
    "grype": lambda b: _simple_version([b, "version"]),
    "osv-scanner": lambda b: _simple_version([b, "--version"]),
    "pinact": lambda b: _simple_version([b, "--version"]),
    "gh": lambda b: _simple_version([b, "--version"]),
    "pre-commit": lambda b: _simple_version([b, "--version"]),
    "trufflehog": lambda b: _simple_version([b, "--version"]),
    "semgrep": lambda b: _simple_version([b, "--version"]),
    "licensee": lambda b: _simple_version([b, "version"]),
    "pip-licenses": lambda b: _simple_version([b, "--version"]),
    "license-checker": lambda b: _simple_version([b, "--version"]),
    "go-licenses": lambda b: _simple_version([b, "--help"]),
    "cosign": lambda b: _simple_version([b, "version"]),
    "git-sizer": lambda b: _simple_version([b, "--version"]),
    "reuse": lambda b: _simple_version([b, "--version"]),
    "detect-secrets": lambda b: _simple_version([b, "--version"]),
    "pip-audit": lambda b: _simple_version([b, "--version"]),
    "cargo-audit": lambda _b: _simple_version(["cargo", "audit", "--version"]),
    "govulncheck": lambda b: _simple_version([b, "-version"]),
}


def detect_tools(overrides: dict[str, str] | None = None) -> dict[str, str | None]:
    """Detect which tools are installed; return name -> version (None if missing)."""
    overrides = overrides or {}
    found: dict[str, str | None] = {}
    for tool in TIER1 + TIER2:
        if tool in overrides:
            binary = overrides[tool]
        else:
            binary = shutil.which(BINARY_ALIAS.get(tool, tool))
        if not binary:
            found[tool] = None
            continue
        version = VERSION_CMDS.get(tool, lambda _b: "installed")(binary)
        found[tool] = version or "installed"
    return found


def missing_tier1(tools: dict[str, str | None]) -> list[str]:
    return [t for t in TIER1 if not tools.get(t)]
