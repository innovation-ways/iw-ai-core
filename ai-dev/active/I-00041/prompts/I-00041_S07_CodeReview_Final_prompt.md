# I-00041_S07_CodeReview_Final_prompt

**Work Item**: I-00041 — Connection-layer guard against integration tests writing to the live orchestration DB
**Review Step**: S07 (Final Review)
**Implementation Steps Reviewed**: S01, S03, S05

---

## ⛔ Docker is off-limits

Same rules as previous prompts. Read-only introspection only.

## Input Files

- `ai-dev/active/I-00041/I-00041_Issue_Design.md`
- `ai-dev/active/I-00041/reports/I-00041_S01_Backend_report.md`
- `ai-dev/active/I-00041/reports/I-00041_S02_CodeReview_Backend_report.md`
- `ai-dev/active/I-00041/reports/I-00041_S03_Backend_report.md`
- `ai-dev/active/I-00041/reports/I-00041_S04_CodeReview_Backend_report.md`
- `ai-dev/active/I-00041/reports/I-00041_S05_Tests_report.md`
- `ai-dev/active/I-00041/reports/I-00041_S06_CodeReview_Tests_report.md`
- All modified/new files:
  - S01 (chokepoint): `orch/db/live_db_guard.py` (new),
    `orch/db/session.py`, `orch/db/safe_migrate.py`,
    `orch/daemon/main.py` (`create_session_factory` only),
    `orch/daemon/migration_pipeline.py`,
    `orch/daemon/migration_rebase.py`,
    `orch/daemon/worktree_compose.py`,
    `orch/cli/merge_queue_commands.py`
  - S03 (env-var arming + executor strip): `tests/conftest.py`,
    `orch/daemon/__main__.py` (NOT `main.py`),
    `orch/cli/migrations_commands.py`,
    `orch/daemon/batch_manager.py`,
    `orch/daemon/fix_cycle.py`,
    `orch/daemon/doc_job_poller.py`
  - S05 (tests): `tests/unit/test_live_db_guard.py`,
    `tests/unit/test_agent_subprocess_env.py`,
    `tests/integration/test_live_db_guard_reproduction.py`,
    `tests/integration/test_migration_pipeline.py`

## Output Files

- Report: `ai-dev/active/I-00041/reports/I-00041_S07_CodeReview_Final_report.md`

## Context

You are the **last quality gate before QV**. Per-step reviews caught
local issues; this review verifies the system as a whole behaves correctly
and the design's acceptance criteria are met.

Specifically, verify the **defense-in-depth chain** holds end-to-end:

1. **Connection layer**: every engine creation in `orch/` routes through
   `safe_create_engine` → `assert_engine_url_allowed`. (S01)
2. **Test polarity**: the conftest sets `IW_CORE_TEST_CONTEXT=true`
   session-wide, can't be silently stripped. (S03)
3. **Operator/daemon arming**: only the right entry points set the
   allow-list flags, scoped to their own processes. (S03)
4. **Allow-list strip at agent/gate launch**: the daemon's
   `_agent_subprocess_env()` helper pops `IW_CORE_DAEMON_CONTEXT` and
   `IW_CORE_OPERATOR_APPLY` from every agent or QV-gate child env, so
   the daemon's own allow-list cannot leak via `os.environ` inheritance.
   This is the link that was missing in the v1 design and is the
   canonical attack path. (S03 R5)
5. **Test cleanup**: the offending file (`test_migration_pipeline.py`)
   no longer hardcodes `batch_id = 42` and the regression suite locks
   in the new behaviour. (S05)

A break in any link of the chain re-opens the bug. Your job is to verify
no link is missing.

## Acceptance Criteria Verification

Walk through each AC from the design doc and verify it is met:

### AC1: Bug is fixed

> Given a pytest process with `IW_CORE_TEST_CONTEXT=true` and code that
> calls `create_engine(<live URL>)`, a `LiveDbConnectionRefused` is raised.

- [ ] Repro test (`test_subprocess_in_test_context_cannot_connect_to_live_db`)
      passes.
- [ ] Manually run the subprocess yourself and confirm the refusal:
      ```bash
      IW_CORE_TEST_CONTEXT=true uv run python -c "
      from orch.db.session import safe_create_engine
      e = safe_create_engine('postgresql://iw_orch:iw_orch@localhost:5433/iw_orch')
      e.connect()
      "
      ```
      Expect non-zero exit + `LiveDbConnectionRefused` in stderr.

### AC2: Daemon and operator paths still work

> Given the daemon process with `IW_CORE_DAEMON_CONTEXT=true`, the
> connection succeeds.

- [ ] `IW_CORE_DAEMON_CONTEXT=true uv run python -c "from orch.db.session
      import SessionLocal; s = SessionLocal(); s.close()"` succeeds.
- [ ] `iw migrations list-pending` (operator command, no flag set)
      still returns the expected output.
- [ ] Daemon process status (read-only): `./ai-core.sh status` shows
      daemon healthy. Do NOT restart it.

### AC3: Reproduction test exists

- [ ] `tests/integration/test_live_db_guard_reproduction.py` exists,
      contains the canonical reproduction, and passes.

### AC4: Mock-bypass path is closed

- [ ] Running `pytest tests/integration/test_migration_pipeline.py -v`
      against the post-fix code does NOT add new rows to live
      `pending_migration_log`. Verify by snapshot before/after if you
      have operator opt-in, or by reading the test code top-down to
      confirm every code path is mocked.

## Cross-Cutting Reviews

### Layer boundaries

- [ ] `orch/db/live_db_guard.py` does NOT import from `orch/daemon/`,
      `orch/cli/`, or `dashboard/`.
- [ ] `tests/conftest.py` does not import from `orch/daemon/` (it doesn't
      need to and shouldn't).
- [ ] No circular imports introduced. Run
      `uv run python -c "import orch.db.session, orch.db.safe_migrate,
      orch.daemon.main, orch.cli.migrations_commands; print('OK')"`
      and confirm no errors.

### Single chokepoint discipline

- [ ] The canonical post-fix invariant grep:
      ```bash
      grep -rnE "create_engine\(" orch/ --include='*.py' \
        | grep -v "live_db_guard" \
        | grep -v "safe_create_engine"
      ```
      Must show ONE match — `orch/db/session.py` inside
      `safe_create_engine`'s body. Any other match is a missed S01 R3
      site and a regression of the chokepoint invariant.
- [ ] All eight S01-targeted sites confirmed routed:
      - `orch/db/safe_migrate.py` lines 170, 200, 312, 346
      - `orch/daemon/main.py` line 64 (`create_session_factory`)
      - `orch/daemon/migration_pipeline.py` lines 231, 266
      - `orch/daemon/migration_rebase.py` lines 210, 239
      - `orch/daemon/worktree_compose.py` line 224
      - `orch/cli/merge_queue_commands.py` line 51
- [ ] In `tests/`, raw `create_engine` calls are confined to fixtures that
      target testcontainers (verify by sampling).

### Backwards compatibility

- [ ] `IW_CORE_AGENT_CONTEXT` is honoured but deprecated. Calling
      `_assert_not_agent_context(...)` raises a `DeprecationWarning`
      AND still enforces the guard.
- [ ] No alembic migration file added. `git diff --stat
      orch/db/migrations/versions/` shows zero changes.
- [ ] Public API of `orch.db.session` (`engine`, `SessionLocal`,
      `get_session`) unchanged.
- [ ] `iw migrations apply --i-am-operator` still requires the
      `--i-am-operator` flag — the new env var is set AFTER the flag
      check, not as a replacement.

### Documentation alignment

- [ ] The design doc's AC1-AC4 each map to at least one passing test.
- [ ] The Regression Prevention section is accurate (the three
      structural changes — single chokepoint, opt-in polarity,
      fingerprint match — are all implemented).
- [ ] No "TBD" placeholders remain in the design doc.
- [ ] Reports for S01, S03, S05 each show `tests_passed: true` and
      `completion_status: complete`.

### Risk hot spots

- [ ] **The dashboard process is unchanged.** Confirm. The dashboard
      runs under the daemon's environment when launched via
      `./ai-core.sh start`, which inherits `IW_CORE_DAEMON_CONTEXT=true`.
      If launched standalone, the guard's "no flag set" default-allow
      preserves current behaviour. Note any concern but do not block on
      this — a follow-up incident can address standalone-launch hardening.
- [ ] **Subprocess env propagation (CRITICAL — primary attack path)**:
      verify the `_agent_subprocess_env()` helper in
      `orch/daemon/batch_manager.py` is used at all five agent/gate
      launch sites:
      ```bash
      grep -nE 'env\s*=\s*\{?\*\*\s*os\.environ' \
        orch/daemon/batch_manager.py \
        orch/daemon/fix_cycle.py \
        orch/daemon/doc_job_poller.py
      ```
      Must show ZERO matches at the documented agent/gate launch sites.
      Manually run:
      ```bash
      IW_CORE_DAEMON_CONTEXT=true IW_CORE_OPERATOR_APPLY=true uv run python -c "
      from orch.daemon.batch_manager import _agent_subprocess_env
      env = _agent_subprocess_env()
      assert 'IW_CORE_DAEMON_CONTEXT' not in env
      assert 'IW_CORE_OPERATOR_APPLY' not in env
      assert env.get('IW_CORE_AGENT_CONTEXT') == 'true'
      print('strip + arm OK')
      "
      ```
      A break here re-opens the bug for the canonical attack path
      (daemon-launched agent running `make test-unit`). This is a
      CRITICAL finding if not closed.
- [ ] **Test concurrency**: with pytest-xdist, all worker processes
      share `os.environ` if forked, but spawn under separate process
      images. Confirm the session fixture's `os.environ` setting
      propagates correctly to all workers (xdist's worker startup
      inherits parent env by default — but verify with one parallel
      run).

### Test quality

- [ ] Every assertion in the new tests checks a SPECIFIC value, not
      just shape. Sample five at random and ask "would this pass if
      the function returned None / empty / wrong value?"
- [ ] Reproduction test would have FAILED against the pre-fix code
      (no connection-layer guard). Confirm by simulating: temporarily
      remove the `assert_engine_url_allowed` call from
      `safe_create_engine`, run the repro test, observe failure, restore.
      OR confirm by reasoning if the diff is too large to revert safely.

## Output Report

Findings list with severity (CRITICAL / HIGH / MEDIUM / LOW / INFO),
`file:line`, and a one-line verdict per item. Group findings by category
(Acceptance / Layer / Chokepoint / Backwards-Compat / Risk / Test-Quality).

End with:

- Overall verdict: `PASS` / `NEEDS_FIX` / `BLOCKED`.
- A short paragraph summarising whether the defense-in-depth chain is
  intact end-to-end, or naming the specific link that is broken.
- The appropriate `iw step-done` or `iw step-fail` call.

## Lifecycle Commands

When you START:
```bash
uv run iw step-start I-00041 --step S07
```

When you COMPLETE:
```bash
mkdir -p ai-dev/active/I-00041/reports
uv run iw step-done I-00041 --step S07 --report ai-dev/active/I-00041/reports/I-00041_S07_CodeReview_Final_report.md
```
