# I-00040 S11 QV Fix Cycle 3/5

Quality gate S11 for work item I-00040 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: 30 unit tests failed. Pre-existing test infrastructure issues.

**Unparseable output** (always surfaces):
  !  agent "qv-gate" is a subagent, not a primary agent. Falling back to default agent
  > build · MiniMax-M2.7
  $ uv run iw step-start I-00040 --step S11
  warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
  Traceback (most recent call last):
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00040/.venv/bin/iw", line 4, in <module>
      from orch.cli.main import cli
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00040/orch/cli/__init__.py", line 1, in <module>
      from orch.cli.main import cli
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00040/orch/cli/main.py", line 20, in <module>
      from orch.cli.merge_queue_commands import merge_queue_group
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00040/orch/cli/merge_queue_commands.py", line 20, in <module>
      from orch.daemon.migration_pipeline import (
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00040/orch/daemon/migration_pipeline.py", line 24, in <module>
      from orch.db.safe_migrate import apply as safe_apply
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00040/orch/db/safe_migrate.py", line 37, in <module>
      from orch.db.live_db_guard import assert_engine_url_allowed
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00040/orch/db/live_db_guard.py", line 13
      import os
  IndentationError: unexpected indent
  → Read orch/db/live_db_guard.py [limit=30]
  ← Edit orch/db/live_db_guard.py
  Index: /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00040/orch/db/live_db_guard.py
  --- /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00040/orch/db/live_db_guard.py
  +++ /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00040/orch/db/live_db_guard.py
  @@ -9,9 +9,9 @@
   from __future__ import annotations
   import logging
  -    import os
  +import os
       if os.environ.get("IW_CORE_AGENT_CONTEXT") == "true":
           raise AgentContextForbiddenError(
               "IW_CORE_AGENT_CONTEXT is set; "
  → Read orch/db/live_db_guard.py
  ← Edit orch/db/live_db_guard.py
  Index: /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00040/orch/db/live_db_guard.py
  --- /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00040/orch/db/live_db_guard.py
  +++ /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00040/orch/db/live_db_guard.py
  @@ -11,32 +11,32 @@
   import logging
   import os
  -    if os.environ.get("IW_CORE_AGENT_CONTEXT") == "true":
  -        raise AgentContextForbiddenError(
  -            "IW_CORE_AGENT_CONTEXT is set; "
  -            "migration operations are forbidden in agent subprocesses. "
  -            "Hint: run migrations via the daemon (iw migrations apply) or "
  -            "directly as the operator."
  -        )
  +if os.environ.get("IW_CORE_AGENT_CONTEXT") == "true":
  +    raise AgentContextForbiddenError(
  +        "IW_CORE_AGENT_CONTEXT is set; "
  +        "migration operations are forbidden in agent subprocesses. "
  +        "Hint: run migrations via the daemon (iw migrations apply) or "
  +        "directly as the operator."
  +    )
  -    if os.environ.get("IW_CORE_AGENT_CONTEXT") == "true":
  -        if os.environ.get("IW_CORE_PER_WORKTREE_DB") == "true":
  -            raise LiveDbConnectionRefusedError(
  -                "Connection to live orch DB refused: "
  -                "IW_CORE_AGENT_CONTEXT and IW_CORE_PER_WORKTREE_DB are both set, "
  -                "but per-worktree DB mode is only for per-worktree DBs (port != 5433). "
  -                "The live orch DB on port 5433 is always protected."
  -            )
  +if os.environ.get("IW_CORE_AGENT_CONTEXT") == "true":
  +    if os.environ.get("IW_CORE_PER_WORKTREE_DB") == "true":
           raise LiveDbConnectionRefusedError(
               "Connection to live orch DB refused: "
  -            "host:port of the URL matches the live orch DB, "
  -            "and IW_CORE_AGENT_CONTEXT is set. "
  -            "Remediation: set IW_CORE_OPERATOR_APPLY=true via "
  -            "`iw migrations apply --i-am-operator` or run from the daemon "
  -            "entry point (which sets IW_CORE_DAEMON_CONTEXT=true)"
  +            "IW_CORE_AGENT_CONTEXT and IW_CORE_PER_WORKTREE_DB are both set, "
  +            "but per-worktree DB mode is only for per-worktree DBs (port != 5433). "
  +            "The live orch DB on port 5433 is always protected."
           )
  +    raise LiveDbConnectionRefusedError(
  +        "Connection to live orch DB refused: "
  +        "host:port of the URL matches the live orch DB, "
  +        "and IW_CORE_AGENT_CONTEXT is set. "
  +        "Remediation: set IW_CORE_OPERATOR_APPLY=true via "
  +        "`iw migrations apply --i-am-operator` or run from the daemon "
  +        "entry point (which sets IW_CORE_DAEMON_CONTEXT=true)"
  +    )
   def safe_create_engine(url: str, **kwargs: object) -> Engine:
       """Create a SQLAlchemy engine after asserting the URL is allowed.
  $ uv run iw step-start I-00040 --step S11
  warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
  Traceback (most recent call last):
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00040/.venv/bin/iw", line 4, in <module>
      from orch.cli.main import cli
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00040/orch/cli/__init__.py", line 1, in <module>
      from orch.cli.main import cli
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00040/orch/cli/main.py", line 20, in <module>
      from orch.cli.merge_queue_commands import merge_queue_group
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00040/orch/cli/merge_queue_commands.py", line 20, in <module>
      from orch.daemon.migration_pipeline import (
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00040/orch/daemon/migration_pipeline.py", line 24, in <module>
      from orch.db.safe_migrate import apply as safe_apply
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00040/orch/db/safe_migrate.py", line 37, in <module>
      from orch.db.live_db_guard import assert_engine_url_allowed
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00040/orch/db/live_db_guard.py", line 16, in <module>
      raise AgentContextForbiddenError(
            ^^^^^^^^^^^^^^^^^^^^^^^^^^
  NameError: name 'AgentContextForbiddenError' is not defined
  → Read orch/db/live_db_guard.py
  $ cd /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00040 && git show HEAD:orch/db/live_db_guard.py
  """Connection-layer chokepoint — refuses to create an engine for the live orch DB
  unless an explicit operator/daemon opt-in flag is set.
  Public API:
      LiveDbConnectionRefused  — raised when a live-DB connection is attempted
      is_live_db_url(url)       — returns True if URL resolves to the live orch DB
      assert_engine_url_allowed(url) — raises LiveDbConnectionRefused if refused context
  """
  from __future__ import annotations
  import logging
  import os
  from typing import TYPE_CHECKING
  from sqlalchemy.engine.url import make_url
  if TYPE_CHECKING:
      from sqlalchemy.engine import Engine
  logger = logging.getLogger(__name__)
  class LiveDbConnectionRefusedError(RuntimeError):
      """Raised when a connection to the live orch DB is attempted from a
      refused context (test, deprecated agent, or no opt-in)."""
  LiveDbConnectionRefused = LiveDbConnectionRefusedError
  def _get_live_db_host_port() -> tuple[str, str]:
      """Return the live orch DB host and port from env vars."""
      host = os.environ.get("IW_CORE_DB_HOST", "localhost")
      port = os.environ.get("IW_CORE_DB_PORT", "5433")
      return host, port
  def is_live_db_url(url: str) -> bool:
      """Return True if `url` resolves to the live orch DB.
      Match priority:
        1. IW_CORE_EXPECTED_INSTANCE_ID is set → the configured host:port IS
           the live DB fingerprint. Any URL at that host:port with matching
           credentials is the live DB. (We do not probe the DB to verify the
           fingerprint — that would open a connection and defeat the guard.)
        2. IW_CORE_EXPECTED_INSTANCE_ID is unset → fall back to host:port
           comparison against IW_CORE_DB_HOST / IW_CORE_DB_PORT.
      Returns False on parse failures (fail-open for non-PG URLs).
      """
      try:
          parsed = make_url(url)
      except Exception:
          return False
      live_host, live_port = _get_live_db_host_port()
      parsed_host = parsed.host or ""
      parsed_port = str(parsed.port or 5432)
      return parsed_host == live_host and parsed_port == live_port
  def assert_engine_url_allowed(url: str) -> None:
      """Raise LiveDbConnectionRefused if `url` is the live orch DB AND
      the caller is in a refused context.
      Decision matrix (evaluated top-to-bottom, first match wins):
        1. URL is NOT the live DB                    → ALLOW (no-op)
        2. Any allowed-context flag is set           → ALLOW (operator/daemon)
              - IW_CORE_OPERATOR_APPLY=true (iw migrations apply)
              - IW_CORE_DAEMON_CONTEXT=true (daemon entry point)
        3. Any refused-context flag is set           → REFUSE (raise)
              - IW_CORE_TEST_CONTEXT=true (pytest conftest)
              - IW_CORE_AGENT_CONTEXT=true (deprecated alias)
        4. No flags set                              → ALLOW (ad-hoc local scripts)
      Allowed-context wins over refused-context (rule 2 before rule 3).
      Rationale: an operator running daemon code locally inside a pytest
      sub-shell is intentional; the operator's explicit opt-in is more
      specific than the inherited test-context default.
      """
      if not is_live_db_url(url):
          return
      if os.environ.get("IW_CORE_OPERATOR_APPLY") == "true":
          return
      if os.environ.get("IW_CORE_DAEMON_CONTEXT") == "true":
          return
      if os.environ.get("IW_CORE_TEST_CONTEXT") == "true":
          raise LiveDbConnectionRefusedError(
              "Connection to live orch DB refused: "
              "host:port of the URL matches the live orch DB, "
              "and IW_CORE_TEST_CONTEXT is set. "
              "Remediation: set IW_CORE_OPERATOR_APPLY=true via "
              "`iw migrations apply --i-am-operator` or run from the daemon "
              "entry point (which sets IW_CORE_DAEMON_CONTEXT=true)"
          )
      if os.environ.get("IW_CORE_AGENT_CONTEXT") == "true":
          raise LiveDbConnectionRefusedError(
              "Connection to live orch DB refused: "
              "host:port of the URL matches the live orch DB, "
              "and IW_CORE_AGENT_CONTEXT is set. "
              "Remediation: set IW_CORE_OPERATOR_APPLY=true via "
              "`iw migrations apply --i-am-operator` or run from the daemon "
              "entry point (which sets IW_CORE_DAEMON_CONTEXT=true)"
          )
  def safe_create_engine(url: str, **kwargs: object) -> Engine:
      """Create a SQLAlchemy engine after asserting the URL is allowed.
      This is the single chokepoint for all engine creation in `orch/`.
      Every `create_engine` call in the codebase must route through here.
      """
      assert_engine_url_allowed(url)
      from sqlalchemy import create_engine as _create_engine
      return _create_engine(url, **kwargs)
  $ cd /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00040 && git checkout HEAD -- orch/db/live_db_guard.py
  (no output)
  $ cd /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00040 && uv run iw step-start I-00040 --step S11
  warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
  Error: Database error: Connection to live orch DB refused: host:port of the URL matches the live orch DB, and IW_CORE_AGENT_CONTEXT is set. Remediation: set IW_CORE_OPERATOR_APPLY=true via `iw migrations apply --i-am-operator` or run from the daemon entry point (which sets IW_CORE_DAEMON_CONTEXT=true)
  $ cd /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00040 && make test-unit 2>&1
  ...output truncated...
  Full output saved to: /home/sergiog/.local/share/opencode/tool-output/tool_dced13797001epZ3K0QniH13nz
  orch/db/safe_migrate.py:227: in _current_revision_from_db
      engine = safe_create_engine(db_url, pool_pre_ping=True)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  orch/db/live_db_guard.py:119: in safe_create_engine
      assert_engine_url_allowed(url)
  _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
  url = 'postgresql+psycopg://blocked:blocked@127.0.0.1:1/iw_orch_test_blocked'
      def assert_engine_url_allowed(url: str) -> None:
          """Raise LiveDbConnectionRefused if `url` is the live orch DB AND
          the caller is in a refused context.
          Decision matrix (evaluated top-to-bottom, first match wins):
            1. URL is NOT the live DB                    → ALLOW (no-op)
            2. Any allowed-context flag is set           → ALLOW (operator/daemon)
                  - IW_CORE_OPERATOR_APPLY=true (iw migrations apply)
                  - IW_CORE_DAEMON_CONTEXT=true (daemon entry point)
            3. Any refused-context flag is set           → REFUSE (raise)
                  - IW_CORE_TEST_CONTEXT=true (pytest conftest)
                  - IW_CORE_AGENT_CONTEXT=true (deprecated alias)
            4. No flags set                              → ALLOW (ad-hoc local scripts)
          Allowed-context wins over refused-context (rule 2 before rule 3).
          Rationale: an operator running daemon code locally inside a pytest
          sub-shell is intentional; the operator's explicit opt-in is more
          specific than the inherited test-context default.
          """
          if not is_live_db_url(url):
              return
          if os.environ.get("IW_CORE_OPERATOR_APPLY") == "true":
              return
          if os.environ.get("IW_CORE_DAEMON_CONTEXT") == "true":
              return
          if os.environ.get("IW_CORE_TEST_CONTEXT") == "true":
  >           raise LiveDbConnectionRefusedError(
                  "Connection to live orch DB refused: "
                  "host:port of the URL matches the live orch DB, "
                  "and IW_CORE_TEST_CONTEXT is set. "
                  "Remediation: set IW_CORE_OPERATOR_APPLY=true via "
                  "`iw migrations apply --i-am-operator` or run from the daemon "
                  "entry point (which sets IW_CORE_DAEMON_CONTEXT=true)"
              )
  E           orch.db.live_db_guard.LiveDbConnectionRefusedError: Connection to live orch DB refused: host:port of the URL matches the live orch DB, and IW_CORE_TEST_CONTEXT is set. Remediation: set IW_CORE_OPERATOR_APPLY=true via `iw migrations apply --i-am-operator` or run from the daemon entry point (which sets IW_CORE_DAEMON_CONTEXT=true)
  orch/db/live_db_guard.py:93: LiveDbConnectionRefusedError
  During handling of the above exception, another exception occurred:
  tmp_path = PosixPath('/tmp/pytest-of-sergiog/pytest-2839/test_startup_removes_stale_pid0')
      def test_startup_removes_stale_pid_file_and_continues(tmp_path: Path) -> None:
          """If a PID file exists with a dead PID, startup removes it and continues."""
          daemon = make_daemon(tmp_path)
          pid_file = Path(daemon.config.pid_file)
          pid_file.write_text("99999")  # dead PID
          with (
              patch("orch.daemon.main._is_pid_alive", side_effect=lambda pid: pid == os.getpid()),
              patch("orch.daemon.main.verify_instance_identity", return_value=_bootstrap_status()),
              patch.object(daemon, "_startup_health_check"),
              patch.object(daemon, "_load_projects"),
          ):
  >           daemon._startup()
  tests/unit/test_daemon_core.py:139: 
  _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
  orch/daemon/main.py:286: in _startup
      _alembic_guard_startup(self._session_factory)
  _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
  session_factory = <function make_mock_session_factory.<locals>._factory at 0x70820037d580>
      def _alembic_guard_startup(session_factory: SessionFactory) -> None:
          """Fail-fast check at daemon startup.
          Runs after verify_instance_identity. On mismatch:
            - logs CRITICAL with remediation message
            - emits a DaemonEvent of type db_schema_mismatch
            - exits with code 2
          Skippable via IW_CORE_SKIP_ALEMBIC_GUARD=true (operator override only).
          """
          global _last_mismatch_event_time
          if SKIP_ALEMBIC_GUARD:
              if os.environ.get("IW_CORE_AGENT_CONTEXT", "").lower() == "true":
                  logger.error("IW_CORE_SKIP_ALEMBIC_GUARD cannot be applied in agent context — refusing")
                  sys.exit(2)
              logger.warning("IW_CORE_SKIP_ALEMBIC_GUARD is set — skipping alembic head check")
              return
          try:
              status = check_db_at_head()
          except Exception as exc:
              logger.critical("alembic guard check failed: %s", exc)
  >           sys.exit(2)
  E           SystemExit: 2
  orch/daemon/main.py:145: SystemExit
  ------------------------------ Captured log call -------------------------------
  WARNING  orch.daemon.main:main.py:327 Stale PID file (PID 99999 dead) — removing and continuing
  CRITICAL orch.daemon.main:main.py:144 alembic guard check failed: Connection to live orch DB refused: host:port of the URL matches the live orch DB, and IW_CORE_TEST_CONTEXT is set. Remediation: set IW_CORE_OPERATOR_APPLY=true via `iw migrations apply --i-am-operator` or run from the daemon entry point (which sets IW_CORE_DAEMON_CONTEXT=true)
  ____________________ test_startup_proceeds_when_no_pid_file ____________________
  session_factory = <function make_mock_session_factory.<locals>._factory at 0x70820037d940>
      def _alembic_guard_startup(session_factory: SessionFactory) -> None:
          """Fail-fast check at daemon startup.
          Runs after verify_instance_identity. On mismatch:
            - logs CRITICAL with remediation message
            - emits a DaemonEvent of type db_schema_mismatch
            - exits with code 2
          Skippable via IW_CORE_SKIP_ALEMBIC_GUARD=true (operator override only).
          """
          global _last_mismatch_event_time
          if SKIP_ALEMBIC_GUARD:
              if os.environ.get("IW_CORE_AGENT_CONTEXT", "").lower() == "true":
                  logger.error("IW_CORE_SKIP_ALEMBIC_GUARD cannot be applied in agent context — refusing")
                  sys.exit(2)
              logger.warning("IW_CORE_SKIP_ALEMBIC_GUARD is set — skipping alembic head check")
              return
          try:
  >           status = check_db_at_head()
                       ^^^^^^^^^^^^^^^^^^
  orch/daemon/main.py:142: 
  _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
  orch/db/alembic_guard.py:84: in check_db_at_head
      current_rev = current_revision(db_url)
                    ^^^^^^^^^^^^^^^^^^^^^^^^
  orch/db/safe_migrate.py:648: in current_revision
      return _current_revision_from_db(db_url)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  orch/db/safe_migrate.py:227: in _current_revision_from_db
      engine = safe_create_engine(db_url, pool_pre_ping=True)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  orch/db/live_db_guard.py:119: in safe_create_engine
      assert_engine_url_allowed(url)
  _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
  url = 'postgresql+psycopg://blocked:blocked@127.0.0.1:1/iw_orch_test_blocked'
      def assert_engine_url_allowed(url: str) -> None:
          """Raise LiveDbConnectionRefused if `url` is the live orch DB AND
          the caller is in a refused context.
          Decision matrix (evaluated top-to-bottom, first match wins):
            1. URL is NOT the live DB                    → ALLOW (no-op)
            2. Any allowed-context flag is set           → ALLOW (operator/daemon)
                  - IW_CORE_OPERATOR_APPLY=true (iw migrations apply)
                  - IW_CORE_DAEMON_CONTEXT=true (daemon entry point)
            3. Any refused-context flag is set           → REFUSE (raise)
                  - IW_CORE_TEST_CONTEXT=true (pytest conftest)
                  - IW_CORE_AGENT_CONTEXT=true (deprecated alias)
            4. No flags set                              → ALLOW (ad-hoc local scripts)
          Allowed-context wins over refused-context (rule 2 before rule 3).
          Rationale: an operator running daemon code locally inside a pytest
          sub-shell is intentional; the operator's explicit opt-in is more
          specific than the inherited test-context default.
          """
          if not is_live_db_url(url):
              return
          if os.environ.get("IW_CORE_OPERATOR_APPLY") == "true":
              return
          if os.environ.get("IW_CORE_DAEMON_CONTEXT") == "true":
              return
          if os.environ.get("IW_CORE_TEST_CONTEXT") == "true":
  >           raise LiveDbConnectionRefusedError(
                  "Connection to live orch DB refused: "
                  "host:port of the URL matches the live orch DB, "
                  "and IW_CORE_TEST_CONTEXT is set. "
                  "Remediation: set IW_CORE_OPERATOR_APPLY=true via "
                  "`iw migrations apply --i-am-operator` or run from the daemon "
                  "entry point (which sets IW_CORE_DAEMON_CONTEXT=true)"
              )
  E           orch.db.live_db_guard.LiveDbConnectionRefusedError: Connection to live orch DB refused: host:port of the URL matches the live orch DB, and IW_CORE_TEST_CONTEXT is set. Remediation: set IW_CORE_OPERATOR_APPLY=true via `iw migrations apply --i-am-operator` or run from the daemon entry point (which sets IW_CORE_DAEMON_CONTEXT=true)
  orch/db/live_db_guard.py:93: LiveDbConnectionRefusedError
  During handling of the above exception, another exception occurred:
  tmp_path = PosixPath('/tmp/pytest-of-sergiog/pytest-2839/test_startup_proceeds_when_no_0')
      def test_startup_proceeds_when_no_pid_file(tmp_path: Path) -> None:
          """If no PID file exists, startup proceeds without error."""
          daemon = make_daemon(tmp_path)
          with (
              patch("orch.daemon.main.verify_instance_identity", return_value=_bootstrap_status()),
              patch.object(daemon, "_startup_health_check"),
              patch.object(daemon, "_load_projects"),
          ):
  >           daemon._startup()  # should not raise
              ^^^^^^^^^^^^^^^^^
  tests/unit/test_daemon_core.py:168: 
  _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
  orch/daemon/main.py:286: in _startup
      _alembic_guard_startup(self._session_factory)
  _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
  session_factory = <function make_mock_session_factory.<locals>._factory at 0x70820037d940>
      def _alembic_guard_startup(session_factory: SessionFactory) -> None:
          """Fail-fast check at daemon startup.
          Runs after verify_instance_identity. On mismatch:
            - logs CRITICAL with remediation message
            - emits a DaemonEvent of type db_schema_mismatch
            - exits with code 2
          Skippable via IW_CORE_SKIP_ALEMBIC_GUARD=true (operator override only).
          """
          global _last_mismatch_event_time
          if SKIP_ALEMBIC_GUARD:
              if os.environ.get("IW_CORE_AGENT_CONTEXT", "").lower() == "true":
                  logger.error("IW_CORE_SKIP_ALEMBIC_GUARD cannot be applied in agent context — refusing")
                  sys.exit(2)
              logger.warning("IW_CORE_SKIP_ALEMBIC_GUARD is set — skipping alembic head check")
              return
          try:
              status = check_db_at_head()
          except Exception as exc:
              logger.critical("alembic guard check failed: %s", exc)
  >           sys.exit(2)
  E           SystemExit: 2
  orch/daemon/main.py:145: SystemExit
  ------------------------------ Captured log call -------------------------------
  CRITICAL orch.daemon.main:main.py:144 alembic guard check failed: Connection to live orch DB refused: host:port of the URL matches the live orch DB, and IW_CORE_TEST_CONTEXT is set. Remediation: set IW_CORE_OPERATOR_APPLY=true via `iw migrations apply --i-am-operator` or run from the daemon entry point (which sets IW_CORE_DAEMON_CONTEXT=true)
  ______________________ test_favicon_served_at_static_path ______________________
      def test_favicon_served_at_static_path() -> None:
          """GET /static/favicon.svg returns the SVG favicon."""
  >       with patch("dashboard.app.check_db_at_head") as mock_guard:
  tests/unit/test_dashboard_favicon.py:15: 
  _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
  /usr/lib/python3.12/unittest/mock.py:1458: in __enter__
      original, local = self.get_original()
                        ^^^^^^^^^^^^^^^^^^^
  _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
  self = <unittest.mock._patch object at 0x70820014fec0>
      def get_original(self):
          target = self.getter()
          name = self.attribute
          original = DEFAULT
          local = False
          try:
              original = target.__dict__[name]
          except (AttributeError, KeyError):
              original = getattr(target, name, DEFAULT)
          else:
              local = True
          if name in _builtins and isinstance(target, ModuleType):
              self.create = True
          if not self.create and original is DEFAULT:
  >           raise AttributeError(
                  "%s does not have the attribute %r" % (target, name)
              )
  E           AttributeError: <module 'dashboard.app' from '/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00040/dashboard/app.py'> does not have the attribute 'check_db_at_head'
  /usr/lib/python3.12/unittest/mock.py:1431: AttributeError
  _________ TestIsMergeQueueFrozen.test_returns_true_when_active_is_true _________
  self = <unit.test_migration_pipeline.TestIsMergeQueueFrozen object at 0x7082010a99d0>
      def test_returns_true_when_active_is_true(self) -> None:
          from orch.daemon.migration_pipeline import is_merge_queue_frozen
          mock_result = MagicMock()
          mock_result.fetchone.return_value = ({"active": True},)
          mock_session = MagicMock()
          mock_session.execute.return_value = mock_result
          mock_connection = MagicMock()
          mock_connection.__enter__ = MagicMock(return_value=mock_connection)
          mock_connection.__exit__ = MagicMock(return_value=False)
          with patch("orch.daemon.migration_pipeline.safe_create_engine") as mock_engine:
              mock_engine.return_value.connect.return_value = mock_connection
              mock_engine.return_value.dispose = MagicMock()
              with patch("orch.daemon.migration_pipeline.sessionmaker") as mock_sm:
                  mock_sm.return_value.return_value = mock_session
                  result = is_merge_queue_frozen()
  >       assert result is True
  E       assert False is True
  tests/unit/test_migration_pipeline.py:55: AssertionError
  ________________ TestApply.test_apply_refuses_in_agent_context _________________
  self = <unit.test_safe_migrate.TestApply object at 0x708200d2bef0>
      def test_apply_refuses_in_agent_context(self) -> None:
          env = {"IW_CORE_AGENT_CONTEXT": "true"}
  >       with patch.dict("os.environ", env, clear=False), pytest.raises(
              LiveDbConnectionRefused
          ):
  E       Failed: DID NOT RAISE <class 'orch.db.live_db_guard.LiveDbConnectionRefusedError'>
  tests/unit/test_safe_migrate.py:40: Failed
  _____________ TestRollback.test_rollback_refuses_in_agent_context ______________
  self = <sqlalchemy.engine.base.Connection object at 0x7081a214c7a0>
  engine = Engine(postgresql+psycopg://unused/db), connection = None
  _has_events = None, _allow_revalidate = True, _allow_autobegin = True
      def __init__(
          self,
          engine: Engine,
          connection: Optional[PoolProxiedConnection] = None,
          _has_events: Optional[bool] = None,
          _allow_revalidate: bool = True,
          _allow_autobegin: bool = True,
      ):
          """Construct a new Connection."""
          self.engine = engine
          self.dialect = dialect = engine.dialect
          if connection is None:
              try:
  >               self._dbapi_connection = engine.raw_connection()
                                           ^^^^^^^^^^^^^^^^^^^^^^^
  .venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:143: 
  _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
  .venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:3317: in raw_connection
      return self.pool.connect()
             ^^^^^^^^^^^^^^^^^^^
  .venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:448: in connect
      return _ConnectionFairy._checkout(self)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  .venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:1272: in _checkout
      fairy = _ConnectionRecord.checkout(pool)
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  .venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:712: in checkout
      rec = pool._do_get()
            ^^^^^^^^^^^^^^
  .venv/lib/python3.12/site-packages/sqlalchemy/pool/impl.py:177: in _do_get
      with util.safe_reraise():
  .venv/lib/python3.12/site-packages/sqlalchemy/util/langhelpers.py:121: in __exit__
      raise exc_value.with_traceback(exc_tb)
  .venv/lib/python3.12/site-packages/sqlalchemy/pool/impl.py:175: in _do_get
      return self._create_connection()
             ^^^^^^^^^^^^^^^^^^^^^^^^^
  .venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:389: in _create_connection
      return _ConnectionRecord(self)
             ^^^^^^^^^^^^^^^^^^^^^^^
  .venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:674: in __init__
      self.__connect()
  .venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:900: in __connect
      with util.safe_reraise():
  .venv/lib/python3.12/site-packages/sqlalchemy/util/langhelpers.py:121: in __exit__
      raise exc_value.with_traceback(exc_tb)
  .venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:896: in __connect
      self.dbapi_connection = connection = pool._invoke_creator(self)
                                           ^^^^^^^^^^^^^^^^^^^^^^^^^^
  .venv/lib/python3.12/site-packages/sqlalchemy/engine/create.py:667: in connect
      return dialect.connect(*cargs_tup, **cparams)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  .venv/lib/python3.12/site-packages/sqlalchemy/engine/default.py:630: in connect
      return self.loaded_dbapi.connect(*cargs, **cparams)  # type: ignore[no-any-return]  # NOQA: E501
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  .venv/lib/python3.12/site-packages/psycopg/connection.py:100: in connect
      attempts = conninfo_attempts(params)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^
  _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
  params = {'dbname': 'db', 'host': 'unused'}
      def conninfo_attempts(params: ConnMapping) -> list[ConnDict]:
          """Split a set of connection params on the single attempts to perform.
          A connection param can perform more than one attempt more than one ``host``
          is provided.
          Also perform async resolution of the hostname into hostaddr. Because a host
          can resolve to more than one address, this can lead to yield more attempts
          too. Raise `OperationalError` if no host could be resolved.
          Because the libpq async function doesn't honour the timeout, we need to
          reimplement the repeated attempts.
          """
          last_exc = None
          attempts = []
          if prefer_standby := (
              get_param(params, "target_session_attrs") == "prefer-standby"
          ):
              params = {k: v for k, v in params.items() if k != "target_session_attrs"}
          for attempt in split_attempts(params):
              try:
                  attempts.extend(_resolve_hostnames(attempt))
              except OSError as ex:
                  last_exc = e.OperationalError(
                      f"failed to resolve host {attempt.get('host')!r}: {ex}"
                  )
                  logger.debug("%s", last_exc)
          if not attempts:
              assert last_exc
  >           raise last_exc
  E           psycopg.OperationalError: failed to resolve host 'unused': [Errno -3] Temporary failure in name resolution
  .venv/lib/python3.12/site-packages/psycopg/_conninfo_attempts.py:55: OperationalError
  The above exception was the direct cause of the following exception:
  self = <unit.test_safe_migrate.TestRollback object at 0x708200d2a0f0>
      def test_rollback_refuses_in_agent_context(self) -> None:
          env = {"IW_CORE_AGENT_CONTEXT": "true"}
          with patch.dict("os.environ", env, clear=False), pytest.raises(AgentContextForbiddenError):
  >           rollback("postgresql+psycopg://unused/db")
  tests/unit/test_safe_migrate.py:50: 
  _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
  orch/db/safe_migrate.py:601: in rollback
      revision_from, stderr_tail, error_message = _run_alembic_downgrade(cfg, steps)
                                                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  orch/db/safe_migrate.py:352: in _run_alembic_downgrade
      revision_from = _current_revision_from_db(cfg.get_main_option("sqlalchemy.url") or "")
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  orch/db/safe_migrate.py:229: in _current_revision_from_db
      with engine.connect() as conn:
           ^^^^^^^^^^^^^^^^
  .venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:3293: in connect
      return self._connection_cls(self)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^
  .venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:145: in __init__
      Connection._handle_dbapi_exception_noconnection(
  .venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:2448: in _handle_dbapi_exception_noconnection
      raise sqlalchemy_exception.with_traceback(exc_info[2]) from e
  .venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:143: in __init__
      self._dbapi_connection = engine.raw_connection()
                               ^^^^^^^^^^^^^^^^^^^^^^^
  .venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py:3317: in raw_connection
      return self.pool.connect()
             ^^^^^^^^^^^^^^^^^^^
  .venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:448: in connect
      return _ConnectionFairy._checkout(self)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  .venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:1272: in _checkout
      fairy = _ConnectionRecord.checkout(pool)
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  .venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:712: in checkout
      rec = pool._do_get()
            ^^^^^^^^^^^^^^
  .venv/lib/python3.12/site-packages/sqlalchemy/pool/impl.py:177: in _do_get
      with util.safe_reraise():
  .venv/lib/python3.12/site-packages/sqlalchemy/util/langhelpers.py:121: in __exit__
      raise exc_value.with_traceback(exc_tb)
  .venv/lib/python3.12/site-packages/sqlalchemy/pool/impl.py:175: in _do_get
      return self._create_connection()
             ^^^^^^^^^^^^^^^^^^^^^^^^^
  .venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:389: in _create_connection
      return _ConnectionRecord(self)
             ^^^^^^^^^^^^^^^^^^^^^^^
  .venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:674: in __init__
      self.__connect()
  .venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:900: in __connect
      with util.safe_reraise():
  .venv/lib/python3.12/site-packages/sqlalchemy/util/langhelpers.py:121: in __exit__
      raise exc_value.with_traceback(exc_tb)
  .venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py:896: in __connect
      self.dbapi_connection = connection = pool._invoke_creator(self)
                                           ^^^^^^^^^^^^^^^^^^^^^^^^^^
  .venv/lib/python3.12/site-packages/sqlalchemy/engine/create.py:667: in connect
      return dialect.connect(*cargs_tup, **cparams)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  .venv/lib/python3.12/site-packages/sqlalchemy/engine/default.py:630: in connect
      return self.loaded_dbapi.connect(*cargs, **cparams)  # type: ignore[no-any-return]  # NOQA: E501
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  .venv/lib/python3.12/site-packages/psycopg/connection.py:100: in connect
      attempts = conninfo_attempts(params)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^
  _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
  params = {'dbname': 'db', 'host': 'unused'}
      def conninfo_attempts(params: ConnMapping) -> list[ConnDict]:
          """Split a set of connection params on the single attempts to perform.
          A connection param can perform more than one attempt more than one ``host``
          is provided.
          Also perform async resolution of the hostname into hostaddr. Because a host
          can resolve to more than one address, this can lead to yield more attempts
          too. Raise `OperationalError` if no host could be resolved.
          Because the libpq async function doesn't honour the timeout, we need to
          reimplement the repeated attempts.
          """
          last_exc = None
          attempts = []
          if prefer_standby := (
              get_param(params, "target_session_attrs") == "prefer-standby"
          ):
              params = {k: v for k, v in params.items() if k != "target_session_attrs"}
          for attempt in split_attempts(params):
              try:
                  attempts.extend(_resolve_hostnames(attempt))
              except OSError as ex:
                  last_exc = e.OperationalError(
                      f"failed to resolve host {attempt.get('host')!r}: {ex}"
                  )
                  logger.debug("%s", last_exc)
          if not attempts:
              assert last_exc
  >           raise last_exc
  E           sqlalchemy.exc.OperationalError: (psycopg.OperationalError) failed to resolve host 'unused': [Errno -3] Temporary failure in name resolution
  E           (Background on this error at: https://sqlalche.me/e/20/e3q8)
  .venv/lib/python3.12/site-packages/psycopg/_conninfo_attempts.py:55: OperationalError
  _____________ TestListPendingRevisions.test_multiple_heads_raises ______________
  self = <unit.test_safe_migrate.TestListPendingRevisions object at 0x708200d2a870>
      def test_multiple_heads_raises(self) -> None:
          mock_script_dir = MagicMock()
          mock_script_dir.get_heads.return_value = ["rev_a", "rev_b"]
          with patch(
              "alembic.script.ScriptDirectory.from_config",
              return_value=mock_script_dir,
          ):
              with pytest.raises(MultipleHeadsError) as exc_info:
  >               list_pending_revisions()
  tests/unit/test_safe_migrate.py:72: 
  _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
  orch/db/safe_migrate.py:446: in list_pending_revisions
      script_dir = ScriptDirectory.from_config(_build_alembic_config(db_url))
                                               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  orch/db/safe_migrate.py:216: in _build_alembic_config
      assert_engine_url_allowed(db_url)
  _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
  url = 'postgresql+psycopg://blocked:blocked@127.0.0.1:1/iw_orch_test_blocked'
      def assert_engine_url_allowed(url: str) -> None:
          """Raise LiveDbConnectionRefused if `url` is the live orch DB AND
          the caller is in a refused context.
          Decision matrix (evaluated top-to-bottom, first match wins):
            1. URL is NOT the live DB                    → ALLOW (no-op)
            2. Any allowed-context flag is set           → ALLOW (operator/daemon)
                  - IW_CORE_OPERATOR_APPLY=true (iw migrations apply)
                  - IW_CORE_DAEMON_CONTEXT=true (daemon entry point)
            3. Any refused-context flag is set           → REFUSE (raise)
                  - IW_CORE_TEST_CONTEXT=true (pytest conftest)
                  - IW_CORE_AGENT_CONTEXT=true (deprecated alias)
            4. No flags set                              → ALLOW (ad-hoc local scripts)
          Allowed-context wins over refused-context (rule 2 before rule 3).
          Rationale: an operator running daemon code locally inside a pytest
          sub-shell is intentional; the operator's explicit opt-in is more
          specific than the inherited test-context default.
          """
          if not is_live_db_url(url):
              return
          if os.environ.get("IW_CORE_OPERATOR_APPLY") == "true":
              return
          if os.environ.get("IW_CORE_DAEMON_CONTEXT") == "true":
              return
          if os.environ.get("IW_CORE_TEST_CONTEXT") == "true":
  >           raise LiveDbConnectionRefusedError(
                  "Connection to live orch DB refused: "
                  "host:port of the URL matches the live orch DB, "
                  "and IW_CORE_TEST_CONTEXT is set. "
                  "Remediation: set IW_CORE_OPERATOR_APPLY=true via "
                  "`iw migrations apply --i-am-operator` or run from the daemon "
                  "entry point (which sets IW_CORE_DAEMON_CONTEXT=true)"
              )
  E           orch.db.live_db_guard.LiveDbConnectionRefusedError: Connection to live orch DB refused: host:port of the URL matches the live orch DB, and IW_CORE_TEST_CONTEXT is set. Remediation: set IW_CORE_OPERATOR_APPLY=true via `iw migrations apply --i-am-operator` or run from the daemon entry point (which sets IW_CORE_DAEMON_CONTEXT=true)
  orch/db/live_db_guard.py:93: LiveDbConnectionRefusedError
  ____ TestWriteMigrationLog.test_write_migration_log_old_revision_persisted _____
  self = <unit.test_safe_migrate.TestWriteMigrationLog object at 0x708200d2b800>
      def test_write_migration_log_old_revision_persisted(self) -> None:
          from orch.db.safe_migrate import _write_migration_log
  >       with (
              patch.dict(
                  "os.environ",
                  {"IW_CORE_OPERATOR_APPLY": "true"},
                  clear=False,
              ),
              patch(
                  "orch.db.safe_migrate.get_db_url",
                  return_value="postgresql+psycopg://u:p@host:5432/db",
              ),
              patch("orch.db.safe_migrate.safe_create_engine") as mock_engine,
          ):
  tests/unit/test_safe_migrate.py:107: 
  _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
  /usr/lib/python3.12/unittest/mock.py:1458: in __enter__
      original, local = self.get_original()
                        ^^^^^^^^^^^^^^^^^^^
  _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
  self = <unittest.mock._patch object at 0x7081a1fb6ed0>
      def get_original(self):
          target = self.getter()
          name = self.attribute
          original = DEFAULT
          local = False
          try:
              original = target.__dict__[name]
          except (AttributeError, KeyError):
              original = getattr(target, name, DEFAULT)
          else:
              local = True
          if name in _builtins and isinstance(target, ModuleType):
              self.create = True
          if not self.create and original is DEFAULT:
  >           raise AttributeError(
                  "%s does not have the attribute %r" % (target, name)
              )
  E           AttributeError: <module 'orch.db.safe_migrate' from '/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00040/orch/db/safe_migrate.py'> does not have the attribute 'safe_create_engine'
  /usr/lib/python3.12/unittest/mock.py:1431: AttributeError
  _ TestWriteMigrationLog.test_write_migration_log_backward_compat_no_old_revision _
  self = <unit.test_safe_migrate.TestWriteMigrationLog object at 0x708200d2bb90>
      def test_write_migration_log_backward_compat_no_old_revision(self) -> None:
          from orch.db.safe_migrate import _write_migration_log
  >       with (
              patch.dict(
                  "os.environ",
                  {"IW_CORE_OPERATOR_APPLY": "true"},
                  clear=False,
              ),
              patch(
                  "orch.db.safe_migrate.get_db_url",
                  return_value="postgresql+psycopg://u:p@host:5432/db",
              ),
              patch("orch.db.safe_migrate.safe_create_engine") as mock_engine,
          ):
  tests/unit/test_safe_migrate.py:144: 
  _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
  /usr/lib/python3.12/unittest/mock.py:1458: in __enter__
      original, local = self.get_original()
                        ^^^^^^^^^^^^^^^^^^^
  _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
  self = <unittest.mock._patch object at 0x7081a1fa0230>
      def get_original(self):
          target = self.getter()
          name = self.attribute
          original = DEFAULT
          local = False
          try:
              original = target.__dict__[name]
          except (AttributeError, KeyError):
              original = getattr(target, name, DEFAULT)
          else:
              local = True
          if name in _builtins and isinstance(target, ModuleType):
              self.create = True
          if not self.create and original is DEFAULT:
  >           raise AttributeError(
                  "%s does not have the attribute %r" % (target, name)
              )
  E           AttributeError: <module 'orch.db.safe_migrate' from '/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00040/orch/db/safe_migrate.py'> does not have the attribute 'safe_create_engine'
  /usr/lib/python3.12/unittest/mock.py:1431: AttributeError
  _ TestAssertNotAgentContextRelax.test_blocks_against_orch_db_when_agent_context _
  self = <unit.test_safe_migrate.TestAssertNotAgentContextRelax object at 0x708200d2bfb0>
      def test_blocks_against_orch_db_when_agent_context(self) -> None:
          from orch.db.safe_migrate import _assert_not_agent_context
  >       with (
              patch.dict(
                  "os.environ",
                  {"IW_CORE_AGENT_CONTEXT": "true", "IW_CORE_PER_WORKTREE_DB": "false"},
                  clear=False,
              ),
              pytest.raises(AgentContextForbiddenError),
          ):
  E       Failed: DID NOT RAISE <class 'orch.db.safe_migrate.AgentContextForbiddenError'>
  tests/unit/test_safe_migrate.py:182: Failed
  _ TestAssertNotAgentContextRelax.test_blocks_against_orch_db_even_with_per_worktree_flag _
  self = <unit.test_safe_migrate.TestAssertNotAgentContextRelax object at 0x708200d2b320>
      def test_blocks_against_orch_db_even_with_per_worktree_flag(self) -> None:
          from orch.db.safe_migrate import _assert_not_agent_context
  >       with (
              patch.dict(
                  "os.environ",
                  {"IW_CORE_AGENT_CONTEXT": "true", "IW_CORE_PER_WORKTREE_DB": "true"},
                  clear=False,
              ),
              pytest.raises(AgentContextForbiddenError),
          ):
  E       Failed: DID NOT RAISE <class 'orch.db.safe_migrate.AgentContextForbiddenError'>
  tests/unit/test_safe_migrate.py:205: Failed
  ___________ TestMultipleHeadsErrorArgs.test_args_contains_both_heads ___________
  self = <unit.test_safe_migrate_guards.TestMultipleHeadsErrorArgs object at 0x708200d598b0>
      def test_args_contains_both_heads(self) -> None:
          mock_script_dir = MagicMock()
          mock_script_dir.get_heads.return_value = ["rev_a", "rev_b"]
          with (
              patch(
                  "alembic.script.ScriptDirectory.from_config",
                  return_value=mock_script_dir,
              ),
              pytest.raises(MultipleHeadsError) as exc_info,
          ):
  >           list_pending_revisions()
  tests/unit/test_safe_migrate_guards.py:134: 
  _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
  orch/db/safe_migrate.py:446: in list_pending_revisions
      script_dir = ScriptDirectory.from_config(_build_alembic_config(db_url))
                                               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  orch/db/safe_migrate.py:216: in _build_alembic_config
      assert_engine_url_allowed(db_url)
  _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
  url = 'postgresql+psycopg://blocked:blocked@127.0.0.1:1/iw_orch_test_blocked'
      def assert_engine_url_allowed(url: str) -> None:
          """Raise LiveDbConnectionRefused if `url` is the live orch DB AND
          the caller is in a refused context.
          Decision matrix (evaluated top-to-bottom, first match wins):
            1. URL is NOT the live DB                    → ALLOW (no-op)
            2. Any allowed-context flag is set           → ALLOW (operator/daemon)
                  - IW_CORE_OPERATOR_APPLY=true (iw migrations apply)
                  - IW_CORE_DAEMON_CONTEXT=true (daemon entry point)
            3. Any refused-context flag is set           → REFUSE (raise)
                  - IW_CORE_TEST_CONTEXT=true (pytest conftest)
                  - IW_CORE_AGENT_CONTEXT=true (deprecated alias)
            4. No flags set                              → ALLOW (ad-hoc local scripts)
          Allowed-context wins over refused-context (rule 2 before rule 3).
          Rationale: an operator running daemon code locally inside a pytest
          sub-shell is intentional; the operator's explicit opt-in is more
          specific than the inherited test-context default.
          """
          if not is_live_db_url(url):
              return
          if os.environ.get("IW_CORE_OPERATOR_APPLY") == "true":
              return
          if os.environ.get("IW_CORE_DAEMON_CONTEXT") == "true":
              return
          if os.environ.get("IW_CORE_TEST_CONTEXT") == "true":
  >           raise LiveDbConnectionRefusedError(
                  "Connection to live orch DB refused: "
                  "host:port of the URL matches the live orch DB, "
                  "and IW_CORE_TEST_CONTEXT is set. "
                  "Remediation: set IW_CORE_OPERATOR_APPLY=true via "
                  "`iw migrations apply --i-am-operator` or run from the daemon "
                  "entry point (which sets IW_CORE_DAEMON_CONTEXT=true)"
              )
  E           orch.db.live_db_guard.LiveDbConnectionRefusedError: Connection to live orch DB refused: host:port of the URL matches the live orch DB, and IW_CORE_TEST_CONTEXT is set. Remediation: set IW_CORE_OPERATOR_APPLY=true via `iw migrations apply --i-am-operator` or run from the daemon entry point (which sets IW_CORE_DAEMON_CONTEXT=true)
  orch/db/live_db_guard.py:93: LiveDbConnectionRefusedError
  .venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1434
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00040/.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1434: PytestConfigWarning: Unknown config option: env
      self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")
  orch/db/models.py:175
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00040/orch/db/models.py:175: PytestCollectionWarning: cannot collect test class 'TestRunStatus' because it has a __init__ constructor (from: tests/unit/test_test_runner.py)
      class TestRunStatus(enum.Enum):
  tests/unit/daemon/test_batch_manager_worktree_hooks.py::TestTerminalTransitionComposeDown::test_terminal_transition_calls_compose_down
  tests/unit/test_safe_migrate.py::TestApply::test_apply_refuses_in_agent_context
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00040/orch/db/safe_migrate.py:532: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
      _assert_not_agent_context(live_db_url)
  tests/unit/test_code_qa_router_rerender.py: 1 warning
  tests/unit/test_qa_engine_hybrid_retrieval.py: 2 warnings
  tests/unit/test_qa_engine_render_cache.py: 4 warnings
  tests/unit/test_qa_v2_prompt_layout.py: 8 warnings
  tests/unit/test_qa_v2_relevance_filter_eval.py: 5 warnings
    <string>:9: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
  tests/unit/test_qa_engine.py::TestAnswerStream::test_answer_stream_falls_back_when_module_filter_empty
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00040/tests/unit/test_qa_engine.py:625: RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited
      async for token in engine.answer_stream(
    Enable tracemalloc to get traceback where the object was allocated.
    See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.
  tests/unit/test_qa_engine.py::TestAnswerStream::test_answer_stream_translates_dotted_module_path_to_filesystem_filter
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00040/tests/unit/test_qa_engine.py:723: RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited
      async for token in engine.answer_stream(
    Enable tracemalloc to get traceback where the object was allocated.
    See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.
  tests/unit/test_qa_engine.py::TestAnswerStream::test_answer_stream_does_not_fall_back_when_module_filter_nonempty
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00040/tests/unit/test_qa_engine.py:819: RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited
      async for token in engine.answer_stream(
    Enable tracemalloc to get traceback where the object was allocated.
    See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.
  tests/unit/test_qa_engine.py::TestAnswerStream::test_answer_stream_does_not_fall_back_for_architecture_context
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00040/tests/unit/test_qa_engine.py:905: RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited
      async for token in engine.answer_stream(
    Enable tracemalloc to get traceback where the object was allocated.
    See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.
  tests/unit/test_safe_migrate.py::TestAssertNotAgentContext::test_does_not_raise_when_env_false
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00040/tests/unit/test_safe_migrate.py:25: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
      _assert_not_agent_context()
  tests/unit/test_safe_migrate.py::TestAssertNotAgentContext::test_does_not_raise_when_env_absent
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00040/tests/unit/test_safe_migrate.py:29: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
      _assert_not_agent_context()
  tests/unit/test_safe_migrate.py::TestAssertNotAgentContext::test_raises_when_env_true
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00040/tests/unit/test_safe_migrate.py:34: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
      _assert_not_agent_context()
  tests/unit/test_safe_migrate.py::TestRollback::test_rollback_refuses_in_agent_context
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00040/orch/db/safe_migrate.py:594: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
      _assert_not_agent_context(live_db_url)
  tests/unit/test_safe_migrate.py::TestAssertNotAgentContextRelax::test_blocks_against_orch_db_when_agent_context
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00040/tests/unit/test_safe_migrate.py:190: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
      _assert_not_agent_context("postgresql+psycopg://localhost:5433/iw_core")
  tests/unit/test_safe_migrate.py::TestAssertNotAgentContextRelax::test_allows_against_per_worktree_db_when_per_worktree_flag_set
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00040/tests/unit/test_safe_migrate.py:200: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
      _assert_not_agent_context("postgresql+psycopg://localhost:34567/iw_worktree")
  tests/unit/test_safe_migrate.py::TestAssertNotAgentContextRelax::test_blocks_against_orch_db_even_with_per_worktree_flag
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00040/tests/unit/test_safe_migrate.py:213: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
      _assert_not_agent_context("postgresql+psycopg://localhost:5433/iw_core")
  tests/unit/test_safe_migrate.py::TestAssertNotAgentContextRelax::test_blocks_when_only_per_worktree_flag_without_agent_context_is_irrelevant
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00040/tests/unit/test_safe_migrate.py:225: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
      _assert_not_agent_context("postgresql+psycopg://localhost:34567/iw_worktree")
  tests/unit/test_safe_migrate.py::TestAssertNotAgentContextRelax::test_allows_outside_agent_context_without_flag
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00040/tests/unit/test_safe_migrate.py:235: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
      _assert_not_agent_context("postgresql+psycopg://localhost:5433/iw_core")
  tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_for_non_exact_true[TRUE]
  tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_for_non_exact_true[True]
  tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_for_non_exact_true[1]
  tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_for_non_exact_true[yes]
  tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_for_non_exact_true[YES]
  tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_for_non_exact_true[true\n]
  tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_for_non_exact_true[ true]
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00040/tests/unit/test_safe_migrate_guards.py:47: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
      _assert_not_agent_context()
  tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_when_absent_or_empty[]
  tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_when_absent_or_empty[None]
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00040/tests/unit/test_safe_migrate_guards.py:59: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
      _assert_not_agent_context()
  tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_raises_only_for_exact_true
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00040/tests/unit/test_safe_migrate_guards.py:64: DeprecationWarning: _assert_not_agent_context is deprecated; use orch.db.live_db_guard.assert_engine_url_allowed
      _assert_not_agent_context()
  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  make: *** [Makefile:36: test-unit] Error 1
  $ mkdir -p /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00040/ai-dev/active/I-00040/reports
  (no output)
  ← Write ai-dev/active/I-00040/reports/I-00040_S11_QvGate_report.md
  Wrote file successfully.
  $ uv run iw step-fail I-00040 --step S11 --reason "30 unit tests failed. Pre-existing test infrastructure issues unrelated to I-00040 implementation. See report."
  warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
  Error: Database error: Connection to live orch DB refused: host:port of the URL matches the live orch DB, and IW_CORE_AGENT_CONTEXT is set. Remediation: set IW_CORE_OPERATOR_APPLY=true via `iw migrations apply --i-am-operator` or run from the daemon entry point (which sets IW_CORE_DAEMON_CONTEXT=true)


## Gate Command

The quality gate that failed runs:
```bash
make test-unit
```

After applying fixes, re-run this command to verify the issues are resolved.

## Constraints

1. **Only fix the reported errors.** Do not refactor unrelated code.
2. **Preserve existing behavior.** Fixes must not break working functionality.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. **Run the gate command after every fix** to verify resolution.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
