"""FastAPI dashboard application factory for IW AI Core."""

from __future__ import annotations

import logging
import os
import uuid
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable

    from sqlalchemy.orm import Session
    from starlette.requests import Request  # noqa: TC002

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request  # noqa: TC002
from starlette.responses import Response  # noqa: TC002

from dashboard.middlewares.alembic_guard import AlembicGuardMiddleware, is_db_stale
from dashboard.routers import (
    actions,
    auto_merge_ui,
    batches,
    chat,
    code,
    code_qa,
    code_ui,
    containers,
    conversations,
    coverage,
    daemon_control,
    docs,
    docs_global,
    healthz,
    items,
    jobs_ui,
    keep_alive,
    oss,
    project_dashboard,
    project_pages,
    projects,
    quality,
    research,
    running,
    runtime_overrides,
    search,
    sse,
    staleness,
    system,
    tests,
    usage,
    worktrees,
)
from dashboard.routers import (
    help as help_router,
)
from dashboard.utils.timing import TimingMiddleware
from orch.db.alembic_guard import check_db_at_head
from orch.db.identity import verify_instance_identity
from orch.db.live_db_guard import LiveDbConnectionRefusedError
from orch.db.session import SessionLocal, engine
from orch.test_runner import mark_orphaned_runs

_HERE = Path(__file__).resolve().parent
_STATIC_DIR = _HERE / "static"
_TEMPLATES_DIR = _HERE / "templates"

logger = logging.getLogger(__name__)


def _open_middleware_session(app: FastAPI) -> tuple[Session, bool]:
    """Open a DB session for middleware use, honoring `app.dependency_overrides[get_db]`.

    Returns ``(session, owns)`` — when ``owns`` is True the caller must close
    the session; when False the override (typically a test fixture) owns the
    lifecycle.

    Why this exists: the chip middleware previously called ``SessionLocal()``
    directly. Because the test module imports ``from dashboard.app import
    create_app`` at top level, pytest collection triggers the module-level
    ``from orch.db.session import SessionLocal, engine`` BEFORE the
    session-autouse ``_arm_live_db_guard`` fixture runs — so the cached
    ``_engine`` ends up bound to whatever ``.env`` configures (production
    ``localhost:5433``). Tests that override ``get_db`` for the request layer
    then see the middleware silently reading from production, and any
    per-test ``AutoMergeProjectConfig`` overrides become invisible.
    """
    from dashboard.dependencies import get_db  # noqa: PLC0415

    override = app.dependency_overrides.get(get_db)
    if override is None:
        return SessionLocal(), True
    result = override()
    # FastAPI accepts both generator-style (yield) and plain callables as
    # dependencies. Handle both shapes so we work with any override.
    if hasattr(result, "__next__"):
        session = next(result)
        return cast("Session", session), False  # generator owns its own cleanup
    return cast("Session", result), False  # raw session — fixture owns lifecycle


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:  # noqa: ARG001
    # ------------------------------------------------------------------
    # F-00083: Start managed OpenCode subprocess BEFORE daemon startup.
    # Failure is non-fatal: runtime is set to None and the chat panel
    # renders a "runtime unavailable" banner.
    #
    # In test context (IW_CORE_TEST_CONTEXT=true) the lifespan skips
    # subprocess startup and leaves app.state unchanged so tests can
    # pre-set mock runtimes before entering the TestClient context manager.
    # ------------------------------------------------------------------
    _runtime = None
    _relay_manager = None
    _pi_runtime = None
    if os.environ.get("IW_CORE_TEST_CONTEXT") != "true":
        try:
            from orch.chat import OpencodeClient, OpencodeRuntime, PiRuntime, RelayManager
            from orch.config import CORE_ROOT, load_config

            cfg = load_config()
            _runtime = OpencodeRuntime(
                repo_root=CORE_ROOT,
                port=cfg.opencode_port,
                bin_path=cfg.opencode_bin,
            )
            await _runtime.start()
            _client = OpencodeClient(base_url=_runtime.base_url, password=_runtime.password)

            def _resolve_tab_session_id(tab_id: str) -> str | None:
                """Resolve chat tab -> OpenCode session id for RelayManager."""
                from orch.chat import tab_service  # noqa: PLC0415

                session = SessionLocal()
                try:
                    tab = tab_service.get_tab(session, tab_id)
                    if tab is None:
                        return None
                    return tab.opencode_session_id
                finally:
                    session.close()

            _relay_manager = RelayManager(_client, session_resolver=_resolve_tab_session_id)
            app.state.opencode_runtime = _runtime
            app.state.opencode_client = _client
            app.state.relay_manager = _relay_manager
            logger.info("OpenCode runtime started on port %d", cfg.opencode_port)

            # Pi runtime — per-tab subprocess pool (F-00087).
            # Resolve the pi binary: explicit IW_CORE_PI_BIN wins (parity with
            # IW_CORE_OPENCODE_BIN); production deployments install the real
            # `pi` on PATH. The per-worktree E2E container ships no /usr/local
            # /bin/pi shim, so when IW_E2E_SEED=1 (set only by
            # docker-compose.e2e.yml) and `pi` isn't on PATH, fall back to the
            # bundled stub under tests/integration/stubs/pi so S13 V3..V7 can
            # exercise the Pi pipeline end-to-end. Production behaviour stays
            # unchanged: without IW_E2E_SEED set, the default remains "pi" and
            # missing-binary correctly maps to 503 per the design doc spec.
            import shutil as _shutil  # noqa: PLC0415

            pi_binary = os.environ.get("IW_CORE_PI_BIN", "").strip() or "pi"
            if (
                pi_binary == "pi"
                and os.environ.get("IW_E2E_SEED") == "1"
                and _shutil.which("pi") is None
            ):
                _stub_path = CORE_ROOT / "tests" / "integration" / "stubs" / "pi"
                if _stub_path.is_file():
                    # Defensive: Docker COPY occasionally drops the exec bit on
                    # certain daemon/host combos; the stub is owned by the
                    # runtime user inside the container so chmod+x is safe.
                    if not os.access(str(_stub_path), os.X_OK):
                        try:
                            _stub_path.chmod(_stub_path.stat().st_mode | 0o111)
                            logger.info(
                                "Pi stub %s had no exec bit; chmod +x applied",
                                _stub_path,
                            )
                        except OSError as _chmod_exc:
                            logger.warning(
                                "Pi stub %s not executable and chmod failed: %s",
                                _stub_path,
                                _chmod_exc,
                            )
                    if os.access(str(_stub_path), os.X_OK):
                        pi_binary = str(_stub_path)
                        logger.info(
                            "Pi binary not on PATH; using bundled E2E stub at %s",
                            pi_binary,
                        )
                    else:
                        logger.warning(
                            "Pi E2E stub at %s is not executable; PiRuntime "
                            "health() will fail and Pi tab creation will 503",
                            _stub_path,
                        )
                else:
                    logger.warning(
                        "IW_E2E_SEED=1 set and `pi` missing on PATH, but the "
                        "bundled stub at %s does not exist; PiRuntime health() "
                        "will fail and Pi tab creation will 503",
                        _stub_path,
                    )

            _pi_runtime = PiRuntime(
                base_session_dir=Path.home() / ".pi" / "agent" / "sessions",
                binary=pi_binary,
            )
            app.state.pi_runtime = _pi_runtime
            logger.info("Pi runtime initialised (lazy subprocess spawn)")
        except Exception as exc:
            logger.exception("OpenCode runtime startup failed: %s", exc)
            app.state.opencode_runtime = None
            app.state.opencode_client = None
            app.state.relay_manager = None
            app.state.pi_runtime = None
    else:
        logger.debug("OpenCode runtime startup skipped in test context")

    try:
        count = mark_orphaned_runs()
        if count:
            logger.warning("Marked %d orphaned test run(s) as error on startup", count)
    except Exception as exc:
        if os.environ.get("IW_CORE_TEST_CONTEXT") == "true":
            logger.debug("mark_orphaned_runs skipped in test context: %s", exc)
        else:
            logger.warning("mark_orphaned_runs failed: %s", exc)

    session = SessionLocal()
    try:
        identity_status = verify_instance_identity(session)
        if identity_status.mode == "match":
            logger.info("Dashboard: DB identity verified (%s)", str(identity_status.actual)[:8])
        elif identity_status.mode == "bootstrap":
            logger.info(
                "Dashboard: %s",
                identity_status.message,
            )
    except Exception as exc:
        if (
            os.environ.get("IW_CORE_TEST_CONTEXT") == "true"
            or os.environ.get("IW_CORE_OPERATOR_APPLY") == "true"
        ):
            logger.warning("Dashboard: %s — continuing anyway", exc)
        else:
            logger.error("Dashboard: %s", exc)
            raise
    finally:
        session.close()

    yield

    # ------------------------------------------------------------------
    # Shutdown: reverse order — pi_runtime → relay_manager → opencode runtime
    # ------------------------------------------------------------------
    if _pi_runtime is not None:
        try:
            await _pi_runtime.close_all_clients()
        except Exception as exc:
            logger.warning("Pi runtime shutdown error: %s", exc)
    if _relay_manager is not None:
        try:
            await _relay_manager.shutdown()
        except Exception as exc:
            logger.warning("RelayManager shutdown error: %s", exc)
    if _runtime is not None:
        try:
            await _runtime.stop()
        except Exception as exc:
            logger.warning("OpenCode runtime stop error: %s", exc)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="IW AI Core Dashboard",
        description="Real-time management interface for IW AI Core orchestration platform.",
        version="0.1.0",
        lifespan=_lifespan,
        docs_url="/api-docs",
        redoc_url="/api-redoc",
    )

    # Mount static files
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    # Register timing middleware
    app.add_middleware(
        TimingMiddleware,
        engine=engine,
        slow_request_ms=int(os.environ.get("IW_CORE_SLOW_REQUEST_MS", "500")),
    )

    # Register alembic guard middleware (R3 — throttle re-checks at most once per 10s)
    app.add_middleware(AlembicGuardMiddleware)

    # Session cookie middleware — sets iw_chat_session if absent.
    # HttpOnly=False so JS can read it for localStorage scoping.
    @app.middleware("http")
    async def _session_cookie_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        cookie_name = "iw_chat_session"
        cookie_value = request.cookies.get(cookie_name)

        if cookie_value is None:
            cookie_value = str(uuid.uuid4())
            request.state.session_id = cookie_value
            response: Response = await call_next(request)
            secure = os.environ.get("IW_CORE_SECURE_COOKIE", "false").lower() == "true"
            secure_flag = "; Secure" if secure else ""
            response.headers["Set-Cookie"] = (
                f"{cookie_name}={cookie_value}; "
                f"Max-Age=7776000; Path=/; SameSite=Lax; HttpOnly=false{secure_flag}"
            )
            return response

        request.state.session_id = cookie_value
        return await call_next(request)

    # Auto-merge chip middleware (AC6 / Invariant 6).
    # On every per-project page, resolve the project's auto-merge phase and
    # attach it to request.state so base.html can gate the header chip without
    # an htmx round-trip.  Fully defensive: any error defaults to phase=0.
    @app.middleware("http")
    async def _auto_merge_chip_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        import re as _re  # noqa: PLC0415

        m = _re.match(r"^/project/([^/]+)/", str(request.url.path))
        if m:
            try:
                from orch.auto_merge_aggregator import get_status_snapshot  # noqa: PLC0415
                from orch.daemon.auto_merge import AutoMergeConfig  # noqa: PLC0415

                _project_id = m.group(1)
                _executor_toml = (
                    Path(__file__).resolve().parents[1] / "executor" / "auto_merge.toml"
                )
                _toml_config, _ = AutoMergeConfig.load(str(_executor_toml))
                # Honor app.dependency_overrides[get_db] so test fixtures that
                # swap the request DB also swap the middleware DB. See the
                # docstring on _open_middleware_session for the full rationale.
                _session, _owns_session = _open_middleware_session(app)
                try:
                    _snapshot = get_status_snapshot(_session, _project_id, _toml_config)
                    request.state.auto_merge_phase_for_chip = _snapshot.config.phase
                    request.state.auto_merge_status_for_chip = _snapshot
                finally:
                    if _owns_session:
                        _session.close()
            except Exception:  # noqa: BLE001
                request.state.auto_merge_phase_for_chip = 0
                request.state.auto_merge_status_for_chip = None
        return await call_next(request)

    # Initial alembic guard check at app construction (R3).
    # Suppress failures: if the DB is unreachable at boot, the middleware
    # will retry on each request (with the same suppress) and the banner
    # stays hidden. Mirrors the middleware's contextlib.suppress pattern.
    try:
        app.state.alembic_guard_status = check_db_at_head()
    except LiveDbConnectionRefusedError as exc:
        # Guard refused — expected in test context (R0 guard doing its job).
        if os.environ.get("IW_CORE_TEST_CONTEXT") == "true":
            logger.debug(
                "alembic guard skipped: %s: live DB connection refused under "
                "IW_CORE_TEST_CONTEXT=true",
                type(exc).__name__,
            )
        else:
            logger.warning(
                "alembic guard skipped: %s: live DB connection refused: %s", type(exc).__name__, exc
            )
        app.state.alembic_guard_status = None
    except Exception:  # noqa: BLE001
        logger.exception("alembic guard check failed at startup; continuing")
        app.state.alembic_guard_status = None

    # Configure Jinja2 templates and store on app state so routers can access it
    templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

    def _fmt_ts_time(ts: float) -> str:
        import datetime as _dt_module

        return (
            _dt_module.datetime.fromtimestamp(ts, tz=_dt_module.UTC)
            .astimezone()
            .strftime("%H:%M:%S")
        )

    def _localdt(dt: object, fmt: str = "%b %d %H:%M") -> str:
        import datetime as _dt_module

        if not isinstance(dt, _dt_module.datetime):
            return ""
        return dt.astimezone().strftime(fmt)

    def _timeago(dt: object) -> str:
        import datetime as _dt_module

        if not isinstance(dt, _dt_module.datetime):
            return ""
        now = _dt_module.datetime.now(tz=_dt_module.UTC)
        diff = now - dt.astimezone(tz=_dt_module.UTC)
        seconds = diff.total_seconds()
        if seconds < 60:
            return "just now"
        minutes = int(seconds / 60)
        if minutes < 60:
            return f"{minutes}m ago"
        hours = int(minutes / 60)
        if hours < 24:
            return f"{hours}h ago"
        days = int(hours / 24)
        if days < 30:
            return f"{days}d ago"
        months = int(days / 30)
        if months < 12:
            return f"{months}mo ago"
        years = int(months / 12)
        return f"{years}y ago"

    import re as _re

    _work_item_re = _re.compile(r"^(F|I|CR)-\d{5}$")

    def _is_work_item_id(value: str | None) -> bool:
        return bool(value and _work_item_re.match(value))

    templates.env.filters["intcomma"] = lambda n: f"{n:,}" if isinstance(n, int) else str(n)
    templates.env.filters["timeago"] = _timeago
    templates.env.filters["fmt_ts_time"] = _fmt_ts_time
    templates.env.filters["localdt"] = _localdt
    templates.env.filters["work_item_id"] = _is_work_item_id

    def _is_db_stale(request: Request) -> bool:
        return is_db_stale(request)

    templates.env.globals["is_db_stale"] = _is_db_stale

    import subprocess as _sp

    try:
        _git_hash = (
            _sp.check_output(
                ["git", "rev-parse", "--short", "HEAD"],  # noqa: S607
                cwd=str(_HERE),
                stderr=_sp.DEVNULL,
            )
            .decode()
            .strip()
        )
    except Exception:
        _git_hash = "0"
    templates.env.globals["static_v"] = _git_hash

    from orch.config import get_e2e_mode

    templates.env.globals["_e2e_mode"] = get_e2e_mode()

    # Innovation Ways brand globals (palette, Mermaid theme, embedded Inter,
    # logo markup) — single source of truth from doc-system/brand/brand.json.
    from dashboard.utils.branding import brand_jinja_globals

    templates.env.globals.update(brand_jinja_globals())

    app.state.templates = templates

    # Health check endpoint (used by browser_verification steps and monitoring)
    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "iw-ai-core-dashboard"}

    # Favicon route — returns the SVG as image/svg+xml so browsers don't 404
    # on the automatic GET /favicon.ico request (CR-00044 AC5)
    favicon_svg_path = _STATIC_DIR / "favicon.svg"

    @app.get("/favicon.ico")
    def favicon_ico() -> Response:
        from fastapi.responses import FileResponse

        if favicon_svg_path.is_file():
            return FileResponse(
                path=str(favicon_svg_path),
                media_type="image/svg+xml",
            )
        # Defensive: if the SVG is somehow missing, return 204 No Content
        from starlette.responses import Response

        return Response(status_code=204)

    # Schema-mismatch guard. When the live DB is missing a column that the
    # ORM model declares (e.g. a per-worktree DB seeded from production whose
    # schema is behind the worktree's own migration), every SELECT 500s with
    # an UndefinedColumn buried inside a SQLAlchemy ProgrammingError. Surface
    # a single clear 503 so qv-browser/operators see "DB schema is behind
    # models — run alembic upgrade head" instead of generic Internal Server
    # Errors and downstream JS confusion (F-00079 / S19 root cause).
    from fastapi.responses import JSONResponse  # noqa: PLC0415
    from sqlalchemy.exc import ProgrammingError  # noqa: PLC0415

    @app.exception_handler(ProgrammingError)
    async def _undefined_column_handler(request: Request, exc: ProgrammingError) -> JSONResponse:
        cause = getattr(exc, "orig", None) or getattr(exc, "__cause__", None)
        cause_name = type(cause).__name__ if cause is not None else ""
        if cause_name == "UndefinedColumn":
            logger.error(
                "DB schema is behind models for %s — UndefinedColumn: %s",
                request.url.path,
                cause,
            )
            return JSONResponse(
                status_code=503,
                content={
                    "detail": (
                        "DB schema is behind models — run 'alembic upgrade head' "
                        f"against the active DB. Missing column reported by "
                        f"PostgreSQL: {cause}"
                    ),
                    "remediation": "alembic upgrade head",
                    "kind": "schema_behind_head",
                },
                headers={"Retry-After": "30"},
            )
        raise exc

    # Register routers
    app.include_router(healthz.router)
    app.include_router(help_router.router)
    app.include_router(projects.router)
    app.include_router(running.router)
    app.include_router(actions.router)
    app.include_router(runtime_overrides.router)
    app.include_router(auto_merge_ui.router)
    app.include_router(sse.router)
    app.include_router(chat.router)
    app.include_router(system.router)
    app.include_router(keep_alive.router)
    app.include_router(daemon_control.router)
    app.include_router(project_dashboard.router)
    app.include_router(batches.router)
    app.include_router(items.router)
    app.include_router(tests.router)
    app.include_router(quality.router)
    app.include_router(oss.router)
    app.include_router(project_pages.router)
    app.include_router(jobs_ui.router)
    app.include_router(search.router)
    app.include_router(worktrees.router)
    app.include_router(containers.router)
    app.include_router(docs.router)
    app.include_router(docs_global.router)
    app.include_router(code.router)
    app.include_router(code_ui.router)
    app.include_router(code_qa.router)
    app.include_router(conversations.router)
    app.include_router(research.router)
    app.include_router(staleness.router)
    app.include_router(coverage.router)
    app.include_router(usage.router)

    return app
