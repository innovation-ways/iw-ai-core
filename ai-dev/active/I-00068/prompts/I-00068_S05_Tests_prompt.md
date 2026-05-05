# I-00068_S05_Tests_prompt

**Work Item**: I-00068 -- Recent Activity batch link from "archived" event routes to /item/ instead of /batch/
**Step**: S05
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures from `tests/conftest.py` are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy.

## Input Files

- `uv run iw item-status I-00068 --json` — runtime step state
- `ai-dev/active/I-00068/I-00068_Issue_Design.md` — Design document (Acceptance Criteria are the contract)
- `ai-dev/active/I-00068/reports/I-00068_S01_Backend_report.md` — S01 report
- `ai-dev/active/I-00068/reports/I-00068_S03_Frontend_report.md` — S03 report
- `orch/archive/batch_archiver.py` — Now-fixed archiver
- `dashboard/templates/pages/project/dashboard.html` — Now-fixed template
- `tests/integration/test_dashboard_pages.py` — Existing dashboard tests (DO NOT modify the existing tests)
- `tests/conftest.py` and `tests/CLAUDE.md` — Fixture conventions

## Output Files

- `tests/integration/test_i00068_batch_link_routing.py` — New regression test file
- `ai-dev/active/I-00068/reports/I-00068_S05_Tests_report.md` — Step report

## Context

Write the regression test suite for I-00068. The fixes have been applied in S01 (backend) and S03 (frontend). Your tests must:

1. Be **falsifiable on `main`** — i.e., would FAIL against the pre-fix archiver / template.
2. PASS against the current (post-S01-S03) code.

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed. But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert "batch" in row.entity_type` (substring match — would pass for "batch_archived" too if the column held the event_type by mistake)
- GOOD: `assert row.entity_type == "batch"` (exact value)
- BAD: `assert "BATCH-99099" in resp.text` (the ID could be anywhere — even in an error message)
- GOOD: `assert 'href="/project/test-proj/batch/BATCH-99099"' in resp.text` (locks in the full URL substring)

## Requirements

### 1. Tests required

Add the following tests in **a new file** `tests/integration/test_i00068_batch_link_routing.py`. Do NOT modify the existing `tests/integration/test_dashboard_pages.py` — its tests should continue to assert the existing contracts unchanged.

#### Backend tests

##### test_batch_archiver_emit_writes_entity_type_batch

- Use the testcontainer-backed `db_session` fixture.
- Call `orch.archive.batch_archiver._emit(db_session, event_type="batch_archived", project_id="test-proj", batch_id="BATCH-99099", message="Batch BATCH-99099 archived successfully")`.
- `db_session.commit()`.
- Query for the row: `db_session.scalars(select(DaemonEvent).where(DaemonEvent.entity_id == "BATCH-99099")).one()`.
- Assert: `row.entity_type == "batch"` (exact equality).
- Assert: `row.entity_id == "BATCH-99099"`.
- Assert: `row.event_type == "batch_archived"`.

This test would FAIL on `main` because pre-fix `_emit` does not set `entity_type`.

#### Dashboard tests

##### test_dashboard_routes_batch_id_to_batch_url_when_entity_type_is_batch

- Seed a `Project` row (use `make_project` helper or equivalent — match the pattern at `tests/integration/test_dashboard_pages.py:213`).
- Seed a `DaemonEvent` with `entity_id="BATCH-99099"`, `entity_type="batch"`, `message="Batch archived"`.
- GET `/project/test-proj/`.
- Assert HTTP 200.
- Assert `'href="/project/test-proj/batch/BATCH-99099"' in resp.text`.
- Assert `'href="/project/test-proj/item/BATCH-99099"' not in resp.text`.

This is a regression-prevention test (already worked pre-fix) — it locks in the explicit-branch behaviour.

##### test_dashboard_routes_batch_id_to_batch_url_when_entity_type_is_none

- Same setup but `entity_type=None`.
- Assert HTTP 200.
- Assert `'href="/project/test-proj/batch/BATCH-99099"' in resp.text`.
- Assert `'href="/project/test-proj/item/BATCH-99099"' not in resp.text`.

This test would FAIL on `main` (pre-fix template falls through to `/item/`).

##### test_dashboard_falls_back_to_item_for_non_batch_id_with_no_entity_type

- Seed a `DaemonEvent` with `entity_id="I-99099"`, `entity_type=None`.
- Assert `'href="/project/test-proj/item/I-99099"' in resp.text`.
- Assert `'href="/project/test-proj/batch/I-99099"' not in resp.text`.

This guards against accidentally over-matching `BATCH-` (e.g., if someone mistakenly checked `event.entity_id.startswith('B')`).

##### test_dashboard_falls_back_to_item_for_lowercase_batch_prefix

- Seed a `DaemonEvent` with `entity_id="batch-99099"` (lowercase), `entity_type=None`.
- Assert `'href="/project/test-proj/item/batch-99099"' in resp.text`.
- Assert `'href="/project/test-proj/batch/batch-99099"' not in resp.text`.

Locks in case-sensitivity (the prefix check is `BATCH-`, not `batch-`).

##### test_dashboard_does_not_match_batchfoo_prefix_without_dash

- Seed a `DaemonEvent` with `entity_id="BATCHFOO"` (no dash), `entity_type=None`.
- Assert `'href="/project/test-proj/item/BATCHFOO"' in resp.text`.
- Assert `'href="/project/test-proj/batch/BATCHFOO"' not in resp.text`.

Locks in the trailing-dash requirement of the prefix check.

##### test_dashboard_existing_entity_type_branches_unchanged

- Seed three `DaemonEvent` rows: `(entity_type="batch", entity_id="BATCH-90001")`, `(entity_type="doc_job", entity_id="DOCJOB-90001")`, `(entity_type="work_item", entity_id="I-90001")`.
- Assert each renders the canonical URL: `/batch/BATCH-90001`, `/jobs/doc/DOCJOB-90001`, `/item/I-90001`.

Locks in no regression on the explicit branches.

### 2. End-to-end test (integration of S01 + S03)

##### test_archived_batch_event_renders_correct_dashboard_link

- Use the real archiver path: import and call something that exercises `_emit` for a fake batch archive (or simulate by calling `_emit` directly with `entity_type="batch"` per S01).
- Verify the resulting `DaemonEvent` row, when rendered through the dashboard, produces a `/batch/` link.
- This is the "regression scenario from the screenshot" check, end-to-end.

### 3. Test conventions

- Use `make_project`, `make_daemon_event` helpers if they exist in `tests/integration/test_dashboard_pages.py` (or import them); otherwise create local helpers in the new file.
- Match the existing pattern at lines 213-299 of `test_dashboard_pages.py` for fixture wiring.
- Test names start with `test_` and clearly describe the behaviour.
- No mocks for the database (per `CLAUDE.md`).

## Project Conventions

Read `tests/CLAUDE.md` and `CLAUDE.md`. Critical rules:

- testcontainers, NEVER live DB on port 5433.
- `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after `Base.metadata.create_all()`.
- `DaemonEvent.metadata` → `event_metadata` in Python.
- `daemon_events` is append-only — do NOT UPDATE existing rows in tests.

## Pre-flight Quality Gates

```bash
make format
make typecheck
make lint
```

## Test Verification (NON-NEGOTIABLE)

Run `make test-integration` and confirm:

1. All seven new tests above pass.
2. No regressions in `test_dashboard_pages.py`. In particular, `test_recent_activity_unknown_entity_type_falls_back_to_item_route` (which uses `I-99999` and asserts `/item/I-99999`) must still pass — its scenario is unchanged because `I-99999` does NOT match the `BATCH-` prefix.

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "tests-impl",
  "work_item": "I-00068",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/integration/test_i00068_batch_link_routing.py"
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
