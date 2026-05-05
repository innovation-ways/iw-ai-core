# I-00064_S03_Tests_prompt

**Work Item**: I-00064 -- Job detail "View document" link 404s with double project_id prefix
**Step**: S03
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures spun up by pytest are exempt
— the project's `tests/conftest.py` handles them. Do NOT manually start
or stop containers. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. This step does NOT touch migrations.)

## Input Files

- `uv run iw item-status I-00064 --json` — runtime step state.
- `ai-dev/active/I-00064/I-00064_Issue_Design.md` — design document; the
  **Test to Reproduce** section sketches the three tests.
- `ai-dev/active/I-00064/reports/I-00064_S01_Backend_report.md` — S01 report (lists `files_changed`).
- `orch/jobs/aggregator.py` — the fixed file.
- `tests/CLAUDE.md` — fixture rules (read carefully — testcontainer
  patterns, FTS bootstrap, psycopg URL replacement, `monkeypatch.delenv`).
- `tests/conftest.py` — available fixtures (look for `db_session`,
  `client`, dashboard TestClient setup).
- `tests/integration/test_i00059_doc_generation_get_job.py` — adjacent
  test file in the same area; use it as a template for fixture
  construction and JobsAggregator usage.

## Output Files

- `tests/integration/test_i00064_doc_generation_view_document_url.py` — new test file
- `ai-dev/active/I-00064/reports/I-00064_S03_Tests_report.md` — step report

## Context

You are writing the regression test suite for I-00064. The S01 fix has
already been applied — your tests must FAIL on `main` (pre-fix) and
PASS on the current branch (post-fix). Read the design document for the
full root-cause story.

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is
non-empty) and passed. But the bug was NOT fixed. Tests must verify
SPECIFIC VALUES:

- BAD: `assert "doc_id" in row.raw` (shape only — passes even with the
  composite FK)
- GOOD: `assert row.raw["doc_id"] == "code-index"` (semantic — verifies
  the specific expected value)
- GOOD: `assert ":" not in (row.raw["doc_id"] or "")` (semantic —
  verifies the unwanted composite shape is absent)

Every assertion below this line must follow that rule.

## Requirements

### 1. New test file

Create `tests/integration/test_i00064_doc_generation_view_document_url.py`.
Use the existing testcontainer-backed `db_session` fixture (and any
matching dashboard `client` fixture — check `tests/conftest.py` and
`tests/dashboard/conftest.py`). Do NOT connect to the live DB on port
5433.

### 2. Three test cases

#### `test_i00064_reproduces_bug`

Builds the minimal fixture set (project `iw-ai-core`, ProjectDoc
`code-index` whose composite id is `iw-ai-core:code-index`, and a
`DocGenerationJob` with `doc_id="iw-ai-core:code-index"` and
`public_id="DOC-00001"`). Calls
`JobsAggregator(db_session).get_job(project_id="iw-ai-core",
job_type="doc_generation", job_id="DOC-00001")` and asserts:

- `row is not None`
- `row.raw["doc_id"] == "code-index"` (the inner identifier)
- `":" not in row.raw["doc_id"]` (no composite leak)
- `row.raw["doc_id"] != "iw-ai-core:code-index"` (explicit anti-shape)

This is the **falsifiable reproduction**: against the pre-fix code on
`main`, it would fail with `row.raw["doc_id"] == "iw-ai-core:code-index"`.

#### `test_i00064_view_document_link_resolves`

Same fixture set as above. Use the dashboard `client` fixture (FastAPI
TestClient). Build the URL the way the template does:

```python
row = aggregator.get_job(project_id="iw-ai-core", job_type="doc_generation",
                         job_id="DOC-00001")
url = f"/project/iw-ai-core/docs/{row.raw['doc_id']}"
response = client.get(url, follow_redirects=False)
assert response.status_code == 200, (
    f"Expected 200 from {url!r}, got {response.status_code}: "
    f"{response.text[:200]}"
)
# Optional but encouraged: assert the doc title appears in HTML
assert "code-index" in response.text or "Code Index" in response.text
```

This proves the **end-to-end** link the user sees actually works.

#### `test_i00064_orphan_doc_id_is_none`

Build a `DocGenerationJob` with `doc_id=None` (orphan). Assert:

- `row.raw["doc_id"] is None`

Also build a second case where `doc_id` is set to a composite id whose
ProjectDoc row has been deleted (or simply was never inserted). Assert
the same: `row.raw["doc_id"] is None`. This protects the existing
template guard `{% if raw.get('doc_id') %}` from a regression.

(If the FK constraint prevents inserting a `DocGenerationJob` with a
`doc_id` that has no matching `ProjectDoc`, simulate the orphan by
inserting a `ProjectDoc`, building the job, then `db.delete(doc)` and
`db.flush()` — `ondelete=SET NULL` will null out the FK.)

### 3. Fixture rules — READ CAREFULLY

From `CLAUDE.md` and `tests/CLAUDE.md`:

- **NEVER** connect tests to live DB (port 5433) — use testcontainers
  only.
- **NEVER** call `importlib.reload(orch.config)` — use
  `monkeypatch.delenv()`.
- **NEVER** mock the database in integration tests — FOR UPDATE locking
  can't be tested otherwise.
- **MUST** replace psycopg2 URLs in testcontainers:
  `url.replace("postgresql+psycopg2://", "postgresql+psycopg://")`.
- **MUST** run `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after
  `Base.metadata.create_all()` (the existing `db_session` fixture
  already does this — just use it).
- **CRITICAL**: `DaemonEvent.metadata` is named `event_metadata` in
  Python (not relevant here, but a reminder).

### 4. Naming conventions

- File name: `tests/integration/test_i00064_doc_generation_view_document_url.py`
- Function names: `test_i00064_reproduces_bug`,
  `test_i00064_view_document_link_resolves`,
  `test_i00064_orphan_doc_id_is_none`.
- Each test has a one-paragraph docstring explaining what it asserts
  and why it would fail pre-fix.

### 5. Imports / helpers

If `tests/integration/test_i00059_doc_generation_get_job.py` exposes
fixture-construction helpers (or a shared `helpers/` module is
available), reuse them. If not, inline minimal `_make_project`,
`_make_doc`, `_make_doc_generation_job` helpers in the new file — keep
them small and readable.

## Project Conventions

- Use `pytest` fixture style (no class-based test cases).
- Type hints required on test signatures.
- One assertion concept per test (the three tests above).
- No `time.sleep()`, no flaky retries.
- Use `db_session.flush()` for primary-key generation, `db_session.commit()`
  only when the dashboard TestClient needs to see committed state.

## TDD Requirement

The implementation in S01 has already been done. For S03, you are the
**RED-then-GREEN check**:

1. Write the tests assuming the fix is applied (they should pass on the
   current branch).
2. Mentally check (or run a one-shot sanity revert if your tooling
   allows) that they would FAIL on the pre-fix code. The reproduction
   test must be **falsifiable**.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`:

1. `make format` — auto-fixes formatting drift.
2. `make typecheck` — zero errors involving the new test file.
3. `make lint` — zero errors.

## Test Verification (NON-NEGOTIABLE)

After writing the tests:

1. Run `make test-integration` — the three new tests must PASS.
2. Run `make test-unit` — must PASS (no collateral regressions).
3. Do NOT report `tests_passed: true` unless both pass.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "tests-impl",
  "work_item": "I-00064",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/integration/test_i00064_doc_generation_view_document_url.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed (3 new tests)",
  "blockers": [],
  "notes": ""
}
```
