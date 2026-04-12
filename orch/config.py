"""Platform configuration loaded from environment variables.

Loads `.env` from the repo root via python-dotenv.
Fails fast with a clear error if any required variable is missing.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the repo root (two levels up from this file: orch/config.py -> orch/ -> repo root)
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
CORE_ROOT: Path = _ENV_FILE.parent
load_dotenv(_ENV_FILE)


def _require(name: str) -> str:
    """Return the value of a required env var, raising RuntimeError if missing."""
    value = os.environ.get(name)
    if value is None:
        raise RuntimeError(
            f"Required environment variable '{name}' is not set. "
            f"Check your .env file (expected at {_ENV_FILE})."
        )
    return value


def get_db_url() -> str:
    """Build the SQLAlchemy database URL from individual env vars."""
    host = _require("IW_CORE_DB_HOST")
    port = _require("IW_CORE_DB_PORT")
    name = _require("IW_CORE_DB_NAME")
    user = _require("IW_CORE_DB_USER")
    password = _require("IW_CORE_DB_PASSWORD")
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{name}"


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

    # Project registry
    projects_toml: Path = field(default_factory=lambda: _ENV_FILE.parent / "projects.toml")


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
        projects_toml=Path(
            os.environ.get("IW_CORE_PROJECTS_TOML", str(_ENV_FILE.parent / "projects.toml"))
        ),
    )
