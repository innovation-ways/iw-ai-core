"""Fix recipes for repository hygiene compliance checks (OSS-HYG-*, OSS-ENV-04)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from . import register
from .base import FixPreview

if TYPE_CHECKING:
    from pathlib import Path

SECRET_PATTERNS = [".env", "*.pem", "*.key", "*.pfx", "*.p12"]
LANGUAGE_IGNORES = {
    "python": ["__pycache__/", ".venv/", "*.pyc", ".pytest_cache/"],
    "node": ["node_modules/"],
    "go": [],
    "rust": ["target/"],
    "java": ["target/", "build/"],
}


def _read_gitignore(repo_root: Path) -> tuple[str, set[str]]:
    """Read the .gitignore file and return its raw text plus a set of active patterns.

    Args:
        repo_root: Repository root directory to look up .gitignore in.

    Returns:
        Tuple of (raw_text, patterns_set) where patterns_set contains every
        non-blank, non-comment line stripped of surrounding whitespace.
    """
    gi = repo_root / ".gitignore"
    existing = gi.read_text() if gi.exists() else ""
    lines = existing.splitlines()
    gi_set = {line.strip() for line in lines if line.strip() and not line.strip().startswith("#")}
    return existing, gi_set


def _detect_ecosystems(repo_root: Path) -> list[str]:
    """Infer the project's language ecosystem(s) from well-known manifest files.

    Checks for pyproject.toml/setup.py/requirements.txt (Python), package.json
    (Node), go.mod (Go), Cargo.toml (Rust), and pom.xml/build.gradle (Java).

    Args:
        repo_root: Repository root directory to inspect.

    Returns:
        List of detected ecosystem names (e.g. ``["python"]``). Returns an
        empty list when no known manifest is found.
    """
    if (
        (repo_root / "pyproject.toml").exists()
        or (repo_root / "setup.py").exists()
        or (repo_root / "requirements.txt").exists()
    ):
        return ["python"]
    if (repo_root / "package.json").exists():
        return ["node"]
    if (repo_root / "go.mod").exists():
        return ["go"]
    if (repo_root / "Cargo.toml").exists():
        return ["rust"]
    if (repo_root / "pom.xml").exists() or (repo_root / "build.gradle").exists():
        return ["java"]
    return []


class GitignoreSecretsRecipe:
    """Fix recipe that adds secret file patterns to .gitignore.

    Addresses OSS-HYG-01: .gitignore missing patterns for common credential
    files such as .env, PEM keys, and PKCS#12 keystores.
    """

    check_id = "OSS-HYG-01"
    auto_apply_safe = True

    def preview(self, repo_root: Path) -> FixPreview:
        existing, gi_set = _read_gitignore(repo_root)
        missing = [p for p in SECRET_PATTERNS if p not in gi_set]
        if not missing:
            return FixPreview(
                target_files=[],
                full_contents={},
                diffs={},
                notes="No changes needed.",
            )
        new_lines = list(missing)
        new_content = (
            existing.rstrip() + "\n\n# IW OSS — secrets patterns\n" + "\n".join(new_lines) + "\n"
        )
        import difflib

        diff = "".join(
            difflib.unified_diff(existing.splitlines(), new_content.splitlines(), lineterm="")
        )
        return FixPreview(
            target_files=[repo_root / ".gitignore"],
            full_contents={},
            diffs={repo_root / ".gitignore": diff},
            notes=f"Adding {len(missing)} secret pattern(s) to .gitignore.",
        )

    def apply(self, repo_root: Path) -> FixPreview:
        preview = self.preview(repo_root)
        if not preview.target_files:
            return preview
        gi = preview.target_files[0]
        existing = gi.read_text() if gi.exists() else ""
        existing_lines = set(existing.splitlines())
        missing = [p for p in SECRET_PATTERNS if p not in existing_lines]
        if not missing:
            return preview
        new_lines = list(missing)
        new_content = (
            existing.rstrip() + "\n\n# IW OSS — secrets patterns\n" + "\n".join(new_lines) + "\n"
        )
        gi.write_text(new_content)
        return preview


register(GitignoreSecretsRecipe())


class GitignoreLanguageRecipe:
    """Fix recipe that adds language-specific build artifact patterns to .gitignore.

    Addresses OSS-HYG-03: .gitignore missing ecosystem-standard patterns such
    as __pycache__/, .venv/, node_modules/, or target/. The set of patterns
    added depends on which language manifests are detected in the repository.
    """

    check_id = "OSS-HYG-03"
    auto_apply_safe = True

    def preview(self, repo_root: Path) -> FixPreview:
        existing, gi_set = _read_gitignore(repo_root)
        ecosystems = _detect_ecosystems(repo_root)
        missing = []
        for eco in ecosystems:
            for pat in LANGUAGE_IGNORES.get(eco, []):
                if pat not in gi_set:
                    missing.append(pat)
        if not missing:
            return FixPreview(
                target_files=[],
                full_contents={},
                diffs={},
                notes="No changes needed.",
            )
        new_content = (
            existing.rstrip() + "\n\n# IW OSS — language ignores\n" + "\n".join(missing) + "\n"
        )
        import difflib

        diff = "".join(
            difflib.unified_diff(existing.splitlines(), new_content.splitlines(), lineterm="")
        )
        return FixPreview(
            target_files=[repo_root / ".gitignore"],
            full_contents={},
            diffs={repo_root / ".gitignore": diff},
            notes=f"Adding {len(missing)} language ignore(s) to .gitignore.",
        )

    def apply(self, repo_root: Path) -> FixPreview:
        preview = self.preview(repo_root)
        if not preview.target_files:
            return preview
        gi = preview.target_files[0]
        existing = gi.read_text() if gi.exists() else ""
        existing_lines = set(existing.splitlines())
        ecosystems = _detect_ecosystems(repo_root)
        missing = []
        for eco in ecosystems:
            for pat in LANGUAGE_IGNORES.get(eco, []):
                if pat not in existing_lines:
                    missing.append(pat)
        if not missing:
            return preview
        new_content = (
            existing.rstrip() + "\n\n# IW OSS — language ignores\n" + "\n".join(missing) + "\n"
        )
        gi.write_text(new_content)
        return preview


register(GitignoreLanguageRecipe())


class IwDirGitignoreRecipe:
    """Fix recipe that adds the .iw/ directory to .gitignore.

    Addresses OSS-ENV-04: the IW AI Core working directory (.iw/) is not
    excluded from version control, risking accidental commits of generated
    scan artefacts and local config overrides.
    """

    check_id = "OSS-ENV-04"
    auto_apply_safe = True

    def preview(self, repo_root: Path) -> FixPreview:
        gi = repo_root / ".gitignore"
        existing = gi.read_text() if gi.exists() else ""
        if ".iw" in existing.splitlines():
            return FixPreview(
                target_files=[],
                full_contents={},
                diffs={},
                notes="No changes needed.",
            )
        new_content = existing.rstrip() + "\n\n# IW AI Core\n.iw/\n"
        import difflib

        diff = "".join(
            difflib.unified_diff(existing.splitlines(), new_content.splitlines(), lineterm="")
        )
        return FixPreview(
            target_files=[gi],
            full_contents={},
            diffs={gi: diff},
            notes="Adding .iw/ to .gitignore.",
        )

    def apply(self, repo_root: Path) -> FixPreview:
        preview = self.preview(repo_root)
        if not preview.target_files:
            return preview
        gi = preview.target_files[0]
        existing = gi.read_text() if gi.exists() else ""
        if ".iw/" in existing.splitlines():
            return preview
        new_content = existing.rstrip() + "\n\n# IW AI Core\n.iw/\n"
        gi.write_text(new_content)
        return preview


register(IwDirGitignoreRecipe())
