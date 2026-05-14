"""worktree_compose — per-worktree docker-compose lifecycle.

Daemon-managed compose stacks for parallel work-item isolation. Projects
opt in by adding ``ai-dev/iw-config/{worktree-compose.template.yml,
worktree-env.toml, worktree-seed.sh}`` to their repo. Projects without
iw-config use legacy mode (no stack created).

This module is the single canonical source of truth for docker compose
lifecycle commands in the iw-ai-core codebase (alongside the pre-existing
``browser_env.py``). All docker state-changing invocations (``up``, ``down``,
``port``, ``ps``, ``container prune``, ``volume prune``) live here and here only.

Lifecycle:

1. ``up()`` → render_compose → docker compose up → discover_ports →
   rewrite_env → run_seed → DaemonEvent(phase='up')
2. ``down()`` → docker compose down → DaemonEvent(phase='down')
3. ``is_alive()`` → docker compose ps (read-only, no side effects)

Reference: ``docs/IW_AI_Core_Worktree_Isolation.md`` (created in S13).
Precedent: ``orch/daemon/browser_env.py``.

ivar IW_CORE_PER_WORKTREE_DB:
    Set by the daemon in the agent subprocess env when a per-worktree
    compose stack exists. Used by ``safe_migrate`` to allow alembic
    operations against the per-worktree DB without weakening protection
    of the global orch DB on port 5433.
"""

from __future__ import annotations

import logging
import os
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jinja2
from sqlalchemy.orm import Session, sessionmaker

from orch.config import get_db_url
from orch.db.models import DaemonEvent
from orch.db.session import safe_create_engine

__all__ = [
    "WorktreeStackConfig",
    "UpResult",
    "has_iw_config",
    "load_config",
    "assert_gitignore_safe",
    "render_compose",
    "up",
    "down",
    "is_alive",
    "discover_ports",
    "rewrite_env",
    "run_seed",
]

logger = logging.getLogger(__name__)

COMPOSE_PROJECT_PREFIX = "iwcore"
COMPOSE_UP_TIMEOUT_SEC = 300
COMPOSE_DOWN_TIMEOUT_SEC = 120
SEED_STDERR_TAIL_BYTES = 16 * 1024


def _read_db_credentials_from_toml(env_toml_path: Path) -> dict[str, str]:
    """Read per-worktree DB credentials from worktree-env.toml.

    Returns a dict mapping env-var names to their string values for the five
    IW_CORE_DB_* vars (HOST, PORT, NAME, USER, PASSWORD). PORT is intentionally
    excluded — it is discovered at runtime via ``discover_ports`` and written
    into the .env by ``rewrite_env``. The caller (batch_manager._launch_step)
    assembles the full connection info from worktree_info which carries both
    the discovered port and these credentials.

    If the toml file is absent or the [env_overrides] section is empty,
    returns an empty dict — never raises.
    """
    if not env_toml_path.is_file():
        return {}
    try:
        with env_toml_path.open("rb") as f:
            toml_data = tomllib.load(f)
    except Exception:
        return {}
    overrides = toml_data.get("env_overrides", {})
    creds = {}
    for key in ("IW_CORE_DB_HOST", "IW_CORE_DB_NAME", "IW_CORE_DB_USER", "IW_CORE_DB_PASSWORD"):
        val = overrides.get(key)
        if val:
            creds[key] = val
    return creds


@dataclass(frozen=True)
class WorktreeStackConfig:
    batch_item_id: str
    project_id: str
    worktree_path: Path
    template_path: Path
    env_toml_path: Path
    seed_script_path: Path | None
    rendered_compose_path: Path
    compose_project_name: str


@dataclass(frozen=True)
class UpResult:
    success: bool
    rendered_compose_path: Path | None
    discovered_ports: dict[str, int]
    discovered_db_credentials: dict[str, str]
    error_message: str | None
    seed_stderr_tail: str | None


def _compose_project_name(batch_item_id: str) -> str:
    return f"{COMPOSE_PROJECT_PREFIX}-{batch_item_id.lower().replace('_', '-')}"


def _iw_config_dir(worktree_path: Path) -> Path:
    return worktree_path / "ai-dev" / "iw-config"


def has_iw_config(worktree_path: Path) -> bool:
    """Return True if ``<worktree>/ai-dev/iw-config/worktree-compose.template.yml`` exists."""
    return (_iw_config_dir(worktree_path) / "worktree-compose.template.yml").is_file()


def load_config(
    batch_item_id: str,
    project_id: str,
    worktree_path: Path,
) -> WorktreeStackConfig:
    """Build a WorktreeStackConfig for the given worktree.

    Raises FileNotFoundError if ``ai-dev/iw-config/worktree-compose.template.yml``
    is absent (caller should treat this as legacy/no-op).
    """
    cfg_dir = _iw_config_dir(worktree_path)
    template_path = cfg_dir / "worktree-compose.template.yml"
    env_toml_path = cfg_dir / "worktree-env.toml"

    if not template_path.is_file():
        raise FileNotFoundError(f"worktree-compose.template.yml not found at {template_path}")

    seed_script_path: Path | None = cfg_dir / "worktree-seed.sh"
    if seed_script_path is not None and not seed_script_path.is_file():
        seed_script_path = None
    elif seed_script_path is not None and not os.access(seed_script_path, os.X_OK):
        logger.warning(
            "worktree-seed.sh at %s is not executable; seed will be skipped",
            seed_script_path,
        )
        seed_script_path = None

    iw_dir = worktree_path / ".iw"
    iw_dir.mkdir(exist_ok=True)

    rendered_name = f"docker-compose-{batch_item_id}.yml"
    rendered_compose_path = iw_dir / rendered_name

    return WorktreeStackConfig(
        batch_item_id=batch_item_id,
        project_id=project_id,
        worktree_path=worktree_path,
        template_path=template_path,
        env_toml_path=env_toml_path,
        seed_script_path=(
            seed_script_path if seed_script_path and seed_script_path.is_file() else None
        ),
        rendered_compose_path=rendered_compose_path,
        compose_project_name=_compose_project_name(batch_item_id),
    )


def assert_gitignore_safe(project_repo_root: Path) -> None:
    """Raise ValueError if .env or .iw/ are not both present in .gitignore.

    Both entries are required before the daemon will launch a per-worktree
    compose stack to prevent secrets from being accidentally committed.
    """
    gitignore_path = project_repo_root / ".gitignore"
    if not gitignore_path.is_file():
        raise ValueError(f"refusing to launch: .gitignore not found in {project_repo_root}")

    content = gitignore_path.read_text()
    present = set()
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        present.add(line)

    missing = []
    for entry in (".env", ".iw/"):
        if entry not in present:
            missing.append(entry)

    if missing:
        raise ValueError(
            f"refusing to launch: {', '.join(missing)} must be in .gitignore "
            f"for project {project_repo_root.name}"
        )


def render_compose(cfg: WorktreeStackConfig) -> Path:
    """Jinja2-render ``cfg.template_path`` and write to ``cfg.rendered_compose_path``.

    Template variables available: ``batch_item_id``, ``worktree_path``,
    ``project_name`` (the compose project name), ``compose_project_name``.
    Uses ``StrictUndefined`` so missing variables raise immediately.
    """
    env = jinja2.Environment(  # nosec B701
        autoescape=jinja2.select_autoescape(),  # nosec B701  YAML output, not HTML
        undefined=jinja2.StrictUndefined,
    )

    template_content = cfg.template_path.read_text()
    template = env.from_string(template_content)

    rendered = template.render(
        batch_item_id=cfg.batch_item_id,
        worktree_path=str(cfg.worktree_path),
        project_name=cfg.project_id,
        compose_project_name=cfg.compose_project_name,
        host_uid=os.getuid(),
        host_gid=os.getgid(),
        host_home=str(Path.home()),
    )

    cfg.rendered_compose_path.write_text(rendered)
    logger.info(
        "rendered compose template for %s → %s",
        cfg.batch_item_id,
        cfg.rendered_compose_path,
    )

    return cfg.rendered_compose_path


def _emit_daemon_event(
    event_type: str,
    metadata: dict[str, Any],
    message: str | None = None,
    db: Session | None = None,
    project_id: str | None = None,
) -> None:
    """Write a DaemonEvent via a fresh short-lived session.

    Args:
        event_type: The type of daemon event (e.g. 'up', 'down').
        metadata: Event metadata dictionary.
        message: Optional human-readable message.
        db: Optional session to use. If not provided, creates its own connection
            to the orch DB (suitable for daemon/CLI context).
        project_id: Optional project ID so the event appears in per-project
            event feeds. Defaults to None for back-compat (global events).
    """
    _owns_session = False
    try:
        if db is None:
            db_url = get_db_url()
            engine = safe_create_engine(db_url, pool_pre_ping=True)
            session_factory = sessionmaker(bind=engine)
            db = session_factory()
            _owns_session = True
        event = DaemonEvent(
            project_id=project_id,
            event_type=event_type,
            entity_id=None,
            entity_type=None,
            message=message,
            event_metadata=metadata,
        )
        db.add(event)
        db.commit()
    except Exception as exc:
        logger.warning("[worktree_compose] Failed to write daemon event: %s", exc)
        if db is not None:
            db.rollback()
    finally:
        if _owns_session and db is not None:
            db.close()


def discover_ports(cfg: WorktreeStackConfig) -> dict[str, int]:
    """Query docker compose for each [port_to_env] entry and return {env_var: port}.

    Parses ``docker compose -p <project> -f <compose> port <service> <container_port>``
    output of the form ``0.0.0.0:34567`` or ``[::]:34567``.
    """
    discovered: dict[str, int] = {}

    if not cfg.env_toml_path.is_file():
        return discovered

    with cfg.env_toml_path.open("rb") as f:
        env_toml = tomllib.load(f)

    port_map: dict[str, str] = env_toml.get("port_to_env", {})
    if not port_map:
        return discovered

    for service_port, env_var in port_map.items():
        if ":" not in service_port:
            logger.warning(
                "port_to_env entry %r skipped (expected 'service:container_port' format)",
                service_port,
            )
            continue

        service, container_port = service_port.split(":", 1)
        try:
            result = subprocess.run(  # noqa: S603,S607
                [  # noqa: S603,S607
                    "docker",
                    "compose",
                    "-p",
                    cfg.compose_project_name,
                    "-f",
                    str(cfg.rendered_compose_path),
                    "port",
                    service,
                    container_port,
                ],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            if result.returncode != 0:
                logger.warning(
                    "port discovery for %s/%s failed (exit %d): %s",
                    cfg.batch_item_id,
                    service,
                    result.returncode,
                    result.stderr.strip(),
                )
                continue

            line = result.stdout.strip()
            if not line:
                logger.warning(
                    "port discovery for %s/%s returned empty output",
                    cfg.batch_item_id,
                    service,
                )
                continue

            host_port_str = line.rsplit(":", 1)[-1]
            discovered[env_var] = int(host_port_str)

        except subprocess.TimeoutExpired:
            logger.warning(
                "port discovery timed out for %s/%s",
                cfg.batch_item_id,
                service,
            )
        except ValueError:
            logger.warning(
                "could not parse port from %r for %s/%s",
                line,
                cfg.batch_item_id,
                service,
            )

    logger.info("discovered ports for %s: %s", cfg.batch_item_id, discovered)
    return discovered


def _unquote_env_value(value: str) -> str:
    """Strip a single matching pair of surrounding single or double quotes.

    The worktree's ``.env`` is generated by ``executor/worktree_setup.sh`` which
    wraps every value in single quotes. ``bash source`` understands those, but
    line-by-line parsers (``rewrite_env``, ``run_seed``) and downstream tools
    that read the raw file (e.g. ``docker exec -e VAR=$VAR``) don't — they
    inherit the literal quotes. Always normalise.
    """
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def rewrite_env(
    cfg: WorktreeStackConfig,
    discovered_ports: dict[str, int],
) -> None:
    """Rewrite the worktree's ``.env`` in-place with discovered ports and env overrides.

    1. Read existing .env (already populated by executor/worktree_setup.sh).
    2. Apply [env_overrides] from worktree-env.toml (literal replacements).
    3. Set each discovered port env var (from discover_ports).
    4. Preserve [env_passthrough] keep-list verbatim.
    5. Write back to ``<worktree>/.env``.
    """
    env_path = cfg.worktree_path / ".env"
    if not env_path.is_file():
        logger.warning(
            "worktree .env not found at %s; skipping env rewrite",
            env_path,
        )
        return

    lines = env_path.read_text().splitlines()

    overrides: dict[str, str] = {}
    passthrough_keys: set[str] = set()

    if cfg.env_toml_path.is_file():
        with cfg.env_toml_path.open("rb") as f:
            env_toml = tomllib.load(f)

        overrides = env_toml.get("env_overrides", {})
        passthrough_raw = env_toml.get("env_passthrough", {})
        raw_keep = passthrough_raw.get("keep", [])
        for pattern in raw_keep:
            passthrough_keys.add(pattern)

    env_vars: dict[str, str] = {}
    passthrough_lines: dict[str, str] = {}

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            key = key.strip()
            value = _unquote_env_value(value.strip())

            if passthrough_keys:
                import fnmatch

                matched = any(fnmatch.fnmatch(key, p) for p in passthrough_keys)
                if matched:
                    # Re-emit unquoted so docker/bash-via-env consumers see the
                    # literal value, not the quoted form.
                    passthrough_lines[key] = f"{key}={value}"
                    continue

            env_vars[key] = value

    for key, val in overrides.items():
        env_vars[key] = val

    for key, port in discovered_ports.items():
        env_vars[key] = str(int(port))

    new_lines: list[str] = []
    new_lines.extend(f"{k}={v}" for k, v in sorted(env_vars.items()))
    new_lines.extend(sorted(passthrough_lines.values()))

    env_path.write_text("\n".join(new_lines) + "\n")
    logger.info(
        "rewrote .env for %s with %d vars + %d passthrough",
        cfg.batch_item_id,
        len(env_vars),
        len(passthrough_lines),
    )


# Match only references that have NO default/error substitution.
# `${VAR}` and `$VAR` are required. `${VAR:-default}`, `${VAR-default}`,
# `${VAR:?msg}`, `${VAR?msg}`, `${VAR:=default}` etc. are author-handled.
_SEED_VAR_PATTERN = __import__("re").compile(
    r"\$\{([A-Z_][A-Z0-9_]*)\}|\$([A-Z_][A-Z0-9_]*)(?![A-Z0-9_])"
)
# Matches `FOO=...`, `FOO="..."`, `export FOO=...`, AND additional assignments
# on the same logical line (`export A=1 B=2 C=3`). Bash accepts multiple
# NAME=VALUE pairs after `export`/`local`/`readonly`/`declare`, so we match
# any `WORD=` token that is either at start-of-line (after an optional
# assignment-prefix keyword) or preceded by whitespace. Over-matching is
# safe here: extra entries in `locally_assigned` only suppress a false
# positive in the missing-var check; bash itself surfaces real undefined
# refs at runtime via `set -u`.
_SEED_ASSIGN_PATTERN = __import__("re").compile(
    r"(?:^\s*(?:export\s+|local\s+|readonly\s+|declare\s+(?:-[a-zA-Z]+\s+)?)?|\s+)"
    r"([A-Z_][A-Z0-9_]*)\s*=",
    __import__("re").MULTILINE,
)
# Bash builtins / shell vars that may legitimately appear in a seed script and
# don't need to be set by the operator.
_SEED_VAR_IGNORE = frozenset(
    {"PATH", "HOME", "USER", "PWD", "SHELL", "LANG", "LC_ALL", "TMPDIR", "IFS"}
)


def _check_seed_env(seed_script_path: Path, seed_env: dict[str, str]) -> tuple[bool, str | None]:
    """Pre-flight check: every ``${VAR}`` referenced by the seed script must be set.

    Variables assigned within the script (``FOO=...``) are excluded — they are
    locals, not env-var dependencies. Returns (True, None) if all remaining
    references are bound. Returns (False, message) with a precise, actionable
    error otherwise — better than a cryptic bash ``unbound variable``.
    """
    try:
        source = seed_script_path.read_text()
    except OSError:
        return True, None  # If we can't read, defer to bash to surface the error.

    locally_assigned = {m.group(1) for m in _SEED_ASSIGN_PATTERN.finditer(source)}

    referenced: set[str] = set()
    for m in _SEED_VAR_PATTERN.finditer(source):
        name = m.group(1) or m.group(2)
        if not name or name in _SEED_VAR_IGNORE or name in locally_assigned:
            continue
        referenced.add(name)

    missing = sorted(name for name in referenced if name not in seed_env)
    if not missing:
        return True, None

    msg = (
        f"seed script {seed_script_path} references unset env var(s): "
        f"{', '.join(missing)}. Add them to the daemon's .env "
        f"(see .env.example). The worktree-env.toml [env_passthrough] keep-list "
        f"only forwards vars that are already set in the daemon's environment."
    )
    return False, msg


def run_seed(cfg: WorktreeStackConfig) -> tuple[bool, str | None]:
    """Execute the worktree-seed.sh script if present and executable.

    Runs with the worktree's ``.env`` loaded into the subprocess env.
    Returns (True, None) if no seed script or script is non-executable (no-op).
    Returns (True, None) on zero exit.
    Returns (False, stderr_tail) on non-zero exit.
    """
    if cfg.seed_script_path is None:
        return True, None

    seed_env = os.environ.copy()
    env_path = cfg.worktree_path / ".env"
    if env_path.is_file():
        env_vars = {}
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            env_vars[key.strip()] = _unquote_env_value(value.strip())
        seed_env = {**seed_env, **env_vars}

    # Inject identifiers the seed needs to address the per-worktree compose
    # stack via docker exec (no host pg_dump/psql install required).
    seed_env["IW_CORE_BATCH_ITEM_ID"] = cfg.batch_item_id
    seed_env["IW_CORE_COMPOSE_PROJECT_NAME"] = cfg.compose_project_name

    ok, err = _check_seed_env(cfg.seed_script_path, seed_env)
    if not ok:
        logger.error("seed pre-flight failed for %s: %s", cfg.batch_item_id, err)
        return False, err

    try:
        result = subprocess.run(  # noqa: S603  from own config, not untrusted
            [str(cfg.seed_script_path)],
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
            env=seed_env,
            cwd=str(cfg.worktree_path),
        )
    except subprocess.TimeoutExpired:
        logger.error(
            "seed script timed out for %s after 600s",
            cfg.batch_item_id,
        )
        return False, "seed script timed out after 600s"
    except OSError as exc:
        logger.error(
            "seed script failed to start for %s: %s",
            cfg.batch_item_id,
            exc,
        )
        return False, str(exc)

    if result.returncode == 0:
        logger.info("seed script succeeded for %s", cfg.batch_item_id)
        return True, None

    stderr_tail = result.stderr[-SEED_STDERR_TAIL_BYTES:]
    logger.warning(
        "seed script failed for %s (exit %d): %s",
        cfg.batch_item_id,
        result.returncode,
        stderr_tail[:500],
    )
    return False, stderr_tail


def _compose_down(
    compose_project_name: str,
    compose_path: Path | None,
    batch_item_id: str,
) -> None:
    """Run docker compose down with belt-and-suspenders prune."""
    compose_args = [
        "docker",
        "compose",
        "-p",
        compose_project_name,
    ]
    if compose_path is not None:
        compose_args.extend(["-f", str(compose_path)])
    compose_args.extend(["down", "-v", "--remove-orphans"])

    try:
        subprocess.run(  # noqa: S603, S607  docker is always in PATH
            compose_args,
            capture_output=True,
            text=True,
            timeout=COMPOSE_DOWN_TIMEOUT_SEC,
            check=False,
        )
    except subprocess.TimeoutExpired:
        logger.warning(
            "compose down timed out for %s",
            batch_item_id,
        )

    for prune_cmd in [  # noqa: S603, S607  docker is always in PATH
        [
            "docker",
            "container",
            "prune",
            "--filter",
            f"label=iwcore.batch_item={batch_item_id}",
        ],
        [
            "docker",
            "volume",
            "prune",
            "--filter",
            f"label=iwcore.batch_item={batch_item_id}",
        ],
    ]:
        try:
            subprocess.run(  # noqa: S603, S607  docker is always in PATH
                prune_cmd,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
        except Exception as exc:
            logger.debug(
                "prune failed for %s (non-fatal): %s",
                batch_item_id,
                exc,
            )


def up(cfg: WorktreeStackConfig) -> UpResult:
    """Bring up the per-worktree compose stack.

    Steps:
    1. assert_gitignore_safe (raises on failure)
    2. render_compose
    3. docker compose up -d
    4. discover_ports
    5. rewrite_env
    6. run_seed (on failure: down + return failure)
    7. DaemonEvent(phase='up')
    """
    try:
        project_root = cfg.worktree_path
        while project_root.parent != project_root:
            if (project_root / ".git").is_dir():
                break
            project_root = project_root.parent
        assert_gitignore_safe(project_root)
    except ValueError as exc:
        _emit_daemon_event(
            "worktree_compose",
            {
                "phase": "up",
                "batch_item_id": cfg.batch_item_id,
                "success": False,
                "error": str(exc),
            },
            message=f"worktree_compose up refused: {exc}",
            project_id=cfg.project_id,
        )
        return UpResult(
            success=False,
            rendered_compose_path=None,
            discovered_ports={},
            discovered_db_credentials={},
            error_message=str(exc),
            seed_stderr_tail=None,
        )

    try:
        compose_path = render_compose(cfg)
    except Exception as exc:
        logger.error("render_compose failed for %s: %s", cfg.batch_item_id, exc)
        _emit_daemon_event(
            "worktree_compose",
            {
                "phase": "up",
                "batch_item_id": cfg.batch_item_id,
                "success": False,
                "error": f"render_compose failed: {exc}",
            },
            message=f"worktree_compose render failed: {exc}",
            project_id=cfg.project_id,
        )
        return UpResult(
            success=False,
            rendered_compose_path=None,
            discovered_ports={},
            discovered_db_credentials={},
            error_message=str(exc),
            seed_stderr_tail=None,
        )

    try:
        result = subprocess.run(  # noqa: S603,S607
            [  # noqa: S603,S607
                "docker",  # noqa: S607
                "compose",
                "-p",
                cfg.compose_project_name,
                "-f",
                str(compose_path),
                "up",
                "-d",
            ],
            capture_output=True,
            text=True,
            timeout=COMPOSE_UP_TIMEOUT_SEC,
            check=False,
        )
        if result.returncode != 0:
            err = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
            logger.error("compose up failed for %s: %s", cfg.batch_item_id, err)
            _compose_down(cfg.compose_project_name, compose_path, cfg.batch_item_id)
            _emit_daemon_event(
                "worktree_compose",
                {
                    "phase": "up",
                    "batch_item_id": cfg.batch_item_id,
                    "success": False,
                    "error": err,
                },
                message=f"worktree_compose up failed: {err}",
                project_id=cfg.project_id,
            )
            return UpResult(
                success=False,
                rendered_compose_path=compose_path,
                discovered_ports={},
                discovered_db_credentials={},
                error_message=err,
                seed_stderr_tail=None,
            )
    except subprocess.TimeoutExpired:
        err = "compose up timed out"
        logger.error("%s for %s", err, cfg.batch_item_id)
        _compose_down(cfg.compose_project_name, compose_path, cfg.batch_item_id)
        _emit_daemon_event(
            "worktree_compose",
            {
                "phase": "up",
                "batch_item_id": cfg.batch_item_id,
                "success": False,
                "error": err,
            },
            message=f"worktree_compose up timed out: {err}",
            project_id=cfg.project_id,
        )
        return UpResult(
            success=False,
            rendered_compose_path=compose_path,
            discovered_ports={},
            discovered_db_credentials={},
            error_message=err,
            seed_stderr_tail=None,
        )

    discovered_ports = discover_ports(cfg)
    rewrite_env(cfg, discovered_ports)

    seed_ok, seed_stderr = run_seed(cfg)
    if not seed_ok:
        logger.warning(
            "seed failed for %s; tearing down stack",
            cfg.batch_item_id,
        )
        _compose_down(cfg.compose_project_name, compose_path, cfg.batch_item_id)
        _emit_daemon_event(
            "worktree_compose",
            {
                "phase": "seed",
                "batch_item_id": cfg.batch_item_id,
                "success": False,
                "seed_stderr_tail": seed_stderr,
            },
            message=f"worktree_compose seed failed: {seed_stderr}",
            project_id=cfg.project_id,
        )
        return UpResult(
            success=False,
            rendered_compose_path=compose_path,
            discovered_ports=discovered_ports,
            discovered_db_credentials={},
            error_message="seed failed",
            seed_stderr_tail=seed_stderr,
        )

    _emit_daemon_event(
        "worktree_compose",
        {
            "phase": "up",
            "batch_item_id": cfg.batch_item_id,
            "success": True,
            "ports": discovered_ports,
        },
        message=f"worktree_compose up succeeded for {cfg.batch_item_id}",
        project_id=cfg.project_id,
    )

    return UpResult(
        success=True,
        rendered_compose_path=compose_path,
        discovered_ports=discovered_ports,
        discovered_db_credentials=_read_db_credentials_from_toml(cfg.env_toml_path),
        error_message=None,
        seed_stderr_tail=None,
    )


def down(
    batch_item_id: str,
    compose_path: Path | None,
    project_id: str | None = None,
) -> bool:
    """Tear down the per-worktree compose stack.

    Runs ``docker compose down -v --remove-orphans`` followed by belt-and-suspenders
    container and volume prune by label. Idempotent — returns True even if
    nothing was running.

    Emits DaemonEvent(phase='down').

    Args:
        batch_item_id: The batch item ID whose stack should be torn down.
        compose_path: Optional path to the rendered compose file (for -f flag).
        project_id: Optional project ID so the event appears in per-project
            event feeds. Defaults to None for back-compat (global events).
    """
    compose_project_name = _compose_project_name(batch_item_id)

    try:
        compose_args: list[str | Path] = [  # noqa: S607  docker is always in PATH
            "docker",
            "compose",
            "-p",
            compose_project_name,
        ]
        if compose_path is not None:
            compose_args.extend(["-f", str(compose_path)])
        compose_args.extend(["down", "-v", "--remove-orphans"])

        subprocess.run(  # noqa: S603, S607  docker is always in PATH
            compose_args,
            capture_output=True,
            text=True,
            timeout=COMPOSE_DOWN_TIMEOUT_SEC,
            check=False,
        )
    except subprocess.TimeoutExpired:
        logger.warning(
            "compose down timed out for %s",
            batch_item_id,
        )

    for prune_cmd in [  # noqa: S603, S607  docker is always in PATH
        [
            "docker",
            "container",
            "prune",
            "--filter",
            f"label=iwcore.batch_item={batch_item_id}",
        ],
        [
            "docker",
            "volume",
            "prune",
            "--filter",
            f"label=iwcore.batch_item={batch_item_id}",
        ],
    ]:
        try:
            subprocess.run(  # noqa: S603, S607  docker is always in PATH
                prune_cmd,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
        except Exception as exc:
            logger.debug(
                "prune failed for %s (non-fatal): %s",
                batch_item_id,
                exc,
            )

    _emit_daemon_event(
        "worktree_compose",
        {
            "phase": "down",
            "batch_item_id": batch_item_id,
            "success": True,
        },
        message=f"worktree_compose down completed for {batch_item_id}",
        project_id=project_id,
    )

    logger.info("compose stack torn down for %s", batch_item_id)
    return True


def is_alive(batch_item_id: str) -> bool:
    """Return True if the compose stack for batch_item_id has running containers.

    Runs ``docker compose -p iwcore-<id> ps --quiet``.
    """
    compose_project_name = _compose_project_name(batch_item_id)
    try:
        result = subprocess.run(  # noqa: S603,S607
            [  # noqa: S603,S607
                "docker",  # noqa: S607
                "compose",
                "-p",
                compose_project_name,
                "ps",
                "--quiet",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        return result.returncode == 0 and bool(result.stdout.strip())
    except Exception:
        return False
