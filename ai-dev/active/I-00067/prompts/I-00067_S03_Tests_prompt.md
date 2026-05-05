# I-00067_S03_Tests_prompt

**Work Item**: I-00067 -- Recent Activity messages need truncation + click-to-expand popup
**Step**: S03
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures from `tests/conftest.py` are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This step adds a test file only.

## Input Files

- `uv run iw item-status I-00067 --json` — runtime step state
- `ai-dev/active/I-00067/I-00067_Issue_Design.md` — Design document (Acceptance Criteria are the contract)
- `ai-dev/active/I-00067/reports/I-00067_S01_Frontend_report.md` — S01 implementation report
- `dashboard/templates/pages/project/dashboard.html` — the (now-fixed) template
- `dashboard/templates/fragments/activity_text_modal.html` — the new modal partial
- `tests/integration/test_dashboard_pages.py` — existing dashboard tests for fixture patterns
- `tests/conftest.py` — fixture conventions (testcontainer, FTS_FUNCTION_SQL, FTS_TRIGGER_SQL)
- `tests/CLAUDE.md` — test rules

## Output Files

- `tests/integration/test_i00067_recent_activity_truncation.py` — New test file (or extension if S01 created a stub)
- `ai-dev/active/I-00067/reports/I-00067_S03_Tests_report.md` — Step report

## Context

Write the regression test suite for I-00067. The fix has already been applied in S01. Your tests must:

1. Be **falsifiable on `main`** — i.e., would FAIL against the pre-fix template at `dashboard/templates/pages/project/dashboard.html:121` (`<span ...>{{ event.message or event.event_type }}</span>` with no truncation).
2. PASS against the current (post-S01) code.

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed. But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert "permissions" in data` (shape only)
- GOOD: `assert "brands:manage" in permissions` (semantic — verifies specific expected value)
- GOOD: `assert "*" not in permissions` (semantic — verifies unwanted value is absent)

For this incident:
- BAD: `assert "..." in html` (would pass even if `...` appears anywhere — including in the empty-state link "View all batches.").
- GOOD: `assert ("x" * 100 + "...") in html` and `assert ("x" * 200) in html` and `assert "x" * 101 + "..." not in html` (the cutoff is exact).

## Requirements

### 1. Tests required

Add the following tests in `tests/integration/test_i00067_recent_activity_truncation.py`:

#### test_long_message_is_truncated_to_100_chars_with_dots

- Seed a `DaemonEvent` with `message = "x" * 200` for the project.
- GET `/project/{pid}/`.
- Assert HTTP 200.
- Assert the response body contains the literal substring `"x" * 100 + "..."`.
- Assert the trigger class (e.g., `activity-message-truncated`) is present near that row.
- Assert the FULL 200-char string is also present in the body (carried in the modal payload, e.g., `data-full-text="xxx...xxx"`). This is the regression-prevention check.
- Assert the rendered visible truncation does NOT include the 101st `x`: i.e., `"x" * 101 + "..."` is NOT in the response body. (This catches off-by-one errors.)

#### test_short_message_renders_verbatim_with_no_dots

- Seed a `DaemonEvent` with `message = "short message under 100 chars"` (well under 100).
- GET `/project/{pid}/`.
- Assert the response body contains the verbatim message.
- Assert the trigger class (`activity-message-truncated`) is NOT present for that row's vicinity.
- Assert no `data-full-text="short message under 100 chars"` payload is emitted (the modal payload should only exist for truncated rows).
- Assert the message is NOT followed by `...` in the rendered output.

#### test_message_at_exactly_100_chars_is_not_truncated

- Seed a `DaemonEvent` with `message = "a" * 100`.
- GET `/project/{pid}/`.
- Assert `"a" * 100` is in the response.
- Assert `"a" * 100 + "..."` is NOT in the response.
- Assert the trigger class is NOT present for this row.

#### test_message_at_exactly_101_chars_is_truncated

- Seed a `DaemonEvent` with `message = "b" * 101`.
- GET `/project/{pid}/`.
- Assert `"b" * 100 + "..."` IS in the response.
- Assert the trigger class IS present.
- Assert the full 101-char string is in the modal payload.

#### test_html_in_message_is_escaped_in_both_preview_and_payload

- Seed a `DaemonEvent` with `message = "<script>alert('xss')</script>" + "a" * 200` (long enough to truncate).
- GET `/project/{pid}/`.
- Assert the literal string `<script>alert('xss')</script>` is NOT in the response (would mean unescaped HTML execution).
- Assert the escaped form `&lt;script&gt;` IS present.

#### test_empty_message_falls_back_to_event_type_with_no_truncation

- Seed a `DaemonEvent` with `message = None`, `event_type = "step_failed"`.
- GET `/project/{pid}/`.
- Assert the response contains the literal `step_failed`.
- Assert the trigger class is NOT present for that row.
- Assert no `data-full-text` payload is emitted for that row.

#### test_entity_link_routing_unchanged_for_batch_doc_job_work_item

- Seed three `DaemonEvent` rows, one each with `entity_type="batch"` (entity_id `BATCH-99001`), `entity_type="doc_job"` (entity_id `aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa`), `entity_type="work_item"` (entity_id `I-99001`).
- GET `/project/{pid}/`.
- Assert each entity-id link href is correct: `/project/{pid}/batch/BATCH-99001`, `/project/{pid}/jobs/doc/aaaaaaaa-...`, `/project/{pid}/item/I-99001`.
- This is the no-regression check on the link rendering paths the fix should NOT have touched.

### 2. Test conventions

- Use the existing `client: TestClient` and `db_session: Any` fixtures from `tests/conftest.py` and the dashboard test patterns at `tests/integration/test_dashboard_pages.py`.
- Each test cleans up its own seeded `DaemonEvent` rows or uses an isolated session — match the dominant pattern in `test_dashboard_pages.py`.
- Test names start with `test_` and follow the project naming style.
- Do NOT use mocks for the database (per `CLAUDE.md` critical rule).

## Project Conventions

Read `tests/CLAUDE.md` and `CLAUDE.md`. Critical rules:

- Tests use testcontainers, NEVER live DB on port 5433.
- Run `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after `Base.metadata.create_all()` (the `db_session` fixture handles this).
- `DaemonEvent.metadata` is `event_metadata` in Python (SQLAlchemy reserves `metadata`).

## Pre-flight Quality Gates

```bash
make format
make typecheck
make lint
```

## Test Verification (NON-NEGOTIABLE)

Run `make test-integration` and confirm:

1. All seven tests above pass.
2. No regressions in existing dashboard tests (`tests/integration/test_dashboard_pages.py`).

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "tests-impl",
  "work_item": "I-00067",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/integration/test_i00067_recent_activity_truncation.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "7 passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
