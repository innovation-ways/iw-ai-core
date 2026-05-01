# I-00059_S03_Tests_prompt

**Work Item**: I-00059 -- Doc Generation Job Detail Page Shows No Error Info or Parameters
**Step**: S03
**Agent**: Tests

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status I-00059 --json`
- `ai-dev/active/I-00059/I-00059_Issue_Design.md` — Design document
- `ai-dev/active/I-00059/reports/I-00059_S01_Backend_report.md` — S01 implementation report
- `orch/jobs/aggregator.py` — Fixed file

## Output Files

- `ai-dev/active/I-00059/reports/I-00059_S03_Tests_report.md` — Step report

## Context

You are writing regression tests for **I-00059**: the fix to `JobsAggregator._get_doc_generation` in `orch/jobs/aggregator.py`. The bug was that the detail-path method returned a stub `raw` dict (only `id`, `project_id`, `status`) instead of the full 14-field dict that the list-path `_fetch_doc_generation` returns.

The S01 Backend agent already wrote a basic reproduction test as part of TDD. Your job is to:
1. Verify the reproduction test exists and is semantically correct (see below).
2. Add additional regression tests covering edge cases.

Read the design document's "Test to Reproduce" and "Regression Prevention" sections before writing.

---

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

Previous incidents shipped tests that only checked API response **shape** (key exists, is a list, is non-empty). Those tests passed even when the bug was NOT fixed. Tests must verify **SPECIFIC VALUES**:

- BAD: `assert "error" in row.raw` (shape only — passes even with a stub)
- BAD: `assert row.raw` (truthy check — passes for any non-empty dict)
- GOOD: `assert row.raw.get("error") == "generation timeout after 15 minutes"` (verifies exact stored value)
- GOOD: `assert row.raw.get("skill_used") == "iw-doc-generator"` (verifies exact stored value)
- GOOD: `assert row.raw.get("duration_seconds") == 900` (verifies numeric value)

Every assertion in every test MUST verify a **specific expected value**, not just presence or non-emptiness.

---

## Requirements

### 1. Reproduction Test (verify or add)

Check whether S01 already added a reproduction test matching the design doc's "Test to Reproduce" section. If it exists and correctly asserts specific values, keep it as-is. If it is missing or uses shape-only assertions, fix it.

The test must:
- Create a `DocGenerationJob` with `error`, `skill_used`, `duration_seconds`, `doc_id`, `trigger_reason` explicitly set
- Call `aggregator.get_job(project_id=..., job_type=JobType.doc_generation, job_id=...)`
- Assert SPECIFIC stored values for each field: `error`, `skill_used`, `duration_seconds`, `doc_id`, `trigger_reason`
- Be placed in `tests/integration/` (DB-coupled)

### 2. Additional Regression Tests

Add at least two more tests:

**Test A — lint_warnings field (list type)**

```python
def test_i00059_get_doc_generation_raw_lint_warnings(db_session):
    """lint_warnings (a list/JSON field) must survive the raw dict round-trip."""
    # Create job with lint_warnings set to a non-empty list
    # Assert row.raw.get("lint_warnings") == <the exact list stored>
```

**Test B — parity between get_job and list path**

```python
def test_i00059_get_job_raw_parity_with_fetch(db_session):
    """get_job and _fetch_doc_generation must produce identical raw dicts for the same job."""
    # Create a DocGenerationJob
    # Fetch via aggregator.get_job() -> row_detail.raw
    # Fetch via aggregator.fetch_jobs() with matching filters -> find the same job -> row_list.raw
    # Assert row_detail.raw == row_list.raw (or at least the same keys and values)
```

This parity test is the key regression guard: if someone adds a field to `_fetch_doc_generation` but forgets `_get_doc_generation` (or the shared helper), this test catches it immediately.

### 3. Placement and Naming

- All tests go in `tests/integration/` — they require a live testcontainer DB session (`db_session` fixture from `tests/conftest.py`)
- NEVER connect to the live orchestration DB (port 5433)
- Follow the naming convention already used in the test directory (check existing files)
- Test function names must start with `test_i00059_` to make the incident traceable

## Project Conventions

Read `tests/CLAUDE.md` and `CLAUDE.md` for:
- Testcontainer setup and the `db_session` fixture
- `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after `Base.metadata.create_all()` (already handled by `conftest.py` — don't duplicate)
- ORM model imports from `orch.db.models`

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck`
3. `make lint`

## Test Verification (NON-NEGOTIABLE)

Run `make test-integration` — all new tests must pass with zero failures.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "Tests",
  "work_item": "I-00059",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/integration/test_jobs_aggregator_i00059.py"
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
