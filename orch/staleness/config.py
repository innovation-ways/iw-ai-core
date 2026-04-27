"""orch.staleness.config — Config schema and parser for staleness detection.

Parses the ``[[projects.<id>.services]]`` and ``[projects.<id>.alembic]``
blocks out of the raw project config dict (from projects.toml).

No I/O here — pure data validation. All shell-outs live in detection.py,
git_lookup.py, and alembic_check.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# ServiceDetect — discriminated union over detection strategies
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ServiceDetect:
    """Detection strategy for a running service.

    Attributes:
        type: One of "port", "pidfile", "docker", "pgrep".
        port: (port only) TCP port number to check with ``ss -ltnp``.
        path: (pidfile only) Path to the PID file, relative to repo_root.
        container: (docker only) Docker container name.
        pattern: (pgrep only) Regex pattern matched against process cmdline.
    """

    type: str
    port: int | None = None
    path: str | None = None
    container: str | None = None
    pattern: str | None = None

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> ServiceDetect:
        """Parse and validate a detect sub-table dict.

        Raises:
            ValueError: If type is unknown or a required type-specific field
                is missing.
        """
        detect_type = raw.get("type")
        if not detect_type:
            raise ValueError("detect block missing required 'type' field")

        if detect_type == "port":
            port = raw.get("port")
            if port is None:
                raise ValueError("detect.type='port' requires a 'port' field (integer)")
            return cls(type="port", port=int(port))

        if detect_type == "pidfile":
            path = raw.get("path")
            if not path:
                raise ValueError("detect.type='pidfile' requires a 'path' field")
            return cls(type="pidfile", path=str(path))

        if detect_type == "docker":
            container = raw.get("container")
            if not container:
                raise ValueError("detect.type='docker' requires a 'container' field")
            return cls(type="docker", container=str(container))

        if detect_type == "pgrep":
            pattern = raw.get("pattern")
            if not pattern:
                raise ValueError("detect.type='pgrep' requires a 'pattern' field")
            return cls(type="pgrep", pattern=str(pattern))

        raise ValueError(
            f"Unknown detect type {detect_type!r}. "
            f"Valid types: 'port', 'pidfile', 'docker', 'pgrep'."
        )


# ---------------------------------------------------------------------------
# ServiceConfig — one declared service entry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ServiceConfig:
    """Configuration for a single monitored service.

    Attributes:
        name: Unique name within the project (used in API paths).
        detect: Detection strategy.
        watch_paths: Gitignore-style paths that, if changed, mark the service stale.
        ignore_paths: Gitignore-style paths excluded from the staleness diff.
        restart_command: Shell command to restart the service (optional).
        start_command: Shell command to start the service (optional).
        stop_command: Shell command to stop the service (optional).
        hot_reload: If True, skip staleness warning (service self-reloads on change).
    """

    name: str
    detect: ServiceDetect
    watch_paths: list[str]
    ignore_paths: list[str]
    restart_command: str | None = None
    start_command: str | None = None
    stop_command: str | None = None
    hot_reload: bool = False

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> ServiceConfig:
        """Parse and validate a service config dict.

        Raises:
            ValueError: If required fields are missing or detect is invalid.
        """
        name = raw.get("name")
        if not name:
            raise ValueError("service config missing required 'name' field")

        raw_detect = raw.get("detect")
        if raw_detect is None:
            raise ValueError(f"service {name!r} missing required 'detect' block")

        detect = ServiceDetect.from_dict(raw_detect)

        watch_paths = raw.get("watch_paths")
        if watch_paths is None:
            raise ValueError(f"service {name!r} missing required 'watch_paths' field")

        ignore_paths: list[str] = raw.get("ignore_paths", [])

        return cls(
            name=str(name),
            detect=detect,
            watch_paths=list(watch_paths),
            ignore_paths=list(ignore_paths),
            restart_command=raw.get("restart_command") or None,
            start_command=raw.get("start_command") or None,
            stop_command=raw.get("stop_command") or None,
            hot_reload=bool(raw.get("hot_reload", False)),
        )


# ---------------------------------------------------------------------------
# AlembicConfig — alembic migration head check config
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AlembicConfig:
    """Configuration for Alembic migration head checking.

    Attributes:
        config: Path to alembic.ini, relative to repo_root.
        db_url_env: Name of an environment variable whose value is the DB URL.
            When None, the alembic subprocess inherits the parent environment
            unchanged (suitable for projects whose alembic env.py already
            resolves the URL from app config, e.g. iw-ai-core itself reads
            IW_CORE_DB_HOST/PORT/NAME/USER/PASSWORD via orch.config.get_db_url()).
            When set, the named env var's value is injected as IW_ALEMBIC_DB_URL
            in the subprocess environment.
    """

    config: str
    db_url_env: str | None = None

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> AlembicConfig:
        """Parse and validate an alembic config dict.

        Raises:
            ValueError: If required 'config' field is missing.
        """
        config = raw.get("config")
        if not config:
            raise ValueError("alembic config missing required 'config' field (path to alembic.ini)")
        return cls(
            config=str(config),
            db_url_env=raw.get("db_url_env") or None,
        )


# ---------------------------------------------------------------------------
# ProjectStalenessConfig — top-level container
# ---------------------------------------------------------------------------


@dataclass
class ProjectStalenessConfig:
    """Staleness configuration extracted from a project's config dict.

    Attributes:
        services: List of declared services to monitor (empty = opt-out).
        alembic: Alembic config for migration head checking (None = opt-out).
    """

    services: list[ServiceConfig] = field(default_factory=list)
    alembic: AlembicConfig | None = None


# ---------------------------------------------------------------------------
# parse_project_staleness — entry point
# ---------------------------------------------------------------------------


def parse_project_staleness(raw: dict[str, Any]) -> ProjectStalenessConfig:
    """Extract staleness config from a project's raw config dict.

    This function is called with the raw project entry dict from projects.toml
    (i.e. ``raw_toml["projects"][project_id]``).

    Returns an empty ProjectStalenessConfig if neither ``services`` nor
    ``alembic`` keys are present — this is the opt-out signal.

    Raises:
        ValueError: If any service or alembic block is misconfigured.
    """
    raw_services = raw.get("services")
    raw_alembic = raw.get("alembic")

    services: list[ServiceConfig] = []
    if raw_services is not None:
        for svc_raw in raw_services:
            services.append(ServiceConfig.from_dict(svc_raw))

    alembic: AlembicConfig | None = None
    if raw_alembic is not None:
        alembic = AlembicConfig.from_dict(raw_alembic)

    return ProjectStalenessConfig(services=services, alembic=alembic)
