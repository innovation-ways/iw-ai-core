"""LLM-assisted merge conflict resolution — Phase 0/1 plumbing.

Reference: docs/research/R-00076-llm-automated-merge-resolution.md §5
Tracking: F-00084

Phase ladder:
    0 = plumbing only — decision tree runs, NO LLM call, NO state change.
    1 = dry-run — LLM invoked; proposed resolutions captured in DaemonEvent;
        worktree NEVER modified; rebase ALWAYS aborted. Operator UX unchanged.
    2 = tests-only auto-apply — RESERVED for follow-up CR. Refuse if set.
    3 = broader allowlist — RESERVED for follow-up CR. Refuse if set.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json as _json
import logging
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from orch.auto_merge_aggregator import resolve_project_config
from orch.db.models import AgentRuntimeOption, DaemonEvent

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Phase constants
# ---------------------------------------------------------------------------

PHASE_DISABLED = 0
PHASE_DRY_RUN = 1
PHASE_TESTS_ONLY = 2  # Reserved — refuse if encountered
PHASE_BROADER = 3  # Reserved — refuse if encountered

# ---------------------------------------------------------------------------
# Event type strings (TEXT column — no enum)
# ---------------------------------------------------------------------------

EVENT_AUTO_RESOLUTION_ATTEMPTED = "merge_auto_resolution_attempted"
EVENT_AUTO_RESOLVED = "merge_auto_resolved"
EVENT_AUTO_RESOLUTION_FAILED = "merge_auto_resolution_failed"
EVENT_AUTO_RESOLUTION_SKIPPED = "merge_auto_resolution_skipped"
EVENT_AUTO_MERGE_CONFIG_INVALID = "auto_merge_config_invalid"
EVENT_AUTO_MERGE_HEALTH_PROBE = "auto_merge_health_probe"
EVENT_AUTO_MERGE_CONFIG_UPDATED = "auto_merge_config_updated"

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class AutoMergeConfigError(RuntimeError):
    """Raised when the auto_merge.toml cannot be used."""


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

# Known binary file extensions — defence-in-depth alongside null-byte check
_BINARY_SUFFIXES = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".ico",
        ".bmp",
        ".svg",
        ".pdf",
        ".zst",
        ".gz",
        ".tar",
        ".zip",
        ".db",
        ".sqlite",
        ".sqlite3",
        ".parquet",
        ".pyc",
        ".so",
        ".dll",
        ".exe",
        ".whl",
    }
)

# Default values matching executor/auto_merge.toml
_DEFAULT_ALLOWLIST: tuple[str, ...] = (
    "tests/**/*.py",
    "docs/**/*.md",
    "ai-dev/active/**/reports/**",
    "ai-dev/active/**/I-*/reports/**",
    "ai-dev/active/**/F-*/reports/**",
    "ai-dev/active/**/CR-*/reports/**",
)

_DEFAULT_REFUSELIST: tuple[str, ...] = (
    "orch/db/migrations/versions/*.py",
    ".gitleaks.toml",
    ".env",
    ".env.*",
    ".gitignore",
    "orch/db/identity.py",
    "orch/config.py",
    "executor/worktree_commit.sh",
    "executor/worktree_setup.sh",
    "executor/step_executor.sh",
    "executor/step_executor_lib.sh",
    "executor/scope_gate.py",
    "executor/auto_merge.toml",
    "uv.lock",
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.zst",
    "*.tar.gz",
    "*.db",
    "*.sqlite",
    "*.parquet",
)


@dataclass(frozen=True)
class AutoMergeConfig:
    """Loaded configuration from executor/auto_merge.toml."""

    phase: int
    runtime_option_id: int | None
    allowlist_patterns: tuple[str, ...]
    refuselist_patterns: tuple[str, ...]
    max_conflict_hunk_lines: int
    max_conflicted_files_per_merge: int
    max_file_size_bytes: int
    max_event_metadata_bytes: int
    llm_call_timeout_seconds: int
    health_probe_interval_seconds: int = 300
    health_failure_rate_threshold_per_day: int = 3

    @classmethod
    def defaults(cls) -> AutoMergeConfig:
        """Return safe defaults (phase=0, conservative limits)."""
        return cls(
            phase=PHASE_DISABLED,
            runtime_option_id=None,
            allowlist_patterns=_DEFAULT_ALLOWLIST,
            refuselist_patterns=_DEFAULT_REFUSELIST,
            max_conflict_hunk_lines=80,
            max_conflicted_files_per_merge=5,
            max_file_size_bytes=256_000,
            max_event_metadata_bytes=262_144,
            llm_call_timeout_seconds=120,
            health_probe_interval_seconds=300,
            health_failure_rate_threshold_per_day=3,
        )

    @classmethod
    def load(cls, path: str) -> tuple[AutoMergeConfig, str | None]:
        """Load config from a TOML file.

        Returns:
            (config, None) on success.
            (defaults, error_string) on FileNotFoundError or parse error.

        Note: ``runtime_option_id = null`` is a common pattern in auto_merge.toml.
        Python's ``tomllib`` does not support TOML ``null`` (it is not part of the
        TOML spec). We pre-process lines matching ``<key> = null`` and remove them
        so the remaining TOML parses cleanly; the missing key then falls back to the
        Python-side default of ``None``.
        """
        import re as _re

        try:
            raw = Path(path).read_text(encoding="utf-8")
        except FileNotFoundError:
            logger.debug("auto_merge.toml not found at %s — using defaults", path)
            return cls.defaults(), None

        # Strip lines of the form `key = null` — these are conceptually "unset"
        # and tomllib would reject them (null is not a valid TOML value).
        # Track which keys were explicitly nulled so we can treat them as None.
        _nulled_keys: set[str] = set()
        cleaned_lines = []
        for line in raw.splitlines():
            m = _re.match(r"^\s*(\w+)\s*=\s*null\s*(?:#.*)?$", line)
            if m:
                _nulled_keys.add(m.group(1))
            else:
                cleaned_lines.append(line)
        cleaned_raw = "\n".join(cleaned_lines)

        try:
            data = tomllib.loads(cleaned_raw)
        except tomllib.TOMLDecodeError as exc:
            error_str = f"TOML parse error in {path}: {exc}"
            logger.error(error_str)
            return cls.defaults(), error_str

        try:
            allowlist_patterns = tuple(
                data.get("allowlist", {}).get("patterns", list(_DEFAULT_ALLOWLIST))
            )
            refuselist_patterns = tuple(
                data.get("refuselist", {}).get("patterns", list(_DEFAULT_REFUSELIST))
            )
            limits = data.get("limits", {})
            health = data.get("health", {})

            # runtime_option_id: explicit null → None; missing → None; integer → int
            runtime_option_id: int | None = None
            if "runtime_option_id" not in _nulled_keys:
                raw_rid = data.get("runtime_option_id")
                runtime_option_id = int(raw_rid) if raw_rid is not None else None

            phase = int(data.get("phase", PHASE_DISABLED))
            if phase not in (PHASE_DISABLED, PHASE_DRY_RUN):
                error_str = (
                    f"auto_merge.toml value error in {path}: "
                    f"phase={phase} is reserved for future CRs (allowed: 0, 1)"
                )
                logger.error(error_str)
                return cls.defaults(), error_str

            config = cls(
                phase=phase,
                runtime_option_id=runtime_option_id,
                allowlist_patterns=allowlist_patterns,
                refuselist_patterns=refuselist_patterns,
                max_conflict_hunk_lines=int(limits.get("max_conflict_hunk_lines", 80)),
                max_conflicted_files_per_merge=int(limits.get("max_conflicted_files_per_merge", 5)),
                max_file_size_bytes=int(limits.get("max_file_size_bytes", 256_000)),
                max_event_metadata_bytes=int(limits.get("max_event_metadata_bytes", 262_144)),
                llm_call_timeout_seconds=int(limits.get("llm_call_timeout_seconds", 120)),
                health_probe_interval_seconds=int(health.get("probe_interval_seconds", 300)),
                health_failure_rate_threshold_per_day=int(
                    health.get("failure_rate_threshold_per_day", 3)
                ),
            )
        except (KeyError, TypeError, ValueError) as exc:
            error_str = f"auto_merge.toml value error in {path}: {exc}"
            logger.error(error_str)
            return cls.defaults(), error_str

        logger.debug("Loaded auto_merge config from %s: phase=%d", path, config.phase)
        return config, None


@dataclass(frozen=True)
class ClassificationResult:
    """Result of classify_conflicts() — which files are eligible, and why not."""

    eligible_files: tuple[str, ...]
    refuse_files: tuple[str, ...]
    oversized_files: tuple[str, ...]
    oversized_hunks: tuple[str, ...]
    binary_files: tuple[str, ...]
    skipped_reason: str | None
    deferred_files: tuple[str, ...] = ()


@dataclass(frozen=True)
class LLMCallResult:
    """Result of a single per-file LLM invocation."""

    file_path: str
    abstained: bool
    proposed_content: str | None
    error: str | None
    model: str
    cli_tool: str
    input_tokens: int | None
    output_tokens: int | None
    prompt_hash: str
    output_hash: str | None


@dataclass(frozen=True)
class AutoMergeResult:
    """Aggregate result of attempt_resolution()."""

    success: bool
    phase: int
    resolved_files: tuple[str, ...]
    abstained_files: tuple[str, ...]
    error_files: tuple[str, ...]
    llm_calls: tuple[LLMCallResult, ...]


# ---------------------------------------------------------------------------
# Module-level config cache (for hot-reload integration)
# ---------------------------------------------------------------------------

_cached_config: AutoMergeConfig | None = None


def reload_config(path: str) -> AutoMergeConfig:
    """Load (or reload) config from the given path and update the cache."""
    global _cached_config  # noqa: PLW0603
    config, error = AutoMergeConfig.load(path)
    if error:
        logger.warning("auto_merge.reload_config: parse error — keeping previous cache: %s", error)
    else:
        _cached_config = config
    return config


# ---------------------------------------------------------------------------
# Binary file detection helpers
# ---------------------------------------------------------------------------


def _is_binary_file(path: Path) -> bool:
    """Return True if the file appears to be binary.

    Checks:
    1. Known binary suffix.
    2. Null byte in the first 8192 bytes.
    """
    if path.suffix.lower() in _BINARY_SUFFIXES:
        return True
    try:
        return b"\x00" in path.read_bytes()[:8192]
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Hunk size measurement
# ---------------------------------------------------------------------------


def _count_conflict_hunk_lines(content: str) -> int:
    """Return the maximum number of lines within a single conflict block.

    Counts lines between <<<<<<< and >>>>>>> (inclusive of separators).
    Returns 0 if no conflict markers are found.
    """
    max_lines = 0
    in_conflict = False
    current_lines = 0

    for line in content.splitlines():
        if line.startswith("<<<<<<<"):
            in_conflict = True
            current_lines = 1
        elif line.startswith(">>>>>>>") and in_conflict:
            current_lines += 1
            max_lines = max(max_lines, current_lines)
            in_conflict = False
            current_lines = 0
        elif in_conflict:
            current_lines += 1

    return max_lines


# ---------------------------------------------------------------------------


def classify_conflicts(
    worktree_path: Path,
    conflict_files: list[str],
    config: AutoMergeConfig,
) -> ClassificationResult:
    """Apply the decision tree to classify conflicted files.

    Decision tree (highest to lowest precedence):
    1. Any refuse-list match → skipped_reason = "refuse_list"
    2. Any binary file → skipped_reason = "binary"
    3. Any oversized file (size > max_file_size_bytes) → skipped_reason = "file_too_large"
    4. Any oversized hunk (lines > max_conflict_hunk_lines) → skipped_reason = "hunk_too_large"
    5. len(conflict_files) > max_conflicted_files_per_merge → "too_many_files"
    6. Allowlist partition:
       - eligible_files = files matching allowlist_patterns
       - deferred_files = files matching NEITHER refuse-list (already returned above)
         NOR allowlist
       - If eligible_files is empty, return skipped_reason="not_allowlisted"
         with the deferred list populated.
       - Otherwise return skipped_reason=None with both lists populated
         (the LLM will only be invoked for eligible_files).
    7. Else → eligible_files = all; skipped_reason = None
    """
    logger.info(
        "classify_conflicts: %d files against config phase=%d", len(conflict_files), config.phase
    )

    refuse_files: list[str] = []
    binary_files: list[str] = []
    oversized_files: list[str] = []
    oversized_hunks: list[str] = []

    for rel_path in conflict_files:
        # 1. Refuse-list check (glob match against each pattern)
        if any(fnmatch.fnmatchcase(rel_path, pat) for pat in config.refuselist_patterns):
            refuse_files.append(rel_path)

    if refuse_files:
        logger.info("classify_conflicts: refuse_list hit on %s", refuse_files)
        return ClassificationResult(
            eligible_files=(),
            refuse_files=tuple(refuse_files),
            oversized_files=(),
            oversized_hunks=(),
            binary_files=(),
            skipped_reason="refuse_list",
        )

    # 2. Binary check
    for rel_path in conflict_files:
        abs_path = worktree_path / rel_path
        if _is_binary_file(abs_path):
            binary_files.append(rel_path)

    if binary_files:
        logger.info("classify_conflicts: binary files detected: %s", binary_files)
        return ClassificationResult(
            eligible_files=(),
            refuse_files=(),
            oversized_files=(),
            oversized_hunks=(),
            binary_files=tuple(binary_files),
            skipped_reason="binary",
        )

    # 3. File size check
    for rel_path in conflict_files:
        abs_path = worktree_path / rel_path
        try:
            size = abs_path.stat().st_size
        except OSError:
            size = 0
        if size > config.max_file_size_bytes:
            oversized_files.append(rel_path)

    if oversized_files:
        logger.info("classify_conflicts: file_too_large: %s", oversized_files)
        return ClassificationResult(
            eligible_files=(),
            refuse_files=(),
            oversized_files=tuple(oversized_files),
            oversized_hunks=(),
            binary_files=(),
            skipped_reason="file_too_large",
        )

    # 4. Hunk size check
    for rel_path in conflict_files:
        abs_path = worktree_path / rel_path
        try:
            content = abs_path.read_text(errors="replace")
        except OSError:
            content = ""
        hunk_lines = _count_conflict_hunk_lines(content)
        if hunk_lines > config.max_conflict_hunk_lines:
            oversized_hunks.append(rel_path)

    if oversized_hunks:
        logger.info("classify_conflicts: hunk_too_large: %s", oversized_hunks)
        return ClassificationResult(
            eligible_files=(),
            refuse_files=(),
            oversized_files=(),
            oversized_hunks=tuple(oversized_hunks),
            binary_files=(),
            skipped_reason="hunk_too_large",
        )

    # 5. Too-many-files check
    if len(conflict_files) > config.max_conflicted_files_per_merge:
        logger.info(
            "classify_conflicts: too_many_files (%d > %d)",
            len(conflict_files),
            config.max_conflicted_files_per_merge,
        )
        return ClassificationResult(
            eligible_files=(),
            refuse_files=(),
            oversized_files=(),
            oversized_hunks=(),
            binary_files=(),
            skipped_reason="too_many_files",
        )

    # 6. Allowlist partition
    eligible_files: list[str] = []
    deferred_files: list[str] = []
    for rel_path in conflict_files:
        if any(fnmatch.fnmatchcase(rel_path, pat) for pat in config.allowlist_patterns):
            eligible_files.append(rel_path)
        else:
            deferred_files.append(rel_path)

    if not eligible_files:
        # Every file is deferred — preserve today's skip behaviour, now with explicit deferred list
        logger.info("classify_conflicts: not_allowlisted (all deferred): %s", deferred_files)
        return ClassificationResult(
            eligible_files=(),
            refuse_files=(),
            oversized_files=(),
            oversized_hunks=(),
            binary_files=(),
            skipped_reason="not_allowlisted",
            deferred_files=tuple(deferred_files),
        )

    if deferred_files:
        logger.info(
            "classify_conflicts: partial allowlist — eligible=%s deferred=%s",
            eligible_files,
            deferred_files,
        )

    # 7. At least one file is eligible (partial OR full allowlist match)
    logger.info(
        "classify_conflicts: %d eligible, %d deferred",
        len(eligible_files),
        len(deferred_files),
    )
    return ClassificationResult(
        eligible_files=tuple(eligible_files),
        refuse_files=(),
        oversized_files=(),
        oversized_hunks=(),
        binary_files=(),
        skipped_reason=None,
        deferred_files=tuple(deferred_files),
    )


# ---------------------------------------------------------------------------


def build_resolution_prompt(
    *,
    worktree_path: str,
    file_path: str,
    main_sha: str,
    branch_name: str,
    item_id: str,
    item_title: str,
    item_description: str,
) -> str:
    """Build the LLM resolution prompt for a single conflicted file.

    Must be deterministic given identical inputs.
    Per R-00076 §5.5.
    """
    logger.info("build_resolution_prompt: item_id=%s file_path=%s", item_id, file_path)

    # Truncate description to first 500 words
    words = item_description.split()
    truncated_desc = " ".join(words[:500])

    def _git_show(ref: str) -> str:
        """Run `git show <ref>` and return stdout; return empty string on error."""
        try:
            result = subprocess.run(  # noqa: S603
                ["git", "show", ref],  # noqa: S607
                cwd=worktree_path,
                capture_output=True,
                text=True,
                timeout=30,
            )
            return (
                result.stdout
                if result.returncode == 0
                else f"(unavailable: {result.stderr.strip()})"
            )
        except Exception as exc:
            return f"(error: {exc})"

    def _git_log(rev: str) -> str:
        """Run `git log -p -n 3 <rev> -- <file>` and return stdout."""
        try:
            result = subprocess.run(  # noqa: S603
                ["git", "log", "-p", "-n", "3", rev, "--", file_path],  # noqa: S607
                cwd=worktree_path,
                capture_output=True,
                text=True,
                timeout=30,
            )
            return (
                result.stdout
                if result.returncode == 0
                else f"(unavailable: {result.stderr.strip()})"
            )
        except Exception as exc:
            return f"(error: {exc})"

    merge_base_content = _git_show(f":1:{file_path}")
    ours_content = _git_show(f":2:{file_path}")
    theirs_content = _git_show(f":3:{file_path}")
    main_log = _git_log(main_sha)
    branch_log = _git_log("HEAD")

    return f"""# Merge Conflict Resolution Request

## Work Item
- ID: {item_id}
- Title: {item_title}
- Description (first 500 words):
{truncated_desc}

## File to Resolve
- Path: {file_path}
- Branch: {branch_name}
- Main SHA: {main_sha}

## Merge-Base Content (common ancestor — :1:{file_path})
```
{merge_base_content}
```

## Main Branch Version (ours — :2:{file_path})
```
{ours_content}
```

## Feature Branch Version (theirs — :3:{file_path})
```
{theirs_content}
```

## Recent Commit History on Main (last 3 commits touching this file)
```
{main_log}
```

## Recent Commit History on Feature Branch (last 3 commits touching this file)
```
{branch_log}
```

## Instructions

You must resolve the merge conflict in `{file_path}`.

Rules:
1. Output ONLY the complete resolved file content — no markdown fences, no prose.
2. Do NOT invent code, logic, or content not in the main or branch version.
3. If uncertain, output exactly: ABSTAIN (a single word on its own line).
4. The output must be the full file content ready to write directly to disk.
5. Do not include conflict markers (<<<<<<<, =======, >>>>>>>) in the output.

Output ABSTAIN if:
- The conflict requires semantics you cannot safely resolve from file content alone.
- The two versions make logically incompatible changes.
- You are not confident your resolution is correct.
"""


# ---------------------------------------------------------------------------


def _resolve_runtime_option(
    db: Session,
    project_id: str,
    config: AutoMergeConfig,
) -> AgentRuntimeOption | None:
    """Resolve the (cli_tool, model) pair to use for LLM calls.

    Order:
    1. If config.runtime_option_id is set: load that row; if missing/disabled, fall through.
    2. Project default: AgentRuntimeOption where is_default=True AND enabled=True.
    3. Return None.
    """
    resolved = resolve_project_config(db, project_id, config)
    logger.info(
        "_resolve_runtime_option: project_id=%s runtime_option_id=%s source=%s",
        project_id,
        resolved.runtime_option_id,
        resolved.source,
    )

    if resolved.runtime_option_id is not None:
        row = db.get(AgentRuntimeOption, resolved.runtime_option_id)
        if row is not None and row.enabled:
            return row

    # Fall back to project default (global singleton — no project_id FK on this table)
    return (
        db.query(AgentRuntimeOption)
        .filter(
            AgentRuntimeOption.is_default.is_(True),
            AgentRuntimeOption.enabled.is_(True),
        )
        .first()
    )


# ---------------------------------------------------------------------------

# Path to the executor directory (sibling of the orch package)
_EXECUTOR_DIR = Path(__file__).resolve().parent.parent.parent / "executor"


def invoke_llm_for_file(
    *,
    worktree_path: str,
    file_path: str,
    main_sha: str,
    branch_name: str,
    item_id: str,
    item_title: str,
    item_description: str,
    cli_tool: str,
    model: str,
    config: AutoMergeConfig,
) -> LLMCallResult:
    """Invoke the LLM agent for a single conflicted file (Phase 1 — read-only).

    Calls executor/step_executor_lib.sh via step_type=auto_merge_resolve.
    Always returns an LLMCallResult; never raises.
    """
    logger.info(
        "invoke_llm_for_file: item_id=%s file_path=%s cli_tool=%s model=%s",
        item_id,
        file_path,
        cli_tool,
        model,
    )

    prompt = build_resolution_prompt(
        worktree_path=worktree_path,
        file_path=file_path,
        main_sha=main_sha,
        branch_name=branch_name,
        item_id=item_id,
        item_title=item_title,
        item_description=item_description,
    )
    prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()

    step_executor_lib = _EXECUTOR_DIR / "step_executor_lib.sh"

    try:
        result = subprocess.run(  # noqa: S603
            [  # noqa: S607
                "bash",
                str(step_executor_lib),
                "auto_merge_resolve",
                cli_tool,
                model,
            ],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=config.llm_call_timeout_seconds,
            env={
                "WORKTREE_PATH": worktree_path,
                "PATH": "/usr/local/bin:/usr/bin:/bin",
            },
        )
    except subprocess.TimeoutExpired as exc:
        logger.warning(
            "invoke_llm_for_file: timeout for item_id=%s file_path=%s", item_id, file_path
        )
        return LLMCallResult(
            file_path=file_path,
            abstained=False,
            proposed_content=None,
            error=f"LLM call timed out after {config.llm_call_timeout_seconds}s: {exc}",
            model=model,
            cli_tool=cli_tool,
            input_tokens=None,
            output_tokens=None,
            prompt_hash=prompt_hash,
            output_hash=None,
        )
    except Exception as exc:
        logger.warning(
            "invoke_llm_for_file: subprocess error for item_id=%s file_path=%s: %s",
            item_id,
            file_path,
            exc,
        )
        return LLMCallResult(
            file_path=file_path,
            abstained=False,
            proposed_content=None,
            error=str(exc),
            model=model,
            cli_tool=cli_tool,
            input_tokens=None,
            output_tokens=None,
            prompt_hash=prompt_hash,
            output_hash=None,
        )

    if result.returncode != 0:
        logger.warning(
            "invoke_llm_for_file: non-zero exit for item_id=%s file_path=%s: %s",
            item_id,
            file_path,
            result.stderr[:500],
        )
        return LLMCallResult(
            file_path=file_path,
            abstained=False,
            proposed_content=None,
            error=f"exit code {result.returncode}: {result.stderr[:500]}",
            model=model,
            cli_tool=cli_tool,
            input_tokens=None,
            output_tokens=None,
            prompt_hash=prompt_hash,
            output_hash=None,
        )

    stdout = result.stdout.strip()

    if stdout.upper().startswith("ABSTAIN"):
        logger.info(
            "invoke_llm_for_file: LLM abstained for item_id=%s file_path=%s", item_id, file_path
        )
        return LLMCallResult(
            file_path=file_path,
            abstained=True,
            proposed_content=None,
            error=None,
            model=model,
            cli_tool=cli_tool,
            input_tokens=None,
            output_tokens=None,
            prompt_hash=prompt_hash,
            output_hash=None,
        )

    output_hash = hashlib.sha256(stdout.encode()).hexdigest()
    logger.info(
        "invoke_llm_for_file: proposed resolution for item_id=%s file_path=%s output_hash=%s",
        item_id,
        file_path,
        output_hash,
    )
    return LLMCallResult(
        file_path=file_path,
        abstained=False,
        proposed_content=stdout,
        error=None,
        model=model,
        cli_tool=cli_tool,
        input_tokens=None,
        output_tokens=None,
        prompt_hash=prompt_hash,
        output_hash=output_hash,
    )


# ---------------------------------------------------------------------------


def attempt_resolution(
    *,
    db: Session,
    project_id: str,
    item_id: str,
    item_title: str,
    item_description: str,
    worktree_path: str,
    main_sha: str,
    branch_name: str,
    eligible_files: list[str],
    config: AutoMergeConfig,
    deferred_files: list[str] | None = None,
) -> AutoMergeResult:
    """Attempt LLM-assisted resolution for the given eligible files.

    Phase 0: no LLM call; emits EVENT_AUTO_RESOLUTION_SKIPPED.
    Phase 1: calls LLM; captures proposals in DaemonEvents; NEVER modifies worktree.
    Phase >= 2: raises ValueError (reserved).

    Args:
        deferred_files: Files excluded from LLM invocation because they fall outside
            the allowlist (i.e., non-allowlisted conflict files). When non-None and
            non-empty, these are recorded in event metadata for operator visibility.
            The LLM is invoked only for eligible_files regardless of this parameter.
    """
    if config.phase >= PHASE_TESTS_ONLY:
        raise ValueError(f"phase {config.phase} reserved for follow-up CR")

    resolved_cfg = resolve_project_config(db, project_id, config)
    logger.info(
        "attempt_resolution: item_id=%s phase=%d eligible_files=%s",
        item_id,
        resolved_cfg.phase,
        eligible_files,
    )

    if resolved_cfg.phase == PHASE_DISABLED:
        # Phase 0: emit skip event, zero subprocess calls
        _emit_event(
            db,
            project_id,
            EVENT_AUTO_RESOLUTION_SKIPPED,
            item_id,
            "work_item",
            "Auto-merge skipped: phase_0 (dry-run disabled)",
            {
                "reason": "phase_0",
                "eligible_files": eligible_files,
                "deferred_files": list(deferred_files or []),
            },
        )
        db.commit()
        logger.info("attempt_resolution: phase_0 skip for item_id=%s", item_id)
        return AutoMergeResult(
            success=False,
            phase=PHASE_DISABLED,
            resolved_files=(),
            abstained_files=(),
            error_files=tuple(eligible_files),
            llm_calls=(),
        )

    # Phase 1: dry-run — invoke LLM, capture proposals, never apply
    runtime_option = _resolve_runtime_option(db, project_id, config)
    if runtime_option is None:
        logger.warning(
            "attempt_resolution: no runtime option for project_id=%s item_id=%s",
            project_id,
            item_id,
        )
        _emit_event(
            db,
            project_id,
            EVENT_AUTO_RESOLUTION_FAILED,
            item_id,
            "work_item",
            "Auto-merge failed: no runtime option available",
            {
                "reason": "runtime_option_missing",
                "project_id": project_id,
            },
        )
        db.commit()
        return AutoMergeResult(
            success=False,
            phase=PHASE_DRY_RUN,
            resolved_files=(),
            abstained_files=(),
            error_files=tuple(eligible_files),
            llm_calls=(),
        )

    _emit_event(
        db,
        project_id,
        EVENT_AUTO_RESOLUTION_ATTEMPTED,
        item_id,
        "work_item",
        f"Auto-merge resolution attempted: {len(eligible_files)} file(s)",
        {
            "phase": PHASE_DRY_RUN,
            "conflict_files": eligible_files,
            "policy_decision": "allowlist",
            "runtime_option_id": runtime_option.id,
            "allowlisted_files": eligible_files,
            "deferred_files": list(deferred_files or []),
        },
    )
    db.commit()

    llm_calls: list[LLMCallResult] = []
    abstained_files: list[str] = []
    error_files: list[str] = []
    proposed_files: list[str] = []

    for file_path in eligible_files:
        call_result = invoke_llm_for_file(
            worktree_path=worktree_path,
            file_path=file_path,
            main_sha=main_sha,
            branch_name=branch_name,
            item_id=item_id,
            item_title=item_title,
            item_description=item_description,
            cli_tool=runtime_option.cli_tool,
            model=runtime_option.model,
            config=config,
        )
        llm_calls.append(call_result)

        if call_result.error is not None:
            error_files.append(file_path)
        elif call_result.abstained:
            abstained_files.append(file_path)
        else:
            proposed_files.append(file_path)

    total_input_tokens = sum(c.input_tokens or 0 for c in llm_calls)
    total_output_tokens = sum(c.output_tokens or 0 for c in llm_calls)

    # Build per-file error detail for the failed event.
    # Size budget: max_conflicted_files_per_merge = 5, each error capped at 500 chars
    # plus ~80 chars of metadata overhead → worst-case ~3.5 KB, well under the
    # 256 KB default max_event_metadata_bytes limit. No truncation pass needed.
    per_file_errors: list[dict[str, str]] = [
        {
            "file_path": call.file_path,
            "error": call.error[:500],  # cap per design §AC5
            "cli_tool": call.cli_tool,
            "model": call.model,
        }
        for call in llm_calls
        if call.error is not None
    ]

    if abstained_files or error_files:
        _emit_event(
            db,
            project_id,
            EVENT_AUTO_RESOLUTION_FAILED,
            item_id,
            "work_item",
            (
                f"Auto-merge resolution incomplete: {len(abstained_files)} abstained,"
                f" {len(error_files)} errored"
            ),
            {
                "phase": PHASE_DRY_RUN,
                "abstained_files": abstained_files,
                "error_files": error_files,
                "proposed_files": proposed_files,
                "runtime_option_id": runtime_option.id,
                "total_input_tokens": total_input_tokens,
                "total_output_tokens": total_output_tokens,
                "per_file_errors": per_file_errors,
                "deferred_files": list(deferred_files or []),
            },
        )
    else:
        # Build per-file metadata, size-capped
        per_file = []
        for call in llm_calls:
            content_snippet = (call.proposed_content or "")[:2000]
            per_file.append(
                {
                    "file_path": call.file_path,
                    "proposed_content": content_snippet,
                    "prompt_hash": call.prompt_hash,
                    "output_hash": call.output_hash,
                }
            )
        metadata: dict[str, Any] = {
            "phase": PHASE_DRY_RUN,
            "resolved_files": proposed_files,
            "per_file": per_file,
            "runtime_option_id": runtime_option.id,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "deferred_files": list(deferred_files or []),
        }
        # Enforce max_event_metadata_bytes
        raw = _json.dumps(metadata)
        if len(raw.encode()) > config.max_event_metadata_bytes:
            # Truncate per_file proposed_content entries
            for entry in metadata["per_file"]:
                entry["proposed_content"] = entry["proposed_content"][:200] + "...[truncated]"
            metadata["truncated"] = True

        # Build resolved event message with deferred count
        if deferred_files:
            resolved_msg = (
                f"Auto-merge dry-run: proposed resolutions for {len(proposed_files)}"
                f" file(s); {len(deferred_files)} file(s) deferred (non-allowlisted)"
                f" for operator"
            )
        else:
            resolved_msg = (
                f"Auto-merge dry-run: proposed resolutions for {len(proposed_files)} file(s)"
            )
        _emit_event(
            db,
            project_id,
            EVENT_AUTO_RESOLVED,
            item_id,
            "work_item",
            resolved_msg,
            metadata,
        )

    db.commit()

    # Phase 1 ALWAYS returns success=False — never auto-applies
    return AutoMergeResult(
        success=False,
        phase=PHASE_DRY_RUN,
        resolved_files=(),
        abstained_files=tuple(abstained_files),
        error_files=tuple(error_files),
        llm_calls=tuple(llm_calls),
    )


# ---------------------------------------------------------------------------
# Marker parsing
# ---------------------------------------------------------------------------

_RESOLVE_MARKER_PREFIX = "AUTO_RESOLVE_REQUESTED="
_SKIP_MARKER_PREFIX = "AUTO_RESOLVE_SKIPPED="


def parse_auto_resolve_marker(output: str) -> dict[str, Any] | None:
    """Parse AUTO_RESOLVE_REQUESTED=<json> from worktree_commit.sh stdout.

    Returns parsed dict or None if absent or malformed.
    """
    for line in output.splitlines():
        if line.startswith(_RESOLVE_MARKER_PREFIX):
            json_str = line[len(_RESOLVE_MARKER_PREFIX) :]
            try:
                parsed: dict[str, Any] = _json.loads(json_str)
                return parsed
            except _json.JSONDecodeError as exc:
                logger.warning("parse_auto_resolve_marker: malformed JSON: %s", exc)
                return None
    return None


def parse_auto_skip_marker(output: str) -> dict[str, Any] | None:
    """Parse AUTO_RESOLVE_SKIPPED=<json> from worktree_commit.sh stdout.

    Returns parsed dict or None if absent or malformed.
    """
    for line in output.splitlines():
        if line.startswith(_SKIP_MARKER_PREFIX):
            json_str = line[len(_SKIP_MARKER_PREFIX) :]
            try:
                parsed: dict[str, Any] = _json.loads(json_str)
                return parsed
            except _json.JSONDecodeError as exc:
                logger.warning("parse_auto_skip_marker: malformed JSON: %s", exc)
                return None
    return None


# ---------------------------------------------------------------------------
# Event helpers for merge_queue.py integration
# ---------------------------------------------------------------------------


def _emit_event(
    db: Session,
    project_id: str,
    event_type: str,
    entity_id: str | None,
    entity_type: str | None = None,
    message: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Insert a DaemonEvent (caller commits)."""
    event = DaemonEvent(
        project_id=project_id,
        event_type=event_type,
        entity_id=entity_id,
        entity_type=entity_type,
        message=message,
        event_metadata=metadata or {},
    )
    db.add(event)


def emit_skipped_event(
    db: Session,
    project_id: str,
    item_id: str,
    details: dict[str, Any],
) -> None:
    """Emit EVENT_AUTO_RESOLUTION_SKIPPED and commit."""
    logger.info("emit_skipped_event: item_id=%s reason=%s", item_id, details.get("reason"))
    _emit_event(
        db,
        project_id,
        EVENT_AUTO_RESOLUTION_SKIPPED,
        item_id,
        "work_item",
        f"Auto-merge skipped: {details.get('reason', 'unknown')}",
        details,
    )
    db.commit()


def emit_config_invalid_event(
    db: Session,
    project_id: str,
    item_id: str,
    error_str: str,
) -> None:
    """Emit EVENT_AUTO_MERGE_CONFIG_INVALID and commit."""
    logger.error("emit_config_invalid_event: item_id=%s error=%s", item_id, error_str)
    _emit_event(
        db,
        project_id,
        EVENT_AUTO_MERGE_CONFIG_INVALID,
        item_id,
        "work_item",
        f"auto_merge.toml parse error: {error_str}",
        {"error": error_str},
    )
    db.commit()


def emit_event(
    db: Session,
    project_id: str,
    item_id: str,
    event_type: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Public convenience wrapper — emits any event type and commits."""
    _emit_event(
        db,
        project_id,
        event_type,
        item_id,
        "work_item",
        None,
        metadata,
    )
    db.commit()
