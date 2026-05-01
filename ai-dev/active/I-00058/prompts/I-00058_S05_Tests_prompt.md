# I-00058_S05_Tests_prompt

**Work Item**: I-00058 — DocGenerationJob IDs are UUIDs instead of sequential DOC-NNNNN identifiers
**Step**: S05
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

Allowed exceptions: testcontainers (pytest), read-only introspection, `./ai-core.sh` / `make` targets.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status I-00058 --json`
- `ai-dev/active/I-00058/I-00058_Issue_Design.md` — Design document (see "Test to Reproduce" and "TDD Approach" sections)
- `ai-dev/active/I-00058/reports/I-00058_S01_Database_report.md` — S01 (model changes)
- `ai-dev/active/I-00058/reports/I-00058_S03_Backend_report.md` — S03 (listener + aggregator changes)
- `tests/conftest.py` — test fixtures and testcontainer setup
- `tests/CLAUDE.md` — test conventions, fixture patterns, `FTS_FUNCTION_SQL` requirement
- `orch/db/models.py` — `DocGenerationJob` class (with new `public_id` column and listener)
- `orch/jobs/aggregator.py` — updated aggregator

## Output Files

- `tests/integration/test_i00058_doc_generation_public_id.py` — reproduction test + regression tests
- `ai-dev/active/I-00058/reports/I-00058_S05_Tests_report.md` — Step report

## Context

You are writing tests for **I-00058**. The bug: `DocGenerationJob` records received raw UUID IDs instead of sequential `DOC-NNNNN` identifiers. The fix (in S01 and S03) adds a `public_id` column and a `before_insert` event listener that allocates from `id_sequences['DOC']`, and updates the jobs aggregator to surface `public_id` as the display ID.

Your tests must:
1. **Prove the bug existed** (reproduction test — would fail on pre-fix code).
2. **Prove the fix works** (regression tests — must pass after the fix).

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed.
But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert job.public_id is not None` (shape only — only checks non-null)
- GOOD: `assert job.public_id.startswith("DOC-")` (semantic — verifies the prefix)
- GOOD: `assert job.public_id == "DOC-00001"` (semantic — verifies exact first ID)
- GOOD: `assert not job.public_id.startswith("{")` (semantic — verifies it is NOT a UUID)

Every assertion must verify a **specific expected value**, not just that a value exists or is non-empty.

## Requirements

### 1. Reproduction test (integration)

Write a test that would FAIL against pre-fix code and PASS after the fix. Place it in `tests/integration/test_i00058_doc_generation_public_id.py`.

Reference the design document's "Test to Reproduce" section. Key points:
- Use the testcontainer DB fixture from `tests/conftest.py` (never connect to live port 5433).
- Call `db_session.flush()` after `db_session.add(job)` to trigger the `before_insert` listener.
- Assert that `job.public_id` is exactly `"DOC-00001"` (first allocation in a clean DB).
- Assert that `job.public_id` does NOT look like a UUID (e.g., `assert "-" not in job.public_id[:3]` is not enough — check the full format with `re.match(r"^DOC-\d{5}$", job.public_id)`).

### 2. Sequential increment test (integration)

Insert two `DocGenerationJob` rows in the same session and assert:
- First row: `public_id == "DOC-00001"`
- Second row: `public_id == "DOC-00002"`

This proves the `id_sequences['DOC']` counter increments correctly.

### 3. Aggregator unit test

Write a unit test for `_fetch_doc_generation` and `_get_doc_generation` in `orch/jobs/aggregator.py` that verifies:
- When a job has `public_id = "DOC-00001"`, the `JobRow.job_id` returned is `"DOC-00001"` (not the UUID).
- When a job has `public_id = None` (legacy), the `JobRow.job_id` returned is the UUID (fallback).

Use mocking or in-memory DB fixtures as appropriate (check `tests/CLAUDE.md` for the project's preferred approach).

### 4. `DocService.create_doc_job` integration test

Call `DocService.create_doc_job()` against the testcontainer DB and assert that:
- The returned `DocGenerationJob` has a `public_id` matching `r"^DOC-\d{5}$"`.
- The `public_id` is NOT a UUID (i.e., does not match the UUID4 pattern).

## Project Conventions

Read `tests/CLAUDE.md` for:
- Testcontainer setup and the `db_session` fixture
- `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` requirement after `Base.metadata.create_all()`
- psycopg v3 URL replacement: `url.replace("postgresql+psycopg2://", "postgresql+psycopg://")`
- Integration test file naming (`test_i<nnnnn>_*.py` in `tests/integration/`)

**NEVER** connect to port 5433 in tests. Use testcontainers only.

## TDD Requirement

1. **RED**: Confirm the reproduction test fails against a version without the listener (or document that it would fail).
2. **GREEN**: Run all tests against the fixed code — all must pass.
3. **REFACTOR**: Remove any redundant assertions; ensure every assert checks a specific value.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. **`make format`** — auto-fix formatting
2. **`make typecheck`** — zero errors on new test file
3. **`make lint`** — zero errors
4. **`make test-unit`** — all unit tests pass
5. **`make allure-integration`** (or `make test-integration`) — integration tests pass including new ones

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "tests-impl",
  "work_item": "I-00058",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/integration/test_i00058_doc_generation_public_id.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
