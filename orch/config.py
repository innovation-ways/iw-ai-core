"""Platform configuration loaded from environment variables.

Loads `.env` from the repo root via python-dotenv.
Fails fast with a clear error if any required variable is missing.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from orch.rag.config import DEFAULT_INDEX_PATH

# Load .env from the repo root (two levels up from this file: orch/config.py -> orch/ -> repo root)
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
CORE_ROOT: Path = _ENV_FILE.parent
load_dotenv(_ENV_FILE)

# Re-export the canonical default so `orch.config.DEFAULT_INDEX_PATH` and
# `orch.rag.config.DEFAULT_INDEX_PATH` refer to the same value.
__all__ = (
    "CORE_ROOT",
    "DEFAULT_INDEX_PATH",
    "DaemonConfig",
    "get_db_url",
    "get_orch_db_url",
    "get_db_pool_size",
    "get_db_max_overflow",
    "load_config",
)


def _require(name: str) -> str:
    """Return the value of a required env var, raising RuntimeError if missing."""
    value = os.environ.get(name)
    if value is None:
        raise RuntimeError(
            f"Required environment variable '{name}' is not set. "
            f"Check your .env file (expected at {_ENV_FILE})."
        )
    return value


_AGENT_LEAK_RUNBOOK = (
    "I-00062: agent subprocess resolved IW_CORE_DB_PORT to the "
    "operator's orch DB port. This indicates the agent inherited "
    "the daemon's orch DB credentials. See "
    "ai-dev/done/I-00062/I-00062_Issue_Design.md for the runbook."
)


def _check_agent_context_does_not_resolve_to_orch_port(port: str) -> None:
    """Refuse to return a DB URL when an agent process resolves to
    the operator's orch port — indicates env-leak from the daemon."""
    import os  # noqa: PLC0415

    if os.environ.get("IW_CORE_AGENT_CONTEXT", "").lower() != "true":
        return
    operator_orch_port = os.environ.get("IW_CORE_ORCH_DB_PORT")
    if operator_orch_port is None:
        return
    if str(port) == str(operator_orch_port):
        raise RuntimeError(_AGENT_LEAK_RUNBOOK)


def get_db_url() -> str:
    """Build the SQLAlchemy database URL from individual env vars."""
    host = _require("IW_CORE_DB_HOST")
    port = _require("IW_CORE_DB_PORT")
    _check_agent_context_does_not_resolve_to_orch_port(port)
    name = _require("IW_CORE_DB_NAME")
    user = _require("IW_CORE_DB_USER")
    password = _require("IW_CORE_DB_PASSWORD")
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{name}"


def get_orch_db_url() -> str:
    """Build the orch DB URL, preferring IW_CORE_ORCH_DB_* over IW_CORE_DB_*.

    In browser-verification steps IW_CORE_DB_* is overridden to an isolated
    E2E container. IW_CORE_ORCH_DB_* is injected by browser_env._build_env to
    preserve the real orch DB credentials. The iw CLI uses this function so
    step-done/fail/start always reach the orch DB regardless of context.
    """

    def _prefer(orch_key: str, fallback_key: str) -> str:
        return os.environ.get(orch_key) or _require(fallback_key)

    host = _prefer("IW_CORE_ORCH_DB_HOST", "IW_CORE_DB_HOST")
    port = _prefer("IW_CORE_ORCH_DB_PORT", "IW_CORE_DB_PORT")
    name = _prefer("IW_CORE_ORCH_DB_NAME", "IW_CORE_DB_NAME")
    user = _prefer("IW_CORE_ORCH_DB_USER", "IW_CORE_DB_USER")
    password = _prefer("IW_CORE_ORCH_DB_PASSWORD", "IW_CORE_DB_PASSWORD")
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{name}"


def get_db_pool_size() -> int:
    """Return the DB connection pool size from env, defaulting to 20."""
    return int(os.environ.get("IW_CORE_DB_POOL_SIZE", "20"))


def get_db_max_overflow() -> int:
    """Return the DB connection max_overflow from env, defaulting to 20."""
    return int(os.environ.get("IW_CORE_DB_MAX_OVERFLOW", "20"))


def get_migration_lock_timeout_secs() -> int:
    """Return the migration lock timeout in seconds (default 30).

    Used by safe_migrate.apply() to set lock_timeout on the alembic apply
    connection, bounding the maximum silent-hang duration when a self-deadlock
    or other lock contention occurs. Set to 0 to disable (not recommended).
    """
    return int(os.environ.get("IW_CORE_MIGRATION_LOCK_TIMEOUT_SECS", "30"))


@dataclass(frozen=True)
class DaemonConfig:
    """Immutable snapshot of the platform configuration."""

    # Database
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str
    db_url: str

    # Dashboard
    dashboard_host: str
    dashboard_port: int

    # Daemon
    poll_interval: int
    stall_threshold: int
    pid_file: str

    # Archive
    archive_dir: str
    archive_ttl: int

    # Logging
    log_level: str
    log_file: str

    # Code Understanding
    index_path: str = DEFAULT_INDEX_PATH

    # Project registry
    projects_toml: Path = field(default_factory=lambda: _ENV_FILE.parent / "projects.toml")

    # Database pool
    db_pool_size: int = 20
    db_max_overflow: int = 20

    # Evidence ingestion
    evidence_max_bytes: int = 5 * 1024 * 1024

    # Baseline QV gates (F-00061)
    baseline_qv_enabled: bool = True

    # Dashboard AI Assistant — managed `opencode serve` subprocess (F-00083)
    opencode_port: int = 4096
    opencode_bin: str = "opencode"

    # ── S07 / I-00105: tool-output cap + context-overflow detection ──────────
    # Per-tool-output cap: write oversized results to disk and return a preview.
    # Order of magnitude of Claude Code's 30 KB Bash cap (R-00078).
    tool_output_cap_bytes: int = 25 * 1024  # 25 KB default

    # Safety buffer subtracted from context window when computing the effective
    # input budget (window − max_output − buffer).  Default 20 K matches opencode's
    # convention (R-00078).
    effective_budget_safety_buffer_tokens: int = 20_000

    # Fraction of the effective budget at which proactive compaction fires.
    # R-00078 §"Proactive compaction at ~70–80%": fire at ~75% of effective budget.
    # Value is a float multiplier: 0.75 = 75%.
    compaction_threshold_fraction: float = 0.75

    # Context-overflow detection: whether to fail a step when overflow is detected
    # but step-done was not called.  Default True (clean failure per AC4).
    fail_on_context_overflow: bool = True

    # For runtimes that expose a compaction-threshold setting, set this env-var
    # name in the runtime-specific section below.  None means not controllable.
    # Current known: claude → BASH_MAX_OUTPUT_LENGTH (Claude Code Bash cap, not the
    # compaction threshold itself — opencode is the one that exposes
    # CONTEXT_WINDOW − OUTPUT − BUFFER as a calibrated threshold).
    runtime_compaction_env_var: str | None = None  # None = not controllable for all runtimes


def _parse_truthy(value: str) -> bool:
    """Return True for truthy env-var values, False otherwise."""
    return value.lower() in {"1", "true", "yes", "on"}


def load_config() -> DaemonConfig:
    """Load and validate the full platform configuration.

    Raises RuntimeError if any required environment variable is missing.
    """
    db_host = _require("IW_CORE_DB_HOST")
    db_port = _require("IW_CORE_DB_PORT")
    db_name = _require("IW_CORE_DB_NAME")
    db_user = _require("IW_CORE_DB_USER")
    db_password = _require("IW_CORE_DB_PASSWORD")

    return DaemonConfig(
        db_host=db_host,
        db_port=int(db_port),
        db_name=db_name,
        db_user=db_user,
        db_password=db_password,
        db_url=f"postgresql+psycopg://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}",
        dashboard_host=_require("IW_CORE_DASHBOARD_HOST"),
        dashboard_port=int(_require("IW_CORE_DASHBOARD_PORT")),
        poll_interval=int(_require("IW_CORE_POLL_INTERVAL")),
        stall_threshold=int(_require("IW_CORE_STALL_THRESHOLD")),
        pid_file=_require("IW_CORE_PID_FILE"),
        archive_dir=_require("IW_CORE_ARCHIVE_DIR"),
        archive_ttl=int(_require("IW_CORE_ARCHIVE_TTL")),
        log_level=_require("IW_CORE_LOG_LEVEL"),
        log_file=_require("IW_CORE_LOG_FILE"),
        index_path=str(Path(os.environ.get("IW_CORE_INDEX_PATH", DEFAULT_INDEX_PATH)).expanduser()),
        projects_toml=Path(
            os.environ.get("IW_CORE_PROJECTS_TOML", str(_ENV_FILE.parent / "projects.toml"))
        ),
        db_pool_size=int(os.environ.get("IW_CORE_DB_POOL_SIZE", "20")),
        db_max_overflow=int(os.environ.get("IW_CORE_DB_MAX_OVERFLOW", "20")),
        baseline_qv_enabled=_parse_truthy(os.environ.get("IW_CORE_BASELINE_QV", "true")),
        evidence_max_bytes=int(os.environ.get("IW_CORE_EVIDENCE_MAX_BYTES", str(5 * 1024 * 1024))),
        opencode_port=int(os.environ.get("IW_CORE_OPENCODE_PORT", "4096")),
        opencode_bin=os.environ.get("IW_CORE_OPENCODE_BIN", "opencode"),
        # S07 / I-00105: tool-output cap + context-overflow detection
        tool_output_cap_bytes=int(os.environ.get("IW_CORE_TOOL_OUTPUT_CAP_BYTES", str(25 * 1024))),
        effective_budget_safety_buffer_tokens=int(
            os.environ.get("IW_CORE_EFFECTIVE_BUDGET_SAFETY_BUFFER_TOKENS", "20000")
        ),
        compaction_threshold_fraction=float(
            os.environ.get("IW_CORE_COMPACTION_THRESHOLD_FRACTION", "0.75")
        ),
        fail_on_context_overflow=_parse_truthy(
            os.environ.get("IW_CORE_FAIL_ON_CONTEXT_OVERFLOW", "true")
        ),
        runtime_compaction_env_var=os.environ.get("IW_CORE_RUNTIME_COMPACTION_ENV_VAR"),
    )
