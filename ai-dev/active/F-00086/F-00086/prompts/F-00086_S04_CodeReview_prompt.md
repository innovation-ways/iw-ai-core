# F-00086_S04_CodeReview_prompt

**Work Item**: F-00086 -- Multi-tab AI Assistant on OpenCode
**Step Being Reviewed**: S03 (backend-impl)
**Review Step**: S04

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY docker command that changes container/volume/network state. Read-only introspection (`docker ps`, `docker inspect`, `docker logs`) and testcontainer fixtures are exempt. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade/downgrade/stamp` against the live orch DB. Read-only (`alembic history|current|show`) is allowed.

## Input Files

- **Runtime step state** — `uv run iw item-status F-00086 --json`.
- `ai-dev/active/F-00086/F-00086_Feature_Design.md` — design document (read §Scope, §Acceptance Criteria, §Invariants, §TDD Approach in full)
- `ai-dev/active/F-00086/reports/F-00086_S03_Backend_report.md` — S03 implementation report
- All files listed in S03's `files_changed`

## Output Files

- `ai-dev/active/F-00086/reports/F-00086_S04_CodeReview_report.md`

## Context

You are reviewing the backend layer for the multi-tab AI Assistant: `ChatRuntime` ABC, the mechanical move of OpenCode plumbing into `orch/chat/opencode/`, the `RelayManager` rekey-by-`tab_id`, and the new `tab_service` + `migration_helpers` modules.

## Read the Design Document FIRST

Before opening any changed file:

- Read §Acceptance Criteria (AC1..AC8) in full — each is a mandatory check.
- Read §Invariants (1..8) in full — each maps to a test the reviewer must verify exists and is correctly named.
- Note every test file the design names by path (e.g., `tests/unit/chat/test_tab_service.py`, `tests/unit/chat/test_opencode_runtime_abc_compliance.py`). Cross-check these against S03's `files_changed`. **Any test file the design names that does not appear in S03's `files_changed` AND is not deferred to S08 is a CRITICAL finding.** S03 owns at minimum `tests/unit/chat/test_tab_service.py`; S08 owns the rest.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Run `make lint` and `make format` on the S03-changed files. Any new violation is a CRITICAL finding with `"category":"conventions"`.

## Review Checklist

### 1. ABC contract correctness

- `ChatRuntime` is `ABC` with `@abstractmethod` on every method named in the design's §Scope > "Runtime-agnostic refactor"?
- Method signatures match the design's spec **exactly** (parameter names, types, async modifier, keyword-only markers `*,`)?
- `OpencodeRuntime` is declared as `class OpencodeRuntime(ChatRuntime):` — explicit base inheritance?
- Every abstract method has a concrete implementation in `OpencodeRuntime`? Construct an instance in a unit test or via `inspect.signature` — if the ABC's `__abstractmethods__` is non-empty for `OpencodeRuntime`, that is a CRITICAL finding.

### 2. Package move correctness (MECHANICAL — no behaviour change)

- `git log --follow orch/chat/opencode/runtime.py` shows continuity with old `opencode_runtime.py`? If `git mv` was not used (copy + delete instead), history is lost — flag as HIGH.
- Re-run the legacy chat test files (`tests/dashboard/test_chat_router.py`, `tests/dashboard/test_chat_endpoint_session_lifecycle.py`, `tests/dashboard/test_chat_endpoint_permission_flow.py`) — they should still pass against the moved package because S06 hasn't yet rewritten the API. Any failure here is a CRITICAL behaviour regression caused by the move.
- `git grep` for the old import paths (`from orch.chat.opencode_runtime`, `from orch.chat.opencode_client`, `from orch.chat.relay_manager`, `from orch.chat.filters`) — every match outside `tests/` or `ai-dev/` is a HIGH finding (incomplete migration).
- `orch/chat/__init__.py` re-exports the canonical names so external imports of `orch.chat.OpencodeClient` etc. still resolve.

### 3. RelayManager tab_id rekey

- Public entrypoint is now `get_or_create_relay(tab_id: str)` (not `session_id`)?
- Internal mapping `tab_id → opencode_session_id` looks up via `tab_service.get_tab(...)` — flag if the relay directly queries the DB or duplicates the tab repository logic.
- **Every event yielded by `Relay.subscribe()` includes a top-level `"tab_id"` field** (invariant #2). Trace the emit path; flag any branch that lacks the stamping as HIGH.
- Ring buffer size and `Last-Event-ID` replay logic unchanged — diff against the moved file's pre-move state.

### 4. tab_service semantics

- Allowlist `ALLOWED_RUNTIMES = frozenset({"opencode"})` defined as module-level constant (so F-B can extend with one line)?
- `create_tab` raises `ValueError` with the exact message shape from the design (`"runtime '<x>' not in allowlist {'opencode'}"`)?
- Soft cap: `count > 10` triggers `soft_cap_exceeded=True` AFTER the new row is inserted — i.e., 11th tab is the first to flag (invariant #4). The tab is always persisted; rejection is NEVER the behaviour.
- `close_tab` is idempotent: a second call on an already-closed tab returns unchanged (does NOT bump `closed_at`).
- `reopen_tab` clears `closed_at` AND sets `status='active'`.
- `update_tab({})` (empty body) does NOT bump `updated_at` (invariant #8).
- `recent_closed_tabs` orders by `closed_at DESC` and respects the `limit` param.

### 5. bootstrap_default_tab idempotency

- Wrapped in `try/except IntegrityError` that re-fetches the existing default tab on collision?
- Calls `runtime.list_sessions()` and filters by `cwd == project_repo_root` (not a substring match, exact equality)?
- Returns `None` when no prior session exists (does NOT create an empty tab)?
- A second invocation is a no-op (returns the same tab object, no new INSERT)?

### 6. Tests for tab_service

- `tests/unit/chat/test_tab_service.py` exists and includes the 8 named tests listed in S03's prompt §8?
- Tests use testcontainer fixture (not mocks against the DB) — see `tests/CLAUDE.md` rule "NEVER mock the database in integration tests".
- The concurrency test (`test_bootstrap_is_idempotent_under_concurrent_calls`) actually exercises concurrent calls (threading or `asyncio.gather`), not just sequential calls.
- The soft-cap test creates 11 tabs and asserts the flag on the 11th specifically — flag if it tests only counts ≤ 10 or asserts something weaker.

### 7. TDD RED evidence (S03 is a behaviour-implementing step)

- S03's report `tdd_red_evidence` field references `test_create_tab_returns_soft_cap_flag_when_count_exceeds_ten` (or similar) with a plausible failure snippet (`AssertionError` or `AttributeError`, NOT `ImportError`).
- Reason: would the named test fail against pre-change code? Pre-change code has no `tab_service` module, so the answer is yes (would fail with `ImportError` or `AttributeError`). If the evidence shows an unrelated failure shape, flag as HIGH.

### 8. Architecture compliance

- `orch/chat/tab_service.py` is a module of functions (matches the project's repository pattern for new modules), not a class.
- `orch/chat/migration_helpers.py` does NOT call alembic or write to the DB outside the explicit `bootstrap_default_tab` function.
- No new dependency on dashboard code from `orch/` (layer boundary).

## Test Verification (NON-NEGOTIABLE)

Run targeted tests (NOT the full suite):

```bash
uv run pytest tests/unit/chat/ -v
uv run pytest tests/dashboard/test_chat_router.py tests/dashboard/test_chat_endpoint_session_lifecycle.py -v
```

Report results in the contract.

## Severity Levels

Per template — CRITICAL / HIGH / MEDIUM_FIXABLE / MEDIUM_SUGGESTION / LOW.

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "F-00086",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "path/to/file.py",
      "line": 42,
      "description": "",
      "suggestion": ""
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "",
  "notes": ""
}
```
