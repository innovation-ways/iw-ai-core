# F-00086_S08_Tests_prompt

**Work Item**: F-00086 -- Multi-tab AI Assistant on OpenCode
**Step**: S08
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

(Standard policy. Testcontainers via pytest fixtures are exempt.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy.)

## Input Files

- **Runtime step state** — `uv run iw item-status F-00086 --json`.
- `ai-dev/active/F-00086/F-00086_Feature_Design.md` — design document (read §Acceptance Criteria, §Invariants, §Boundary Behavior, §TDD Approach in full)
- All implementation reports from S03/S06/S07 (and fix reports from S05/S10 if present)
- All files listed in those reports' `files_changed`
- Existing test suite: `tests/dashboard/test_chat_*.py`, `tests/integration/test_chat_*.py`

## Output Files

- `tests/unit/chat/__init__.py` — new (may already exist from S03)
- `tests/unit/chat/test_runtime_base.py` — new
- `tests/unit/chat/test_opencode_runtime_abc_compliance.py` — new
- (S03 already created `tests/unit/chat/test_tab_service.py` — extend if S03 didn't cover all 8 tests listed in design §TDD Approach)
- `tests/integration/test_chat_tabs_api.py` — new
- `tests/integration/test_chat_tabs_multi_session_independence.py` — new
- `tests/integration/test_chat_tabs_reload_persistence.py` — new
- `tests/integration/test_chat_tabs_bootstrap_default.py` — new
- Adapted: `tests/dashboard/test_chat_router.py`, `tests/dashboard/test_chat_endpoint_session_lifecycle.py`, `tests/dashboard/test_chat_endpoint_permission_flow.py`, `tests/dashboard/test_chat_endpoint_reconnect.py`, `tests/dashboard/test_chat_panel_*.py`, `tests/dashboard/test_chat_config_allowlist_intersection.py`
- `ai-dev/active/F-00086/reports/F-00086_S08_Tests_report.md`

## Context

You are writing the dedicated test coverage layer for F-00086. The design's §Invariants section is your acceptance contract — every invariant maps to exactly one test you must write or verify exists.

## Requirements

### 1. Unit tests

**`tests/unit/chat/test_runtime_base.py`**
- `test_chat_runtime_cannot_be_instantiated_directly` — `ChatRuntime()` raises `TypeError` (abstract methods).
- `test_subclass_missing_method_cannot_be_instantiated` — define a stub subclass missing `prompt`; assert `__abstractmethods__` non-empty.
- `test_complete_subclass_can_be_instantiated` — define a stub that overrides every abstract; assert instantiates cleanly.

**`tests/unit/chat/test_opencode_runtime_abc_compliance.py`** (invariant #1)
- Discover every abstract method on `ChatRuntime` via `ChatRuntime.__abstractmethods__`.
- For each, assert `OpencodeRuntime` declares a method of the same name AND `inspect.iscoroutinefunction(...)` is True.
- Assert `inspect.signature(OpencodeRuntime.method)` is compatible with the ABC (same param names; same keyword-only markers). Use `inspect.signature` comparison; if `*` markers differ, that is a regression.

**`tests/unit/chat/test_tab_service.py`** (extend if needed)
- Verify the 8 tests listed in S03's prompt §8 all exist and pass. If S03 deferred any (e.g., the concurrency test), add them here.
- Plus: `test_recent_closed_tabs_orders_by_closed_at_desc`, `test_recent_closed_tabs_respects_limit`, `test_touch_last_active_bumps_field`.

### 2. Integration tests

All integration tests use the testcontainer fixture from `tests/integration/conftest.py`. After `Base.metadata.create_all()`, apply `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` (per `tests/CLAUDE.md`).

**`tests/integration/test_chat_tabs_api.py`** (invariants #3, #4, #7, #8 and AC6, AC7)
- `test_post_tabs_creates_active_tab` — happy path; 201 response shape matches spec.
- `test_post_tabs_rejects_unknown_runtime` — `{"runtime":"pi"}` → 400, error message matches.
- `test_post_tabs_rejects_unknown_model` — model not in `/api/chat/config` → 400.
- `test_post_tabs_soft_cap_header_on_eleventh` — create 10 active tabs; 11th POST returns 201 + `X-Tab-Soft-Cap-Exceeded: true`; absent on 1st–10th.
- `test_get_tabs_excludes_closed_by_default` — create + close one; GET returns 0.
- `test_get_tabs_includes_closed_when_requested` — same setup; `include_closed=true` returns 1.
- `test_get_tabs_orders_by_last_active_desc` — three tabs with staggered `touch_last_active`; assert order.
- `test_patch_tabs_empty_body_does_not_bump_updated_at` (invariant #8).
- `test_patch_tabs_updates_title_and_model_independently`.
- `test_delete_tabs_soft_deletes_and_idempotent` (AC8 partial).
- `test_post_reopen_restores_active_status` (AC8 partial).
- `test_recent_closed_lists_closed_tabs_by_closed_at_desc` (AC8 partial).
- `test_no_legacy_session_endpoints` (invariant #7) — assert `client.get("/api/chat/sessions")` returns 404.

**`tests/integration/test_chat_tabs_multi_session_independence.py`** (invariant #2, AC1)
- Create tab A with model M1 and tab B with model M2.
- Stub the runtime client so each call records its arguments and emits a synthetic event stream (do NOT hit a real OpenCode server — use the existing test pattern in `tests/dashboard/test_chat_router.py` for the runtime mock).
- Send prompt P_A in A and P_B in B.
- Subscribe to each tab's SSE stream and assert: events for A have `tab_id == A.id`; events for B have `tab_id == B.id`; no cross-pollination.
- Abort A; assert B's stream continues to emit.

**`tests/integration/test_chat_tabs_reload_persistence.py`** (AC2)
- Create three tabs with messages.
- Dispose the TestClient instance; recreate it (simulates page reload at the TestClient level — the DB persists).
- `GET /api/chat/tabs` returns the three tabs in `last_active_at DESC` order.
- `GET /api/chat/tabs/{id}` returns the full message history for each tab.

**`tests/integration/test_chat_tabs_bootstrap_default.py`** (AC5, invariant #6, Boundary "Bootstrap called twice concurrently" and "Project has only closed tabs")
- `test_bootstrap_seeds_default_when_chat_tabs_empty`: Setup: empty `chat_tabs`; stub `runtime.list_sessions()` to return one session whose `cwd` equals the test project's `repo_root`. First `GET /api/chat/tabs?project_id=X` returns one tab; verify `title="Default"`, `opencode_session_id` matches the stub session.
- `test_bootstrap_is_no_op_on_second_call`: Second `GET` returns the same tab (no duplicate row in DB).
- `test_bootstrap_is_no_op_when_only_closed_tabs_exist` (Boundary "Project has only closed tabs"): Setup: insert one `chat_tabs` row with `status='closed'` for the project (no active rows); stub `runtime.list_sessions()` to return a matching session. `GET /api/chat/tabs?project_id=X` returns an EMPTY list (`include_closed=False` default); the DB still has exactly ONE row (the pre-existing closed tab); no new `Default` tab is inserted. This proves the gate is "zero rows" not "zero active rows" and that bootstrap respects the user's intentional close-all action.
- `test_bootstrap_concurrent_calls_create_exactly_one_tab`: Use `asyncio.gather` or threading to fire two `GET` calls against an empty `chat_tabs`; assert exactly one tab in DB after both complete. The `uq_chat_tabs_default_per_project` partial unique index from S01 enforces this; the loser of the race catches `IntegrityError` and re-fetches the winner's row.

### 3. Adapt existing chat tests

For each file in:
- `tests/dashboard/test_chat_router.py`
- `tests/integration/test_chat_endpoint_session_lifecycle.py`
- `tests/integration/test_chat_endpoint_permission_flow.py`
- `tests/integration/test_chat_endpoint_reconnect.py`
- `tests/dashboard/test_chat_panel_*.py`
- `tests/integration/test_chat_config_allowlist_intersection.py`

Replace every `/api/chat/sessions/{sid}` URL with `/api/chat/tabs/{tab_id}`. Replace every request body that previously contained session-only fields with the equivalent tab-scoped body. Behavioural assertions (status codes, response shapes for fields that survived the refactor, SSE event ordering) MUST NOT change — if a test was asserting `event.session_id`, it now asserts `event.tab_id`. **No test is deleted.** If a test becomes meaningless after refactor (e.g., it only asserted that an old endpoint exists), update it to the new equivalent rather than deleting.

Document every modified test in the report with a 1-line summary of the change ("URL path: sessions → tabs", "added tab_id setup fixture", etc.).

### 4. Test isolation rules

- NEVER mock the database in these tests (per CLAUDE.md). Use the testcontainer fixture.
- NEVER connect tests to the live DB (port 5433).
- NEVER call `importlib.reload(orch.config)` — use `monkeypatch.delenv()` instead.
- Use `monkeypatch` for env-var manipulation; let testcontainer fixtures handle DB connection setup.

## Project Conventions

Read `tests/CLAUDE.md` for fixture rules, FTS trigger requirement, and the live-DB write guard. Read `skills/iw-ai-core-testing/SKILL.md` for assertion-strength rules and the test red-flag checklist.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck`
3. `make lint`
4. `uv run pytest tests/unit/chat/ -v` — your new unit tests must pass
5. `uv run pytest tests/integration/test_chat_tabs_*.py -v` — your new integration tests must pass
6. `uv run pytest tests/dashboard/test_chat_*.py tests/integration/test_chat_endpoint_*.py -v` — adapted tests must pass

Do NOT run `make test-unit` or `make test-integration` (S14 / S15 own those).

## Subagent Result Contract

```json
{
  "step": "S08",
  "agent": "tests-impl",
  "work_item": "F-00086",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/unit/chat/__init__.py",
    "tests/unit/chat/test_runtime_base.py",
    "tests/unit/chat/test_opencode_runtime_abc_compliance.py",
    "tests/unit/chat/test_tab_service.py",
    "tests/integration/test_chat_tabs_api.py",
    "tests/integration/test_chat_tabs_multi_session_independence.py",
    "tests/integration/test_chat_tabs_reload_persistence.py",
    "tests/integration/test_chat_tabs_bootstrap_default.py",
    "tests/dashboard/test_chat_router.py",
    "tests/dashboard/test_chat_endpoint_session_lifecycle.py",
    "tests/dashboard/test_chat_endpoint_permission_flow.py",
    "tests/dashboard/test_chat_endpoint_reconnect.py",
    "tests/dashboard/test_chat_config_allowlist_intersection.py"
  ],
  "preflight": {
    "format": "ok|fixed",
    "typecheck": "ok",
    "lint": "ok"
  },
  "tests_passed": true,
  "test_summary": "tests/unit/chat: X passed; tests/integration/test_chat_tabs_*: Y passed; adapted dashboard tests: Z passed",
  "tdd_red_evidence": "n/a — dedicated test-coverage step (per template TDD RED Evidence rules; tests-impl is exempt)",
  "blockers": [],
  "notes": "Adapted tests listed in report; no deletions."
}
```
