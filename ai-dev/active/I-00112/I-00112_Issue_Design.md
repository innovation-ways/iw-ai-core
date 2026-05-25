# I-00112: Keep-Alive Scheduler logs `status=success` for silent no-op CLI fires; stdout/stderr/elapsed never captured

**Type**: Issue
**Severity**: Medium
**Created**: 2026-05-25
**Reported By**: Operator (cross-checked DB log vs claude.ai/usage page after 05:00 fire on 2026-05-25 did not anchor the Sonnet 5h window)
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt. This incident does NOT touch docker.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. **This incident adds one new Alembic migration** that appends four nullable columns to `keep_alive_runs`. S01 (Database) generates the revision file; the daemon will apply it on next reload.

## Description

The Keep-Alive Scheduler considers a slot fire successful whenever the spawned `claude` CLI exits with returncode 0, discarding stdout, stderr, elapsed time, and the exact returncode value. As a result, an invocation that exited 0 *without actually posting a message to the Anthropic backend* is recorded as `status=success` in `keep_alive_runs` and rendered as a green "Success" badge on `/system/keep-alive` — but the user's claude.ai/usage page shows no message at that timestamp and the 5h usage window is never anchored. The scheduler's only purpose is anchoring usage windows, so a silent no-op completely defeats the feature while looking healthy.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Notably:
- `orch/` is the daemon's home — see `orch/CLAUDE.md`.
- Dashboard routers are thin and Jinja2 fragments live under `dashboard/templates/fragments/` (see `dashboard/CLAUDE.md`); a Tailwind rebuild via `make css` is needed only if new Tailwind utility classes are introduced.
- Tests under `tests/dashboard/` use the FastAPI `client` fixture (see `tests/CLAUDE.md`); a test placed under `tests/unit/` or `tests/integration/` cannot use it (I-00067).
- pytest-randomly is on — every new test must be order-independent.
- Alembic revisions must be committed (not just staged) before the daemon's worktree-launch picks them up — see CLAUDE.md "NEVER apply an uncommitted Alembic migration" rule.

## Browser Evidence

`browser_verification: true`. Reproduction is non-interactive — the bug is the *absence* of distinguishing data on the recent-runs table, not a visual glitch. Evidence captured 2026-05-25 ~08:25 WEST against the live dashboard at `http://localhost:9900/system/keep-alive`:

- `ai-dev/active/I-00112/evidences/pre/I-00112-bug-evidence.png` — full keep-alive page (configuration + timeline + slots).
- `ai-dev/active/I-00112/evidences/pre/I-00112-recent-executions-table.png` — close-up of the **Recent Executions** table. The top row `2026-05-25 04:05:00 | 05:00 | Success` is the silent no-op the operator caught: the row claims success but claude.ai/usage records no Sonnet message at that timestamp and the 5h window was not anchored.
- `ai-dev/active/I-00112/evidences/pre/I-00112-page-snapshot.yml` — Playwright accessibility snapshot of the page (includes every row currently rendered).

## Steps to Reproduce

1. Configure a slot in `/system/keep-alive` (or use an existing one). Confirm the daemon is running.
2. Wait until the slot's `time_hhmm` is within the daemon's 30-minute due window and let the poller fire.
3. Inspect the three independent observation surfaces:
   - DB: `SELECT slot_id, slot_time, status, error, fired_at FROM keep_alive_runs ORDER BY fired_at DESC LIMIT 1;` — status will be `success`, error will be NULL.
   - daemon log: `grep KeepAlive logs/daemon.log | tail -1` — `... status=success error=None`.
   - claude.ai/usage page — no Sonnet message at the fire's timestamp; the 5h Sonnet window does **not** start.

**Expected**: The daemon refuses to claim success unless there is affirmative evidence the API call landed (non-empty stdout AND elapsed time consistent with a real round-trip), and it persists the CLI's actual stdout/stderr/elapsed/returncode on every run so a human can audit the fire post-hoc.

**Actual**: `returncode == 0` ⇒ `status=success` with no captured details. A silent no-op is indistinguishable from a real fire on every internal surface.

## Browser Verification Script

The reproduction is observational, not interactive. To re-verify the pre-fix UI state:

```bash
playwright-cli kill-all
playwright-cli open "${IW_BROWSER_BASE_URL}/system/keep-alive"
playwright-cli snapshot           # confirms the "Recent Executions" table has only Fired At / Slot / Status columns
playwright-cli screenshot         # captures the table for evidence
playwright-cli close
```

Pre-fix expectation: the table has exactly three columns — `Fired At`, `Slot`, `Status`. Every row's status badge is green "Success" with no per-row signal as to whether the call actually landed.

## Root Cause Analysis

Three independent code paths conspire to lose information at the boundary:

1. **`orch/keep_alive_service.py:220-250` (`fire_claude`)** — calls `subprocess.run(["claude", "--model", model, "-p", message], capture_output=True, text=True, timeout=timeout)`, then inspects only `result.returncode`. stdout, stderr, and elapsed time are captured by the kernel but discarded by Python. Function signature is `tuple[bool, str | None]` — there is no room in the return type for diagnostic detail.

2. **`orch/daemon/keep_alive_poller.py:60-83` (`_fire_slot`)** — receives `(success, error)` and routes only the bool into `_log_run`. Even if `fire_claude` were enriched, the poller would still throw the extra information away here.

3. **`orch/daemon/keep_alive_poller.py:85-108` (`_log_run`)** — calls `log_run(db, slot_id=..., slot_time=..., status=..., error=...)` and emits one INFO log line. The DB model `KeepAliveRun` has columns `(id, slot_id, slot_time, status, error, fired_at)` — there is no place to write stdout/stderr/elapsed_ms/returncode even if the upstream code captured them.

4. **`dashboard/templates/fragments/keep_alive_runs.html`** — the Recent Executions fragment renders only `fired_at`, `slot_time`, and a status badge. There is no UI surface for the captured details.

**Why didn't existing tests catch it?** The unit and integration tests for `KeepAlivePoller` mock `fire_claude` to return `(True, None)` or `(False, "...")` and assert the matching `status` is written. They never probe what `fire_claude` itself silently drops — the entire diagnostic surface was outside the test boundary. The bug class is "we are not capturing enough information to *notice* the bug" — by definition, it is invisible to any test that only checks status strings.

**Empirical confirmation (2026-05-25, this session):** running the exact subprocess invocation `claude --model claude-sonnet-4-6 -p "Quick probe..."` against the daemon's auth (`/home/sergiog/.claude/.credentials.json`, `subscriptionType=max`) returns rc=0, prints the model's actual reply ("OK"), and takes ~4 s — proving the CLI itself is healthy and the bug is not auth/env drift but the daemon's success-detection contract.

## Affected Components

| Component | File | Impact |
|-----------|------|--------|
| Service — fire path | `orch/keep_alive_service.py:220-250` | `fire_claude` discards stdout/stderr/elapsed; only returncode bool surfaces |
| Poller — fire dispatch | `orch/daemon/keep_alive_poller.py:60-83` | `_fire_slot` carries only bool forward |
| Poller — run logging | `orch/daemon/keep_alive_poller.py:85-108` | `_log_run` persists only status+error |
| ORM model | `orch/db/models.py` (`KeepAliveRun`) | No columns for stdout/stderr/elapsed_ms/returncode |
| Schema | `keep_alive_runs` table | Same — no columns for diagnostic detail |
| Dashboard — fragment | `dashboard/templates/fragments/keep_alive_runs.html` | Only renders fired_at/slot/status; no surface for diagnostic detail |
| Tests — coverage gap | `tests/unit/test_keep_alive_*` (existing) | Mocks past the boundary where the bug lives |

## Fix Plan

### Agents and Execution Order

> **Step-granularity rule**: each implementation step targets one cohesive concern. This fix has four such concerns — (a) schema + ORM, (b) backend service+poller success contract, (c) frontend rendering of the new fields, and (d) tests. They are split across S01/S03/S05/S07 so each gets its own per-agent code review.

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | Database | Generate Alembic revision adding four nullable columns to `keep_alive_runs`: `stdout TEXT`, `stderr TEXT`, `elapsed_ms INTEGER`, `returncode INTEGER`. Extend `KeepAliveRun` ORM model in `orch/db/models.py` with matching `Mapped[]` declarations. Do NOT touch `orch/keep_alive_service.py`, the poller, or any template — those are S03/S05. | — |
| S02 | CodeReview_Database | Per-agent review of S01 (migration + model only) | — |
| S03 | Backend | Refactor `fire_claude` to return a dataclass-style `FireResult` with fields `(returncode: int, stdout: str, stderr: str, elapsed_ms: int)`. Refactor `keep_alive_service.log_run` to accept and persist `stdout` / `stderr` / `elapsed_ms` / `returncode`. Refactor `KeepAlivePoller._fire_slot` and `_log_run` to plumb the new fields through. Apply the stricter success contract: `status='success'` requires `returncode == 0` AND `stdout.strip() != ""` AND `elapsed_ms >= 500`; otherwise `status='failed'` with the captured detail (and the existing single retry still applies for the rc!=0 branch). The 500 ms floor is a module-level named constant with a comment citing I-00112. Do NOT touch the migration, the model, the template, or test files. | — |
| S04 | CodeReview_Backend | Per-agent review of S03 (service + poller only) | — |
| S05 | Frontend | Extend `dashboard/templates/fragments/keep_alive_runs.html` to render two additional columns — **Elapsed** (`{{ elapsed_ms }} ms` or `—` when NULL) and **Output** (first ~80 chars of `stdout` with a `title` attribute carrying the full string, or `—` when NULL). Update `dashboard/routers/keep_alive.py` (only if needed to pass the extra fields — `get_recent_runs` already returns the ORM objects so the template can read them directly; verify before touching the router). Update `dashboard/templates/_partials/help/keep_alive.html` if it documents the columns. If new Tailwind utilities are introduced, run `make css` and commit the regenerated `dashboard/static/styles.css`. Do NOT touch any backend file or test file. | — |
| S06 | CodeReview_Frontend | Per-agent review of S05 (template + router only) | — |
| S07 | Tests | Create `tests/unit/test_keep_alive_poller_success_contract.py` with the six regression tests in **Test to Reproduce** below. Tests MUST mock `subprocess.run` (not `fire_claude`) so the success-contract logic itself is exercised. **NO** `make test-unit` / `make test-integration` — targeted file only. RED-exempt: S03 owns RED evidence (refactored type signature breaks existing mocks); S07 just documents per-test pre-S03 failure reasoning in its `notes`. | — |
| S08 | CodeReview_Tests | Per-agent review of S07 | — |
| S09 | CodeReview_Final | Cross-layer review of S01/S03/S05/S07 | — |
| S10 | qv-gate | `make lint` | — |
| S11 | qv-gate | `make format-check` | — |
| S12 | qv-gate | `make type-check` | — |
| S13 | qv-gate | `make arch-check` | — |
| S14 | qv-gate | `make security-sast` | — |
| S15 | qv-gate | `make migration-check` (round-trip the new revision) | — |
| S16 | qv-gate | `make test-unit` | — |
| S17 | qv-gate | `make allure-integration` | — |
| S18 | qv-browser | Verify the Recent Executions table renders new columns; verify a freshly fired slot shows real elapsed_ms / stdout snippet | — |
| S19 | self-assess | Project has `self_assess=true` (iw-ai-core in projects.toml) | — |

### Database Changes

- **New tables**: None
- **Modified tables**: `keep_alive_runs` — add four nullable columns: `stdout TEXT NULL`, `stderr TEXT NULL`, `elapsed_ms INTEGER NULL`, `returncode INTEGER NULL`.
- **Migration notes**: All four columns are nullable so existing rows remain valid without a backfill. Downgrade drops the four columns in reverse order. No data is destroyed on downgrade because the columns are append-only by definition (poller writes rows, never updates).

### Code Changes

- `orch/db/models.py` — extend `KeepAliveRun` with four `Mapped[…]` columns matching the migration.
- `orch/db/migrations/versions/<new>_i00112_keep_alive_runs_capture_cli_output.py` — Alembic revision.
- `orch/keep_alive_service.py` — `fire_claude` returns `FireResult` (frozen dataclass); `log_run` accepts and persists the four new fields.
- `orch/daemon/keep_alive_poller.py` — `_fire_slot` consumes `FireResult`; `_log_run` persists the four fields; the stricter success contract lives here next to the call site so the policy is one screen tall.
- `dashboard/templates/fragments/keep_alive_runs.html` — two new columns (Elapsed / Output), `—` for NULL.
- `dashboard/templates/_partials/help/keep_alive.html` — append a one-line note explaining the new columns and the stricter contract (only if the file currently documents the column set).
- `dashboard/routers/keep_alive.py` — touch only if the existing `get_recent_runs` plumbing does not already expose the new ORM fields to the template (likely no touch needed).

## File Manifest

All files for this work item live under `ai-dev/active/I-00112/`:

| File | Type | Purpose |
|------|------|---------|
| `I-00112_Issue_Design.md` | Design | This document |
| `I-00112_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `evidences/pre/I-00112-bug-evidence.png` | Evidence | Full keep-alive page (pre-fix) |
| `evidences/pre/I-00112-recent-executions-table.png` | Evidence | Recent Executions table close-up (pre-fix) |
| `evidences/pre/I-00112-page-snapshot.yml` | Evidence | Playwright accessibility snapshot (pre-fix) |
| `prompts/I-00112_S01_Database_prompt.md` | Prompt | S01 schema + model |
| `prompts/I-00112_S02_CodeReview_Database_prompt.md` | Prompt | S02 review |
| `prompts/I-00112_S03_Backend_prompt.md` | Prompt | S03 service + poller success contract |
| `prompts/I-00112_S04_CodeReview_Backend_prompt.md` | Prompt | S04 review |
| `prompts/I-00112_S05_Frontend_prompt.md` | Prompt | S05 template columns |
| `prompts/I-00112_S06_CodeReview_Frontend_prompt.md` | Prompt | S06 review |
| `prompts/I-00112_S07_Tests_prompt.md` | Prompt | S07 reproduction + regression tests |
| `prompts/I-00112_S08_CodeReview_Tests_prompt.md` | Prompt | S08 review |
| `prompts/I-00112_S09_CodeReview_Final_prompt.md` | Prompt | S09 global review |
| `prompts/I-00112_S18_BrowserVerification_prompt.md` | Prompt | S18 browser verification |
| `prompts/I-00112_S19_SelfAssess_prompt.md` | Prompt | S19 self-assessment |

Reports are created during execution in `ai-dev/active/I-00112/reports/`.

## Test to Reproduce

Six tests in `tests/unit/test_keep_alive_poller_success_contract.py`. The first is the canonical reproduction (FAILs against pre-S03 code, PASSes after); the other five are regression coverage for the surrounding contract.

**Test-file location** — These tests do not need the FastAPI `client` fixture; they mock `subprocess.run` directly. They go under `tests/unit/`, not `tests/dashboard/`.

```python
# tests/unit/test_keep_alive_poller_success_contract.py
"""I-00112 — Keep-Alive Scheduler success contract regression tests.

The pre-fix poller logged status='success' whenever `claude` exited 0, even when
no API call was actually made (empty stdout, near-zero elapsed). These tests
mock `subprocess.run` at the boundary so the success-contract logic itself is
exercised — not the `fire_claude` wrapper.
"""

from __future__ import annotations

import subprocess
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from orch.daemon.keep_alive_poller import KeepAlivePoller
from orch.keep_alive_service import fire_claude


# ---------------------------------------------------------------------------
# Reproduction: silent no-op (rc=0, empty stdout, ~0 ms) must NOT be 'success'
# ---------------------------------------------------------------------------


def test_i00112_silent_no_op_is_not_success_empty_stdout(monkeypatch):
    """Reproduction: rc=0 + empty stdout MUST be classified failed, not success."""
    fake = SimpleNamespace(returncode=0, stdout="", stderr="")
    with patch("orch.keep_alive_service.subprocess.run", return_value=fake), \
         patch("orch.keep_alive_service.time.perf_counter", side_effect=[0.0, 0.001]):
        result = fire_claude("hi", model="claude-sonnet-4-6")
    # Post-fix: result is a FireResult; success contract requires non-empty stdout
    assert result.is_success is False, (
        "rc=0 with empty stdout must NOT be classified success "
        "(I-00112: silent no-op is the whole bug)"
    )
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.elapsed_ms < 500


def test_i00112_silent_no_op_is_not_success_fast_elapsed(monkeypatch):
    """rc=0 + non-empty stdout but <500ms elapsed MUST also be classified failed."""
    fake = SimpleNamespace(returncode=0, stdout="OK", stderr="")
    with patch("orch.keep_alive_service.subprocess.run", return_value=fake), \
         patch("orch.keep_alive_service.time.perf_counter", side_effect=[0.0, 0.020]):
        result = fire_claude("hi", model="claude-sonnet-4-6")
    assert result.is_success is False, (
        "elapsed=20ms is below the 500ms floor — a real Sonnet round-trip "
        "cannot complete that fast; classify as failed (I-00112)"
    )


def test_i00112_real_round_trip_is_success():
    """rc=0 + non-empty stdout + elapsed>=500ms MUST be classified success."""
    fake = SimpleNamespace(returncode=0, stdout="OK", stderr="")
    with patch("orch.keep_alive_service.subprocess.run", return_value=fake), \
         patch("orch.keep_alive_service.time.perf_counter", side_effect=[0.0, 3.5]):
        result = fire_claude("hi", model="claude-sonnet-4-6")
    assert result.is_success is True
    assert result.elapsed_ms == 3500
    assert result.stdout == "OK"


def test_i00112_nonzero_returncode_is_failure():
    """rc!=0 is always failure, regardless of stdout."""
    fake = SimpleNamespace(returncode=1, stdout="anything", stderr="boom")
    with patch("orch.keep_alive_service.subprocess.run", return_value=fake), \
         patch("orch.keep_alive_service.time.perf_counter", side_effect=[0.0, 3.0]):
        result = fire_claude("hi", model="claude-sonnet-4-6")
    assert result.is_success is False
    assert result.returncode == 1
    assert result.stderr == "boom"


def test_i00112_poller_persists_captured_fields(monkeypatch, db_session):
    """Poller MUST persist stdout/stderr/elapsed_ms/returncode on every run."""
    # Slot already in DB via fixture; mock subprocess to return a real-looking call
    fake = SimpleNamespace(returncode=0, stdout="OK", stderr="", )
    with patch("orch.keep_alive_service.subprocess.run", return_value=fake), \
         patch("orch.keep_alive_service.time.perf_counter", side_effect=[0.0, 3.0]):
        KeepAlivePoller().poll()
    row = db_session.query(KeepAliveRun).order_by(KeepAliveRun.id.desc()).first()
    assert row.stdout == "OK"
    assert row.stderr == ""
    assert row.elapsed_ms == 3000
    assert row.returncode == 0
    assert row.status == "success"


def test_i00112_poller_logs_failed_when_contract_violated(monkeypatch, db_session):
    """Poller MUST log status='failed' with details on contract violation."""
    fake = SimpleNamespace(returncode=0, stdout="", stderr="")  # empty stdout
    # Both the first attempt AND the retry mock return the same shape
    with patch("orch.keep_alive_service.subprocess.run", return_value=fake), \
         patch("orch.keep_alive_service.time.perf_counter", side_effect=[0.0, 0.001, 0.0, 0.001]):
        KeepAlivePoller().poll()
    row = db_session.query(KeepAliveRun).order_by(KeepAliveRun.id.desc()).first()
    assert row.status in ("failed", "retried_failed"), (
        f"silent no-op was logged as {row.status!r} — must be failed/retried_failed (I-00112)"
    )
    assert row.stdout == ""
    assert row.returncode == 0
    assert row.elapsed_ms is not None and row.elapsed_ms < 500
```

## Browser Verification Test

S18 (qv-browser) verifies post-fix UI surfaces. See `prompts/I-00112_S18_BrowserVerification_prompt.md` for the full script. Summary:

1. Open `/system/keep-alive`. Confirm the **Recent Executions** table now has five columns: `Fired At`, `Slot`, `Status`, `Elapsed`, `Output`.
2. Confirm pre-existing rows (rows with NULL elapsed/output) show `—` in the new columns and do not crash the template.
3. Trigger a fresh fire (manual add of a slot at `time = now`, wait one poll cycle) and verify the new row shows a non-empty Elapsed value and a non-empty Output snippet.
4. No new console errors in the browser.

## Acceptance Criteria

### AC1: Bug is fixed — silent no-ops are detected

```
Given the daemon's `KeepAlivePoller` fires a slot
When the spawned `claude` process exits 0 with empty stdout or with elapsed time under 500 ms
Then the resulting `keep_alive_runs` row has `status='failed'` (not 'success' or 'retried_success')
 And the row's `stdout`, `stderr`, `elapsed_ms`, `returncode` columns are populated with the captured values
```

### AC2: Successful fires are still detected

```
Given the daemon's `KeepAlivePoller` fires a slot
When the spawned `claude` process exits 0 with non-empty stdout and elapsed >= 500 ms
Then the resulting `keep_alive_runs` row has `status='success'`
 And the row's `stdout`/`stderr`/`elapsed_ms`/`returncode` columns are populated with the captured values
```

### AC3: Regression tests exist

```
Given the fix is applied
When `uv run pytest tests/unit/test_keep_alive_poller_success_contract.py -v` runs
Then all six tests in the file pass
 And mocking `subprocess.run` to return (rc=0, stdout="", elapsed≈0ms) causes the poller to log `failed`
```

### AC4: Diagnostic detail is visible on the dashboard

```
Given a user views `/system/keep-alive`
When they look at the Recent Executions table
Then they see two new columns "Elapsed" and "Output" alongside Fired At, Slot, Status
 And rows captured before the migration show "—" in the new columns (not a crash)
 And rows captured after the fix show real elapsed_ms and a stdout snippet
```

### AC5: Migration round-trips cleanly

```
Given the new Alembic revision adding four columns to keep_alive_runs
When `make migration-check` runs
Then upgrade-from-base succeeds
 And alembic schema matches `Base.metadata.create_all()` schema
 And downgrade-then-upgrade round-trips with no error
```

## Regression Prevention

- **Type-level invariant** — `fire_claude` returns a `FireResult` dataclass with an `is_success: bool` property that encodes the contract in one place. Future callers that misuse it (e.g., short-circuit on `result.returncode == 0` instead of `result.is_success`) become a code-review smell rather than a silent regression.
- **Column-level invariant** — `stdout`/`stderr`/`elapsed_ms`/`returncode` are written on **every** `log_run` call. The poller no longer has any code path that creates a `KeepAliveRun` row without those fields.
- **Test boundary moved** — existing tests mocked at `fire_claude`; new tests mock at `subprocess.run`, which is the only boundary where the silent no-op was actually observable. This boundary change is what keeps the bug class out of the codebase.
- **UI surface** — the operator now has post-hoc audit data on the dashboard, so the *next* time a fire looks suspicious they can confirm in seconds whether the API call actually landed.

## Dependencies

- **Depends on**: None
- **Blocks**: None

## Impacted Paths

- `orch/keep_alive_service.py`
- `orch/daemon/keep_alive_poller.py`
- `orch/db/models.py`
- `orch/db/migrations/versions/**`
- `dashboard/routers/keep_alive.py`
- `dashboard/templates/fragments/keep_alive_runs.html`
- `dashboard/templates/_partials/help/keep_alive.html`
- `dashboard/static/styles.css`
- `tests/unit/test_keep_alive_poller_success_contract.py`

## TDD Approach

- **Reproducing test**: `test_i00112_silent_no_op_is_not_success_empty_stdout` — mocks `subprocess.run` to return rc=0/empty stdout/~0 ms elapsed, then asserts the poller logs `failed`. FAILS against pre-fix code (which logs `success`).
- **Unit tests**: All six tests in `tests/unit/test_keep_alive_poller_success_contract.py` — exercise the `(rc, stdout, elapsed)` contract surface.
- **Integration tests**: Existing `tests/integration/test_keep_alive_poller_integration.py` continues to pass (mocked at `fire_claude`); no new integration tests required.

## Notes

**Why these four columns specifically.** The operator's diagnostic loop after a suspicious fire is: "did the CLI actually print a reply, did it take a plausible amount of time, was there an error message buried in stderr, and was the exit code really 0?". Capturing exactly stdout/stderr/elapsed_ms/returncode answers all four questions in one row. Storing more (e.g., per-attempt detail when a retry happens) is out of scope — the existing `error` column already concatenates "attempt 1 error; retry error: attempt 2 error" and the per-attempt rc/stdout would be a separate refactor.

**Why 500 ms specifically.** A Sonnet 4.6 round-trip from this host has been measured at ~3–4 s for short prompts (probe today: 3.92 s). A local CLI short-circuit — e.g., a degraded `-p` mode that prints onboarding text and exits — completes in milliseconds. 500 ms is a generous lower bound that no real round-trip will cross. The constant lives in `orch/daemon/keep_alive_poller.py` as `_MIN_SUCCESS_ELAPSED_MS = 500` with a comment citing I-00112; if the floor ever needs tuning, that is the one place to change.

**Why no `keep_alive_runs.elapsed_ms` index.** Recent-runs is a 10-row LIMIT query ordered by `fired_at DESC` with no `WHERE` clause on the new columns. An index would be pure overhead.

**Functional doc scope.** The user-facing change is small (two extra columns + stricter success classification). The functional doc focuses on the operator's audit experience, not the internal contract refactor.
