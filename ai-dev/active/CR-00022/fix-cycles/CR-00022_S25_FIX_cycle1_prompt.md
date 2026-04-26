# CR-00022 S25 QV Fix Cycle 1/5

Quality gate S25 for work item CR-00022 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: 2 unit tests failed due to incomplete mock isolation - code under test calls get_db_url() which bypasses mocked session

**Unparseable output** (always surfaces):
  !  agent "qv-gate" is a subagent, not a primary agent. Falling back to default agent
  > build · MiniMax-M2.7
  $ uv run iw step-start CR-00022 --step S25
  warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
  Started CR-00022 step S25 (already in progress)
  $ make test-unit
  ...output truncated...
  Full output saved to: /home/sergiog/.local/share/opencode/tool-output/tool_dcb480830002hzQ0aXbe3juEhz
      with util.safe_reraise():
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/sqlalchemy/util/langhelpers.py", line 121, in __exit__
      raise exc_value.with_traceback(exc_tb)
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/sqlalchemy/pool/impl.py", line 175, in _do_get
      return self._create_connection()
             ^^^^^^^^^^^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py", line 389, in _create_connection
      return _ConnectionRecord(self)
             ^^^^^^^^^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py", line 674, in __init__
      self.__connect()
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py", line 900, in __connect
      with util.safe_reraise():
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/sqlalchemy/util/langhelpers.py", line 121, in __exit__
      raise exc_value.with_traceback(exc_tb)
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py", line 896, in __connect
      self.dbapi_connection = connection = pool._invoke_creator(self)
                                           ^^^^^^^^^^^^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/sqlalchemy/engine/create.py", line 667, in connect
      return dialect.connect(*cargs_tup, **cparams)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/sqlalchemy/engine/default.py", line 630, in connect
      return self.loaded_dbapi.connect(*cargs, **cparams)  # type: ignore[no-any-return]  # NOQA: E501
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/psycopg/connection.py", line 122, in connect
      raise last_ex.with_traceback(None)
  psycopg.OperationalError: connection failed: connection to server at "127.0.0.1", port 1 failed: FATAL:  password authentication failed for user "blocked"
  The above exception was the direct cause of the following exception:
  Traceback (most recent call last):
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/orch/daemon/migration_pipeline.py", line 179, in run_rollback
      result = safe_rollback(live_url, steps=1, batch_id=batch_id)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/orch/db/safe_migrate.py", line 561, in rollback
      revision_from, stderr_tail, error_message = _run_alembic_downgrade(cfg, steps)
                                                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/orch/db/safe_migrate.py", line 316, in _run_alembic_downgrade
      revision_from = _current_revision_from_db(cfg.get_main_option("sqlalchemy.url") or "")
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/orch/db/safe_migrate.py", line 195, in _current_revision_from_db
      with engine.connect() as conn:
           ^^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py", line 3293, in connect
      return self._connection_cls(self)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py", line 145, in __init__
      Connection._handle_dbapi_exception_noconnection(
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py", line 2448, in _handle_dbapi_exception_noconnection
      raise sqlalchemy_exception.with_traceback(exc_info[2]) from e
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py", line 143, in __init__
      self._dbapi_connection = engine.raw_connection()
                               ^^^^^^^^^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py", line 3317, in raw_connection
      return self.pool.connect()
             ^^^^^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py", line 448, in connect
      return _ConnectionFairy._checkout(self)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py", line 1272, in _checkout
      fairy = _ConnectionRecord.checkout(pool)
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py", line 712, in checkout
      rec = pool._do_get()
            ^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/sqlalchemy/pool/impl.py", line 177, in _do_get
      with util.safe_reraise():
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/sqlalchemy/util/langhelpers.py", line 121, in __exit__
      raise exc_value.with_traceback(exc_tb)
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/sqlalchemy/pool/impl.py", line 175, in _do_get
      return self._create_connection()
             ^^^^^^^^^^^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py", line 389, in _create_connection
      return _ConnectionRecord(self)
             ^^^^^^^^^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py", line 674, in __init__
      self.__connect()
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py", line 900, in __connect
      with util.safe_reraise():
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/sqlalchemy/util/langhelpers.py", line 121, in __exit__
      raise exc_value.with_traceback(exc_tb)
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py", line 896, in __connect
      self.dbapi_connection = connection = pool._invoke_creator(self)
                                           ^^^^^^^^^^^^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/sqlalchemy/engine/create.py", line 667, in connect
      return dialect.connect(*cargs_tup, **cparams)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/sqlalchemy/engine/default.py", line 630, in connect
      return self.loaded_dbapi.connect(*cargs, **cparams)  # type: ignore[no-any-return]  # NOQA: E501
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/psycopg/connection.py", line 122, in connect
      raise last_ex.with_traceback(None)
  sqlalchemy.exc.OperationalError: (psycopg.OperationalError) connection failed: connection to server at "127.0.0.1", port 1 failed: FATAL:  password authentication failed for user "blocked"
  (Background on this error at: https://sqlalche.me/e/20/e3q8)
  __ TestMergeItem.test_rebase_success_continues_to_dry_run_with_worktree_path ___
  self = <sqlalchemy.engine.base.Connection object at 0x7985d368ac60>
  engine = Engine(postgresql+psycopg://blocked:***@127.0.0.1:1/iw_orch_test_blocked)
  connection = None, _has_events = None, _allow_revalidate = True
  _allow_autobegin = True
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
  _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
  cls = <class 'psycopg.Connection'>
  conninfo = 'host=127.0.0.1 dbname=iw_orch_test_blocked user=blocked password=blocked port=1 hostaddr=127.0.0.1'
  autocommit = False, prepare_threshold = 5
  context = <psycopg.adapt.AdaptersMap object at 0x7985d368a030>
  row_factory = None, cursor_factory = None
  kwargs = {'dbname': 'iw_orch_test_blocked', 'host': '127.0.0.1', 'password': 'blocked', 'port': 1, ...}
  params = {'dbname': 'iw_orch_test_blocked', 'host': '127.0.0.1', 'password': 'blocked', 'port': 1, ...}
  timeout = 130
      @classmethod
      def connect(
          cls,
          conninfo: str = "",
          *,
          autocommit: bool = False,
          prepare_threshold: int | None = 5,
          context: AdaptContext | None = None,
          row_factory: RowFactory[Row] | None = None,
          cursor_factory: type[Cursor[Row]] | None = None,
          **kwargs: ConnParam,
      ) -> Self:
          """
          Connect to a database server and return a new `Connection` instance.
          """
          params = cls._get_connection_params(conninfo, **kwargs)
          timeout = timeout_from_conninfo(params)
          rv = None
          attempts = conninfo_attempts(params)
          conn_errors: list[tuple[e.Error, str]] = []
          for attempt in attempts:
              tdescr = (attempt.get("host"), attempt.get("port"), attempt.get("hostaddr"))
              descr = "host: %r, port: %r, hostaddr: %r" % tdescr
              logger.debug("connection attempt: %s", descr)
              try:
                  conninfo = make_conninfo("", **attempt)
                  gen = cls._connect_gen(conninfo, timeout=timeout)
                  rv = waiting.wait_conn(gen, interval=_WAIT_INTERVAL)
              except e.Error as ex:
                  logger.debug("connection failed: %s: %s", descr, str(ex))
                  conn_errors.append((ex, descr))
              except e._NO_TRACEBACK as ex:
                  raise ex.with_traceback(None)
              else:
                  logger.debug("connection succeeded: %s", descr)
                  break
          if not rv:
              last_ex = conn_errors[-1][0]
              if len(conn_errors) == 1:
  >               raise last_ex.with_traceback(None)
  E               psycopg.OperationalError: connection failed: connection to server at "127.0.0.1", port 1 failed: FATAL:  password authentication failed for user "blocked"
  .venv/lib/python3.12/site-packages/psycopg/connection.py:122: OperationalError
  The above exception was the direct cause of the following exception:
  batch_id = 42
      def run_rollback(batch_id: int) -> PipelineResult:
          """Phase 3: Attempt alembic downgrade -1 on the live DB.
          On success → batch marked MIGRATION_ROLLED_BACK.
          On failure → merge_queue_frozen flag set, subsequent merges halted.
          """
          live_url = get_db_url()
          logger.info("[pipeline] Phase 3 rollback starting for batch %d", batch_id)
          try:
  >           result = safe_rollback(live_url, steps=1, batch_id=batch_id)
                       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  orch/daemon/migration_pipeline.py:179: 
  _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
  orch/db/safe_migrate.py:561: in rollback
      revision_from, stderr_tail, error_message = _run_alembic_downgrade(cfg, steps)
                                                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  orch/db/safe_migrate.py:316: in _run_alembic_downgrade
      revision_from = _current_revision_from_db(cfg.get_main_option("sqlalchemy.url") or "")
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  orch/db/safe_migrate.py:195: in _current_revision_from_db
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
  _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
  cls = <class 'psycopg.Connection'>
  conninfo = 'host=127.0.0.1 dbname=iw_orch_test_blocked user=blocked password=blocked port=1 hostaddr=127.0.0.1'
  autocommit = False, prepare_threshold = 5
  context = <psycopg.adapt.AdaptersMap object at 0x7985d368a030>
  row_factory = None, cursor_factory = None
  kwargs = {'dbname': 'iw_orch_test_blocked', 'host': '127.0.0.1', 'password': 'blocked', 'port': 1, ...}
  params = {'dbname': 'iw_orch_test_blocked', 'host': '127.0.0.1', 'password': 'blocked', 'port': 1, ...}
  timeout = 130
      @classmethod
      def connect(
          cls,
          conninfo: str = "",
          *,
          autocommit: bool = False,
          prepare_threshold: int | None = 5,
          context: AdaptContext | None = None,
          row_factory: RowFactory[Row] | None = None,
          cursor_factory: type[Cursor[Row]] | None = None,
          **kwargs: ConnParam,
      ) -> Self:
          """
          Connect to a database server and return a new `Connection` instance.
          """
          params = cls._get_connection_params(conninfo, **kwargs)
          timeout = timeout_from_conninfo(params)
          rv = None
          attempts = conninfo_attempts(params)
          conn_errors: list[tuple[e.Error, str]] = []
          for attempt in attempts:
              tdescr = (attempt.get("host"), attempt.get("port"), attempt.get("hostaddr"))
              descr = "host: %r, port: %r, hostaddr: %r" % tdescr
              logger.debug("connection attempt: %s", descr)
              try:
                  conninfo = make_conninfo("", **attempt)
                  gen = cls._connect_gen(conninfo, timeout=timeout)
                  rv = waiting.wait_conn(gen, interval=_WAIT_INTERVAL)
              except e.Error as ex:
                  logger.debug("connection failed: %s: %s", descr, str(ex))
                  conn_errors.append((ex, descr))
              except e._NO_TRACEBACK as ex:
                  raise ex.with_traceback(None)
              else:
                  logger.debug("connection succeeded: %s", descr)
                  break
          if not rv:
              last_ex = conn_errors[-1][0]
              if len(conn_errors) == 1:
  >               raise last_ex.with_traceback(None)
  E               sqlalchemy.exc.OperationalError: (psycopg.OperationalError) connection failed: connection to server at "127.0.0.1", port 1 failed: FATAL:  password authentication failed for user "blocked"
  E               (Background on this error at: https://sqlalche.me/e/20/e3q8)
  .venv/lib/python3.12/site-packages/psycopg/connection.py:122: OperationalError
  During handling of the above exception, another exception occurred:
  self = <sqlalchemy.engine.base.Connection object at 0x7985d368a4b0>
  engine = Engine(postgresql+psycopg://blocked:***@127.0.0.1:1/iw_orch_test_blocked)
  connection = None, _has_events = None, _allow_revalidate = True
  _allow_autobegin = True
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
  _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
  cls = <class 'psycopg.Connection'>
  conninfo = 'host=127.0.0.1 dbname=iw_orch_test_blocked user=blocked password=blocked port=1 hostaddr=127.0.0.1'
  autocommit = False, prepare_threshold = 5
  context = <psycopg.adapt.AdaptersMap object at 0x7985d86d1670>
  row_factory = None, cursor_factory = None
  kwargs = {'dbname': 'iw_orch_test_blocked', 'host': '127.0.0.1', 'password': 'blocked', 'port': 1, ...}
  params = {'dbname': 'iw_orch_test_blocked', 'host': '127.0.0.1', 'password': 'blocked', 'port': 1, ...}
  timeout = 130
      @classmethod
      def connect(
          cls,
          conninfo: str = "",
          *,
          autocommit: bool = False,
          prepare_threshold: int | None = 5,
          context: AdaptContext | None = None,
          row_factory: RowFactory[Row] | None = None,
          cursor_factory: type[Cursor[Row]] | None = None,
          **kwargs: ConnParam,
      ) -> Self:
          """
          Connect to a database server and return a new `Connection` instance.
          """
          params = cls._get_connection_params(conninfo, **kwargs)
          timeout = timeout_from_conninfo(params)
          rv = None
          attempts = conninfo_attempts(params)
          conn_errors: list[tuple[e.Error, str]] = []
          for attempt in attempts:
              tdescr = (attempt.get("host"), attempt.get("port"), attempt.get("hostaddr"))
              descr = "host: %r, port: %r, hostaddr: %r" % tdescr
              logger.debug("connection attempt: %s", descr)
              try:
                  conninfo = make_conninfo("", **attempt)
                  gen = cls._connect_gen(conninfo, timeout=timeout)
                  rv = waiting.wait_conn(gen, interval=_WAIT_INTERVAL)
              except e.Error as ex:
                  logger.debug("connection failed: %s: %s", descr, str(ex))
                  conn_errors.append((ex, descr))
              except e._NO_TRACEBACK as ex:
                  raise ex.with_traceback(None)
              else:
                  logger.debug("connection succeeded: %s", descr)
                  break
          if not rv:
              last_ex = conn_errors[-1][0]
              if len(conn_errors) == 1:
  >               raise last_ex.with_traceback(None)
  E               psycopg.OperationalError: connection failed: connection to server at "127.0.0.1", port 1 failed: FATAL:  password authentication failed for user "blocked"
  .venv/lib/python3.12/site-packages/psycopg/connection.py:122: OperationalError
  The above exception was the direct cause of the following exception:
  self = <unit.test_merge_queue.TestMergeItem object at 0x7985d92dd460>
      def test_rebase_success_continues_to_dry_run_with_worktree_path(self):
          db = MagicMock()
          item = make_batch_item("F-00001", worktree_info={"path": "/wt/F-00001"})
          item.batch_id = 42
          from orch.daemon.migration_rebase import RebaseResult
          from orch.db.safe_migrate import DryRunResult
          mock_rebase_result = RebaseResult(
              success=True,
              rebased=True,
              rewrites=[],
              worktree_base_sha="abc123",
              current_main_sha="def456",
              message="Rebase ok",
              error_message=None,
          )
          mock_dry_result = DryRunResult(
              revisions_applied=["abc123"],
              success=True,
              duration_ms=500,
              stdout_tail="",
              stderr_tail="",
              error_message=None,
          )
          with (
              patch("orch.daemon.merge_queue.run_pre_merge_rebase", return_value=mock_rebase_result),
              patch(
                  "orch.daemon.merge_queue.run_pre_merge_dry_run", return_value=mock_dry_result
              ) as mock_dry,
              patch("orch.daemon.merge_queue.subprocess.run") as mock_run,
              patch("orch.daemon.merge_queue._cleanup_worktree"),
          ):
              mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
  >           _merge_item(db, item, "test-proj", make_project_config())
  tests/unit/test_merge_queue.py:304: 
  _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
  orch/daemon/merge_queue.py:243: in _merge_item
      rollback_result = run_rollback(int_batch_id)
                        ^^^^^^^^^^^^^^^^^^^^^^^^^^
  orch/daemon/migration_pipeline.py:205: in run_rollback
      set_merge_queue_frozen(
  orch/daemon/migration_pipeline.py:286: in set_merge_queue_frozen
      session.commit()
  .venv/lib/python3.12/site-packages/sqlalchemy/orm/session.py:2030: in commit
      trans.commit(_to_root=True)
  <string>:2: in commit
      ???
  .venv/lib/python3.12/site-packages/sqlalchemy/orm/state_changes.py:137: in _go
      ret_value = fn(self, *arg, **kw)
                  ^^^^^^^^^^^^^^^^^^^^
  .venv/lib/python3.12/site-packages/sqlalchemy/orm/session.py:1311: in commit
      self._prepare_impl()
  <string>:2: in _prepare_impl
      ???
  .venv/lib/python3.12/site-packages/sqlalchemy/orm/state_changes.py:137: in _go
      ret_value = fn(self, *arg, **kw)
                  ^^^^^^^^^^^^^^^^^^^^
  .venv/lib/python3.12/site-packages/sqlalchemy/orm/session.py:1286: in _prepare_impl
      self.session.flush()
  .venv/lib/python3.12/site-packages/sqlalchemy/orm/session.py:4331: in flush
      self._flush(objects)
  .venv/lib/python3.12/site-packages/sqlalchemy/orm/session.py:4466: in _flush
      with util.safe_reraise():
  .venv/lib/python3.12/site-packages/sqlalchemy/util/langhelpers.py:121: in __exit__
      raise exc_value.with_traceback(exc_tb)
  .venv/lib/python3.12/site-packages/sqlalchemy/orm/session.py:4427: in _flush
      flush_context.execute()
  .venv/lib/python3.12/site-packages/sqlalchemy/orm/unitofwork.py:466: in execute
      rec.execute(self)
  .venv/lib/python3.12/site-packages/sqlalchemy/orm/unitofwork.py:642: in execute
      util.preloaded.orm_persistence.save_obj(
  .venv/lib/python3.12/site-packages/sqlalchemy/orm/persistence.py:60: in save_obj
      for (
  .venv/lib/python3.12/site-packages/sqlalchemy/orm/persistence.py:223: in _organize_states_for_save
      for state, dict_, mapper, connection in _connections_for_states(
  .venv/lib/python3.12/site-packages/sqlalchemy/orm/persistence.py:1759: in _connections_for_states
      connection = uowtransaction.transaction.connection(base_mapper)
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  <string>:2: in connection
      ???
  .venv/lib/python3.12/site-packages/sqlalchemy/orm/state_changes.py:137: in _go
      ret_value = fn(self, *arg, **kw)
                  ^^^^^^^^^^^^^^^^^^^^
  .venv/lib/python3.12/site-packages/sqlalchemy/orm/session.py:1037: in connection
      return self._connection_for_bind(bind, execution_options)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  <string>:2: in _connection_for_bind
      ???
  .venv/lib/python3.12/site-packages/sqlalchemy/orm/state_changes.py:137: in _go
      ret_value = fn(self, *arg, **kw)
                  ^^^^^^^^^^^^^^^^^^^^
  .venv/lib/python3.12/site-packages/sqlalchemy/orm/session.py:1173: in _connection_for_bind
      conn = self._parent._connection_for_bind(
  <string>:2: in _connection_for_bind
      ???
  .venv/lib/python3.12/site-packages/sqlalchemy/orm/state_changes.py:137: in _go
      ret_value = fn(self, *arg, **kw)
                  ^^^^^^^^^^^^^^^^^^^^
  .venv/lib/python3.12/site-packages/sqlalchemy/orm/session.py:1187: in _connection_for_bind
      conn = bind.connect()
             ^^^^^^^^^^^^^^
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
  _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
  cls = <class 'psycopg.Connection'>
  conninfo = 'host=127.0.0.1 dbname=iw_orch_test_blocked user=blocked password=blocked port=1 hostaddr=127.0.0.1'
  autocommit = False, prepare_threshold = 5
  context = <psycopg.adapt.AdaptersMap object at 0x7985d86d1670>
  row_factory = None, cursor_factory = None
  kwargs = {'dbname': 'iw_orch_test_blocked', 'host': '127.0.0.1', 'password': 'blocked', 'port': 1, ...}
  params = {'dbname': 'iw_orch_test_blocked', 'host': '127.0.0.1', 'password': 'blocked', 'port': 1, ...}
  timeout = 130
      @classmethod
      def connect(
          cls,
          conninfo: str = "",
          *,
          autocommit: bool = False,
          prepare_threshold: int | None = 5,
          context: AdaptContext | None = None,
          row_factory: RowFactory[Row] | None = None,
          cursor_factory: type[Cursor[Row]] | None = None,
          **kwargs: ConnParam,
      ) -> Self:
          """
          Connect to a database server and return a new `Connection` instance.
          """
          params = cls._get_connection_params(conninfo, **kwargs)
          timeout = timeout_from_conninfo(params)
          rv = None
          attempts = conninfo_attempts(params)
          conn_errors: list[tuple[e.Error, str]] = []
          for attempt in attempts:
              tdescr = (attempt.get("host"), attempt.get("port"), attempt.get("hostaddr"))
              descr = "host: %r, port: %r, hostaddr: %r" % tdescr
              logger.debug("connection attempt: %s", descr)
              try:
                  conninfo = make_conninfo("", **attempt)
                  gen = cls._connect_gen(conninfo, timeout=timeout)
                  rv = waiting.wait_conn(gen, interval=_WAIT_INTERVAL)
              except e.Error as ex:
                  logger.debug("connection failed: %s: %s", descr, str(ex))
                  conn_errors.append((ex, descr))
              except e._NO_TRACEBACK as ex:
                  raise ex.with_traceback(None)
              else:
                  logger.debug("connection succeeded: %s", descr)
                  break
          if not rv:
              last_ex = conn_errors[-1][0]
              if len(conn_errors) == 1:
  >               raise last_ex.with_traceback(None)
  E               sqlalchemy.exc.OperationalError: (psycopg.OperationalError) connection failed: connection to server at "127.0.0.1", port 1 failed: FATAL:  password authentication failed for user "blocked"
  E               (Background on this error at: https://sqlalche.me/e/20/e3q8)
  .venv/lib/python3.12/site-packages/psycopg/connection.py:122: OperationalError
  ------------------------------ Captured log call -------------------------------
  WARNING  orch.daemon.worktree_compose:worktree_compose.py:239 [worktree_compose] Failed to write daemon event: (psycopg.OperationalError) connection failed: connection to server at "127.0.0.1", port 1 failed: FATAL:  password authentication failed for user "blocked"
  (Background on this error at: https://sqlalche.me/e/20/e3q8)
  WARNING  orch.daemon.migration_pipeline:migration_pipeline.py:133 [pipeline] Phase 2 apply failed for batch 42 — triggering rollback
  WARNING  orch.daemon.merge_queue:merge_queue.py:238 [test-proj] Phase 2 apply failed for batch 42 — running rollback
  ERROR    orch.daemon.migration_pipeline:migration_pipeline.py:204 [pipeline] Phase 3 rollback error for batch 42
  Traceback (most recent call last):
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py", line 143, in __init__
      self._dbapi_connection = engine.raw_connection()
                               ^^^^^^^^^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py", line 3317, in raw_connection
      return self.pool.connect()
             ^^^^^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py", line 448, in connect
      return _ConnectionFairy._checkout(self)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py", line 1272, in _checkout
      fairy = _ConnectionRecord.checkout(pool)
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py", line 712, in checkout
      rec = pool._do_get()
            ^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/sqlalchemy/pool/impl.py", line 177, in _do_get
      with util.safe_reraise():
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/sqlalchemy/util/langhelpers.py", line 121, in __exit__
      raise exc_value.with_traceback(exc_tb)
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/sqlalchemy/pool/impl.py", line 175, in _do_get
      return self._create_connection()
             ^^^^^^^^^^^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py", line 389, in _create_connection
      return _ConnectionRecord(self)
             ^^^^^^^^^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py", line 674, in __init__
      self.__connect()
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py", line 900, in __connect
      with util.safe_reraise():
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/sqlalchemy/util/langhelpers.py", line 121, in __exit__
      raise exc_value.with_traceback(exc_tb)
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py", line 896, in __connect
      self.dbapi_connection = connection = pool._invoke_creator(self)
                                           ^^^^^^^^^^^^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/sqlalchemy/engine/create.py", line 667, in connect
      return dialect.connect(*cargs_tup, **cparams)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/sqlalchemy/engine/default.py", line 630, in connect
      return self.loaded_dbapi.connect(*cargs, **cparams)  # type: ignore[no-any-return]  # NOQA: E501
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/psycopg/connection.py", line 122, in connect
      raise last_ex.with_traceback(None)
  psycopg.OperationalError: connection failed: connection to server at "127.0.0.1", port 1 failed: FATAL:  password authentication failed for user "blocked"
  The above exception was the direct cause of the following exception:
  Traceback (most recent call last):
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/orch/daemon/migration_pipeline.py", line 179, in run_rollback
      result = safe_rollback(live_url, steps=1, batch_id=batch_id)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/orch/db/safe_migrate.py", line 561, in rollback
      revision_from, stderr_tail, error_message = _run_alembic_downgrade(cfg, steps)
                                                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/orch/db/safe_migrate.py", line 316, in _run_alembic_downgrade
      revision_from = _current_revision_from_db(cfg.get_main_option("sqlalchemy.url") or "")
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/orch/db/safe_migrate.py", line 195, in _current_revision_from_db
      with engine.connect() as conn:
           ^^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py", line 3293, in connect
      return self._connection_cls(self)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py", line 145, in __init__
      Connection._handle_dbapi_exception_noconnection(
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py", line 2448, in _handle_dbapi_exception_noconnection
      raise sqlalchemy_exception.with_traceback(exc_info[2]) from e
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py", line 143, in __init__
      self._dbapi_connection = engine.raw_connection()
                               ^^^^^^^^^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/sqlalchemy/engine/base.py", line 3317, in raw_connection
      return self.pool.connect()
             ^^^^^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py", line 448, in connect
      return _ConnectionFairy._checkout(self)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py", line 1272, in _checkout
      fairy = _ConnectionRecord.checkout(pool)
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py", line 712, in checkout
      rec = pool._do_get()
            ^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/sqlalchemy/pool/impl.py", line 177, in _do_get
      with util.safe_reraise():
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/sqlalchemy/util/langhelpers.py", line 121, in __exit__
      raise exc_value.with_traceback(exc_tb)
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/sqlalchemy/pool/impl.py", line 175, in _do_get
      return self._create_connection()
             ^^^^^^^^^^^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py", line 389, in _create_connection
      return _ConnectionRecord(self)
             ^^^^^^^^^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py", line 674, in __init__
      self.__connect()
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py", line 900, in __connect
      with util.safe_reraise():
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/sqlalchemy/util/langhelpers.py", line 121, in __exit__
      raise exc_value.with_traceback(exc_tb)
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/sqlalchemy/pool/base.py", line 896, in __connect
      self.dbapi_connection = connection = pool._invoke_creator(self)
                                           ^^^^^^^^^^^^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/sqlalchemy/engine/create.py", line 667, in connect
      return dialect.connect(*cargs_tup, **cparams)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/sqlalchemy/engine/default.py", line 630, in connect
      return self.loaded_dbapi.connect(*cargs, **cparams)  # type: ignore[no-any-return]  # NOQA: E501
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    File "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/psycopg/connection.py", line 122, in connect
      raise last_ex.with_traceback(None)
  sqlalchemy.exc.OperationalError: (psycopg.OperationalError) connection failed: connection to server at "127.0.0.1", port 1 failed: FATAL:  password authentication failed for user "blocked"
  (Background on this error at: https://sqlalche.me/e/20/e3q8)
  .venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1434
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/_pytest/config/__init__.py:1434: PytestConfigWarning: Unknown config option: env
      self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")
  orch/db/models.py:175
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/orch/db/models.py:175: PytestCollectionWarning: cannot collect test class 'TestRunStatus' because it has a __init__ constructor (from: tests/unit/test_test_runner.py)
      class TestRunStatus(enum.Enum):
  tests/unit/test_code_qa_router_rerender.py: 1 warning
  tests/unit/test_qa_engine_hybrid_retrieval.py: 2 warnings
  tests/unit/test_qa_engine_render_cache.py: 4 warnings
  tests/unit/test_qa_v2_prompt_layout.py: 8 warnings
  tests/unit/test_qa_v2_relevance_filter_eval.py: 5 warnings
    <string>:9: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
  tests/unit/test_code_ui_routes.py::TestCodeIndexStream::test_sse_stream_returns_idle_when_no_runner_in_registry
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/.venv/lib/python3.12/site-packages/starlette/testclient.py:439: DeprecationWarning: You should not use the 'timeout' argument with the TestClient. See https://github.com/Kludex/starlette/issues/1108 for more information.
      warnings.warn(
  tests/unit/test_qa_engine.py::TestAnswerStream::test_answer_stream_falls_back_when_module_filter_empty
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/tests/unit/test_qa_engine.py:625: RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited
      async for token in engine.answer_stream(
    Enable tracemalloc to get traceback where the object was allocated.
    See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.
  tests/unit/test_qa_engine.py::TestAnswerStream::test_answer_stream_translates_dotted_module_path_to_filesystem_filter
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/tests/unit/test_qa_engine.py:723: RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited
      async for token in engine.answer_stream(
    Enable tracemalloc to get traceback where the object was allocated.
    See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.
  tests/unit/test_qa_engine.py::TestAnswerStream::test_answer_stream_does_not_fall_back_when_module_filter_nonempty
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/tests/unit/test_qa_engine.py:819: RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited
      async for token in engine.answer_stream(
    Enable tracemalloc to get traceback where the object was allocated.
    See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.
  tests/unit/test_qa_engine.py::TestAnswerStream::test_answer_stream_does_not_fall_back_for_architecture_context
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00022/tests/unit/test_qa_engine.py:905: RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited
      async for token in engine.answer_stream(
    Enable tracemalloc to get traceback where the object was allocated.
    See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.
  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  make: *** [Makefile:36: test-unit] Error 1
  The unit tests ran with 2 failures. Both failures appear to be related to database connection issues in the test mocks (trying to connect to `127.0.0.1:1` with user "blocked" instead of using proper testcontainers). These seem to be pre-existing test infrastructure issues rather than issues with the CR-00022 changes.
  Let me create the report and mark the step as failed.
  $ mkdir -p ai-dev/active/CR-00022/reports
  (no output)
  ← Write ai-dev/active/CR-00022/reports/CR-00022_S25_QvGate_report.md
  Wrote file successfully.


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
