"""Tool availability probe for Tier-1 OSS compliance tools."""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
from dataclasses import dataclass

from orch.config import CORE_ROOT

TIER1_INSTALL_COMMANDS: dict[str, str] = {
    "gitleaks": (
        "curl -sSfL https://github.com/gitleaks/gitleaks/releases/latest/download/"
        "gitleaks_linux_x64.tar.gz | tar -xz -C ~/.local/bin"
    ),
    "git-filter-repo": "uv tool install git-filter-repo",
    "ripgrep": "sudo apt install ripgrep",
    "syft": (
        "curl -sSfL https://raw.githubusercontent.com/anchore/syft/main/install.sh"
        " | sh -s -- -b ~/.local/bin"
    ),
    "grant": (
        "curl -sSfL https://raw.githubusercontent.com/anchore/grant/main/install.sh"
        " | sh -s -- -b ~/.local/bin"
    ),
    "grype": (
        "curl -sSfL https://raw.githubusercontent.com/anchore/grype/main/install.sh"
        " | sh -s -- -b ~/.local/bin"
    ),
    "osv-scanner": "go install github.com/google/osv-scanner/cmd/osv-scanner@latest",
    "pinact": "go install github.com/suzuki-shunsuke/pinact/cmd/pinact@latest",
    "gh": "sudo apt install gh",
    "pre-commit": "uv tool install pre-commit",
}

BINARY_ALIAS = {
    "ripgrep": "rg",
}


def _simple_version(cmd: list[str]) -> str | None:
    """Run a version command and return its first output line.

    Combines stdout and stderr so callers need not know which stream a tool
    uses. Returns None on subprocess errors, timeouts, or empty output.

    Args:
        cmd: Command and arguments to execute (e.g. ``["gitleaks", "version"]``).

    Returns:
        First non-empty output line, or None if the command fails or produces
        no output.
    """
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=5, check=False)  # noqa: S603
        output = (r.stdout or r.stderr or "").strip()
        return output.splitlines()[0] if output else None
    except (subprocess.SubprocessError, FileNotFoundError):
        return None


def _get_tier1_tools() -> list[str]:
    """Load the authoritative TIER1 tool list from the iw-oss-publish skill.

    Attempts to import ``tools.TIER1`` from the skill's scripts/lib/tools.py.
    Falls back to the keys of TIER1_INSTALL_COMMANDS when the skill file is
    absent, unloadable, or does not expose a ``TIER1`` attribute.

    Returns:
        List of canonical tool names that must be probed.
    """
    skill_tools_path = (
        CORE_ROOT / ".claude" / "skills" / "iw-oss-publish" / "scripts" / "lib" / "tools.py"
    )
    if not skill_tools_path.exists():
        return list(TIER1_INSTALL_COMMANDS.keys())
    spec = importlib.util.spec_from_file_location("tools", skill_tools_path)
    if spec is None or spec.loader is None:
        return list(TIER1_INSTALL_COMMANDS.keys())
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, "TIER1", list(TIER1_INSTALL_COMMANDS.keys()))


@dataclass(frozen=True)
class ToolStatus:
    """Installation status and version information for a single Tier-1 tool.

    Attributes:
        installed: True when the tool binary was found on PATH.
        version: First line of the tool's version output, or None when the
            tool is absent or the version command fails.
        install_cmd: Recommended shell command to install this tool.
    """

    installed: bool
    version: str | None
    install_cmd: str


def probe_tier1() -> dict[str, ToolStatus]:
    """Probe PATH for each Tier-1 OSS compliance tool and return their status.

    For each tool in the authoritative TIER1 list, checks whether its binary
    is present on PATH (respecting BINARY_ALIAS remappings), runs the
    appropriate version command, and looks up the install hint.

    Returns:
        Dict mapping each tool name to its ToolStatus (installed flag, version
        string, and install command).
    """
    tier1_tools = _get_tier1_tools()
    result: dict[str, ToolStatus] = {}

    for tool in tier1_tools:
        binary_name = BINARY_ALIAS.get(tool, tool)
        binary_path = shutil.which(binary_name)

        if binary_path is not None:
            version_cmd_map = {
                "gitleaks": [binary_path, "version"],
                "git-filter-repo": [binary_path, "--version"],
                "ripgrep": ["rg", "--version"],
                "syft": [binary_path, "version"],
                "grant": [binary_path, "--version"],
                "grype": [binary_path, "version"],
                "osv-scanner": [binary_path, "--version"],
                "pinact": [binary_path, "--version"],
                "gh": [binary_path, "--version"],
                "pre-commit": [binary_path, "--version"],
            }
            version_cmd = version_cmd_map.get(tool, [binary_path, "--version"])
            version = _simple_version(version_cmd)
        else:
            version = None

        install_cmd = TIER1_INSTALL_COMMANDS.get(tool, "")

        result[tool] = ToolStatus(
            installed=binary_path is not None,
            version=version,
            install_cmd=install_cmd,
        )

    return result
