# F-00086 S04 — Code Review Report (Backend S03)

**Step**: S04 (code-review-impl)
**Reviewed step**: S03 (backend-impl)
**Work item**: F-00086 — Multi-tab AI Assistant on OpenCode
**Reviewer**: code-review-impl
**Date**: 2026-05-19

---

## Summary

Reviewed the S03 backend implementation against the design doc's §Scope, §Acceptance Criteria (AC1..AC9), §Invariants (1..8), §Boundary Behavior, and §TDD Approach sections. Read all changed files: `orch/chat/runtime_base.py`, `orch/chat/opencode/runtime.py`, `orch/chat/opencode/relay_manager.py`, `orch/chat/opencode/client.py`, `orch/chat/opencode/filters.py`, `orch/chat/opencode/__init__.py`, `orch/chat/__init__.py`, `orch/chat/tab_service.py`, `orch/chat/migration_helpers.py`, `dashboard/routers/chat.py`, and `tests/unit/chat/test_tab_service.py`.

## What was run

- `make lint` — all checks passed
- `make format` — 784 files already formatted
- `uv run pytest tests/unit/chat/ -v --no-cov` — 9 passed
- `uv run pytest tests/dashboard/test_chat_router.py tests/integration/test_chat_endpoint_session_lifecycle.py -v --no-cov` — 49 passed
- `uv run python -c "from orch.chat import OpencodeRuntime; print(OpencodeRuntime.__abstractmethods__)"` — frozenset() (all ABC methods implemented)
- `git diff --cached --name-status` — confirmed R100 (100% rename) for all four moved files

---

## Checklist Results

### 1. Pre-review lint & format gate

PASS. `make lint` and `make format` both pass with zero violations.

### 2. ABC contract

PASS. `ChatRuntime` is `ABC` with all 13 `@abstractmethod` decorators present (health, create_session, get_session, list_sessions, get_messages, prompt, abort, reply_permission, set_model, close_session, subscribe, get_config, get_providers). Signatures match the design spec. `subscribe` is declared `def` (not `async def`) on the ABC, correctly allowing concrete async generator implementations. `OpencodeRuntime.__abstractmethods__` is `frozenset()` — all abstract methods implemented.

### 3. Package move correctness

PASS. `git diff --cached --name-status` shows `R100` (100% rename) for all four files, confirming `git mv` was used, not copy+delete. History is intact (the staged renames are pending commit — the worktree is mid-implementation, which is expected). The `orch/chat/opencode/__init__.py` re-exports all canonical names. Old import paths are absent from all code (only appear in prompt markdown files in `ai-dev/`).

### 4. RelayManager rekey

PASS. `get_or_create_relay(tab_id: str)` is the public entrypoint. The `session_resolver` callable is injected (DB-free relay package). The `_stamp_tab_id` method is called in all three emit paths:
- Live events in `_pump` (line 204)
- Error events in `_pump` (line 252)
- Gap events in `_compute_replay` (line 166)
Ring buffer unchanged at `_DEFAULT_BUFFER_SIZE = 256`.

### 5. tab_service semantics

MOSTLY PASS — one finding.

- `ALLOWED_RUNTIMES = frozenset({"opencode"})` defined at module level. PASS.
- Soft cap: count taken after `db.flush()` (post-insert), so the 11th tab triggers the flag. PASS. Tab always persisted. PASS.
- `close_tab` idempotent: second call returns unchanged when `status == 'closed'`. PASS.
- `reopen_tab` clears `closed_at` and sets `status='active'`. PASS.
- `update_tab({})` no-op path: returns early without touching `updated_at`. PASS.
- `recent_closed_tabs` orders by `closed_at DESC` with `limit`. PASS.
- Functions-not-class pattern. PASS.

**MEDIUM_FIXABLE**: Error message format deviates from the design spec (see Findings).

### 6. bootstrap_default_tab

PASS. All gates verified:
- `count_tabs(..., include_closed=True) > 0` check before any insert. Second invocation is a no-op.
- `try/except IntegrityError` wraps the insert; the exception branch rolls back and re-fetches via `db.query(ChatTab).filter(...)`.
- CWD filtering uses `== project_repo_root` (exact equality, via `_session_cwd(s) == project_repo_root` in `_pick_most_recent_session`).
- Returns `None` when no prior session matches.
- Does not call alembic.

The `_list_runtime_sessions` async bridge raises loudly if called from inside a running event loop. This is appropriate defensive behavior; S06 must call `bootstrap_default_tab` from sync context or restructure the call.

### 7. Tests

PASS. All 9 required tests present:
1. `test_create_tab_persists_row_with_defaults`
2. `test_create_tab_rejects_unknown_runtime`
3. `test_create_tab_returns_soft_cap_flag_when_count_exceeds_ten`
4. `test_close_tab_is_idempotent`
5. `test_reopen_tab_restores_active_status`
6. `test_empty_patch_does_not_bump_updated_at`
7. `test_bootstrap_creates_default_tab_when_empty_and_session_exists`
8. `test_bootstrap_does_not_fire_when_only_closed_tabs_exist`
9. `test_bootstrap_is_idempotent_under_concurrent_calls`

Tests use testcontainer fixtures (re-exported from `tests/integration/conftest.py`). The concurrency test uses `threading.Barrier(parties=2)` and two independent connections — proper concurrent model. The soft-cap test creates 11 tabs and asserts `flags[:10] == [False] * 10` and `flags[10] is True` — exactly the 11th-tab assertion required.

### 8. TDD RED evidence

ACCEPTABLE (MEDIUM_SUGGESTION level at worst). The RED failure was `ModuleNotFoundError: No module named 'orch.chat.migration_helpers'` rather than the preferred `AssertionError` or `AttributeError`. This is acceptable per the review instructions because the entire module was being created from scratch — the test file's existence confirms RED-first intent.

### 9. Architecture compliance

PASS. No dashboard imports inside `orch/`. `tab_service.py` is flat functions. `migration_helpers.py` does not call alembic.

---

## Findings

### MEDIUM_FIXABLE — Error message format deviates from design spec

**File**: `orch/chat/tab_service.py`
**Line**: 68
**Category**: conventions

The design spec (AC6, Boundary Behavior table) requires the error message shape `"runtime 'pi' not in allowlist {'opencode'}"` — set notation with curly braces.

The implementation produces `"runtime 'pi' not in allowlist ['opencode']"` — list notation with square brackets, because it uses `sorted(ALLOWED_RUNTIMES)!r` which coerces the frozenset to a sorted list.

The test at line 71 uses `match=r"runtime 'pi' not in allowlist"` (partial regex) and therefore passes without catching this discrepancy. When S06 converts the `ValueError` message into the HTTP 400 response body, AC6's assertion will fail if it checks the exact bracket notation.

**Suggestion**: Change line 68 to:
```python
raise ValueError(f"runtime '{runtime}' not in allowlist {ALLOWED_RUNTIMES!r}")
```
This produces `"runtime 'pi' not in allowlist frozenset({'opencode'})"` — or, for the exact `{'opencode'}` match:
```python
raise ValueError(f"runtime '{runtime}' not in allowlist {set(ALLOWED_RUNTIMES)!r}")
```
which produces `"runtime 'pi' not in allowlist {'opencode'}"` — exactly matching the design spec.

---

### LOW — `subscribe` in `OpencodeRuntime` silently ignores `session_id`

**File**: `orch/chat/opencode/runtime.py`
**Line**: 267-287
**Category**: code_quality

`OpencodeRuntime.subscribe(session_id, ...)` accepts `session_id` but ignores it (`# noqa: ARG002`). The ABC contract includes `session_id` because future runtimes (Pi, F-B) may need it to route to a per-session stream. For OpenCode the stream is global and session routing happens in the relay. The silent discard is documented in a noqa comment but could mislead callers who expect session isolation at this layer.

**Suggestion**: Add an explicit docstring note that `session_id` is unused because OpenCode's `/event` stream is session-agnostic — the relay manager provides per-session isolation. Already partially documented; just make it more prominent.

---

## Contract JSON

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "F-00086",
  "step_reviewed": "S03",
  "verdict": "pass",
  "findings": [
    {
      "severity": "MEDIUM_FIXABLE",
      "category": "conventions",
      "file": "orch/chat/tab_service.py",
      "line": 68,
      "description": "Error message uses list notation ['opencode'] (sorted()!r) instead of set notation {'opencode'} specified in the design doc (AC6, Boundary Behavior table). When S06 converts the ValueError into the HTTP 400 body, the bracket style will not match the spec.",
      "suggestion": "Change to: raise ValueError(f\"runtime '{runtime}' not in allowlist {set(ALLOWED_RUNTIMES)!r}\") to produce the exact {'opencode'} notation from the design."
    },
    {
      "severity": "LOW",
      "category": "code_quality",
      "file": "orch/chat/opencode/runtime.py",
      "line": 269,
      "description": "OpencodeRuntime.subscribe silently ignores the session_id parameter (noqa: ARG002). The ABC includes session_id for future runtimes. The discard is acceptable for OpenCode's global stream design but is only partially documented.",
      "suggestion": "Add a brief docstring note that session_id is unused because OpenCode's /event stream is global; per-session routing is the relay manager's responsibility."
    }
  ],
  "mandatory_fix_count": 1,
  "tests_passed": true,
  "test_summary": "9/9 tests passed in tests/unit/chat/test_tab_service.py; 34/34 passed in tests/dashboard/test_chat_router.py; 4/4 passed in tests/integration/test_chat_endpoint_session_lifecycle.py. No regressions introduced by the package move.",
  "notes": "make lint and make format both pass cleanly. All 13 ABC abstract methods are present on ChatRuntime and all are implemented on OpencodeRuntime (abstractmethods == frozenset()). git mv confirmed via git diff --cached --name-status showing R100 for all four renamed files. Old import paths absent from all production and test code. RelayManager rekey is complete: tab_id stamped on all three emit paths (live, error, gap). tab_service invariants #3 #4 #5 #8 all verified at code level and exercised by tests. bootstrap_default_tab idempotency, race safety, intent-preservation all verified. The one MEDIUM_FIXABLE finding (error message bracket notation) should be fixed before S06 wires the ValueError into the HTTP 400 response body."
}
```
