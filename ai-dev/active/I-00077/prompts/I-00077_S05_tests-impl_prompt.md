# I-00077_S05_tests-impl_prompt

**Work Item**: I-00077 — Doc-generation jobs abort on missing editorial guide and the failure is invisible on the Docs page
**Step**: S05
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY command that changes Docker container/volume/network state.
Allowed: testcontainers spun up by pytest fixtures (they self-label and self-destruct via Ryuk);
read-only `docker ps|inspect|logs`; `./ai-core.sh` / `make` targets.
If a task seems to require a prohibited command, STOP and raise a blocker.
Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

No migrations in this item. Tests must run migrations only inside testcontainer fixtures
(`tests/conftest.py` already does this — you don't call it directly). Per `CLAUDE.md`: tests
build the schema via `Base.metadata.create_all()` then run `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL`
— they do **not** run Alembic migrations, so the `doc_type_guides._default` row is **not**
auto-seeded in tests; seed it explicitly in your integration test.

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00077 --json`.
- `ai-dev/active/I-00077/I-00077_Issue_Design.md` — design document (read the **Test to Reproduce** and **TDD Approach** sections in full)
- `ai-dev/active/I-00077/reports/I-00077_S01_backend-impl_report.md`, `ai-dev/active/I-00077/reports/I-00077_S03_frontend-impl_report.md` — what was changed
- Existing tests to extend: `tests/unit/test_doc_type_guide_service.py`, `tests/integration/test_doc_type_guides.py`, `tests/dashboard/test_docs_running_jobs.py`
- For fixture patterns: `tests/conftest.py`, `tests/integration/conftest.py`, `tests/dashboard/conftest.py`, `tests/CLAUDE.md`

## Output Files

- `ai-dev/active/I-00077/reports/I-00077_S05_tests-impl_report.md` — step report
- New/modified test files (see Requirements). If a new integration file is cleaner than extending an existing one, create `tests/integration/test_i00077_doc_job_editorial_fallback.py` (it's in the allowed-paths list).

## Context

You are writing the reproduction + regression tests for I-00077. S01 fixed `_effective_guide` (now falls back to the `_default` `DocTypeGuide`) and clarified the doc-generation skills; S03 widened `docs_running_jobs` to include recently-`failed` jobs and made the catalogue page surface failures. Your tests must (a) fail against the pre-fix code, (b) pass against the current code, and (c) verify **semantic correctness**, not just response shape.

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed.
But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert "permissions" in data` (shape only)
- GOOD: `assert "brands:manage" in permissions` (semantic — verifies specific expected value)
- GOOD: `assert "*" not in permissions` (semantic — verifies unwanted value is absent)

Apply the same standard here:
- BAD: `assert job.guide_snapshot is not None` — GOOD: `assert job.guide_snapshot == "<the exact _default markdown you seeded>"`
- BAD: `assert "failed" in html` — GOOD: assert the failed row's distinct class via the attribute-scoped form (`'class="docs-rjob-failed"' in html` or a `class\s*=\s*"[^"]*…"` regex), the seeded `error` string is present, AND a Cancel control is *absent* from that row.

## Requirements

### 1. Reproduction test — `_effective_guide` falls back to `_default` (unit)

In `tests/unit/test_doc_type_guide_service.py`, add a `TestEffectiveGuide` class (or extend) covering the **three-level resolution order**, using a `MagicMock` session with `side_effect` (the file already uses `MagicMock` sessions):

- instance guide present → returns the instance guide (no `get_type_guide` call needed).
- no instance guide, `doc_type` guide present → returns the `doc_type` guide.
- no instance guide, no `doc_type` guide, `_default` present → returns the `_default` guide. **This is the reproduction case** — assert the exact `_default` markdown string. (Confirm it returns `None` against pre-fix code if you can; at minimum it must pass now.)
- nothing present (`_default` also missing) → returns `None`.

### 2. Reproduction test — `create_doc_job` snapshots the `_default` guide for a diagram doc (integration)

In `tests/integration/test_doc_type_guides.py` (or the new `tests/integration/test_i00077_doc_job_editorial_fallback.py`), using the testcontainer DB fixture:

- Seed a `DocTypeGuide(doc_type="_default", guide_md=<known string>)` via `svc.save_type_guide("_default", ...)` (or directly). Do **not** seed a `diagram` type guide or any instance guide.
- Create a `ProjectDoc` with `doc_type=DocType.diagram` for some project (mirror how other tests in the file build a `ProjectDoc`; ensure the project row exists if the test setup requires it).
- Call `DocService(db).create_doc_job(project_id, doc_id)`.
- Assert `job.guide_snapshot == <the known string>` (it was `None` before the fix), and `job.section_guides_snapshot is None` (unchanged — a diagram has no section guides).
- Add a no-regression sibling: a doc with an explicit instance guide still snapshots that instance guide unchanged (instance wins over `_default`).

### 3. Regression test — failed doc job appears in the running-jobs strip (dashboard)

In `tests/dashboard/test_docs_running_jobs.py`, using the `client` + db fixtures (this file MUST stay under `tests/dashboard/` — the `client` fixture is only registered in `tests/dashboard/conftest.py`):

- Seed a `ProjectDoc` (non-research `doc_type`) and a `DocGenerationJob` for it with `status=JobStatus.failed`, `error="<known error>"`, `completed_at=datetime.now(UTC)` (recent). Mirror existing setup in the file.
- `GET /project/<project_id>/api/docs/running-jobs` → 200; the response HTML contains the seeded `error` string, carries the failed-row distinct CSS state (attribute-scoped assertion), and includes a **Dismiss** control for that row but **not** a Cancel control.
- Add a no-regression case: a `running` job still renders with its spinner/Cancel/EventSource as before (assert the EventSource `<script>` / Cancel button is present for the running row).
- Add a boundedness case: a `failed` job whose `completed_at` is well over 10 minutes ago does **not** appear.
- Assert `docs_library.html` renders a `docJobFailed` handler: render the catalogue page via the `client` fixture and assert the page HTML/inline script contains `addEventListener('docJobFailed'` (or equivalent) and the `components/toast.html` `showToast` reference. (If rendering the full page in a dashboard test is awkward, assert on the template source as the existing tests in this area do — but prefer the rendered-HTML route.)

## Test-file placement (NON-NEGOTIABLE)

- Tests that drive a FastAPI route / render a dashboard template via the `client` fixture → `tests/dashboard/`.
- Tests needing the testcontainer DB → `tests/integration/`.
- Pure-Python / `MagicMock`-session tests → `tests/unit/`.
A `tests/dashboard/` test placed under `tests/unit/` or `tests/integration/` fails with `fixture 'client' not found` (I-00067).

## TDD Requirement

These tests ARE the RED phase artifact. They must be written so they would fail against pre-fix code (you may sanity-check by reasoning about the pre-fix behaviour described in the design doc). Do **NOT** `git checkout`/`git stash` source files at runtime to "prove RED" — that's a design-time exercise, not part of this step.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `complete`:

1. `make format`
2. `make typecheck`
3. `make lint`

Record results in the `preflight` object.

## Test Verification (NON-NEGOTIABLE)

Run **only the test files you wrote/modified** — do NOT run `make test-unit` / `make test-integration` (those are downstream QV gates and will blow this step's budget — see I-00073/S03 post-mortem):

```bash
uv run pytest tests/unit/test_doc_type_guide_service.py tests/integration/test_doc_type_guides.py tests/dashboard/test_docs_running_jobs.py -v
# (add tests/integration/test_i00077_doc_job_editorial_fallback.py if you created it)
```

Do not report `tests_passed: true` unless every file you touched passes with zero failures.

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "tests-impl",
  "work_item": "I-00077",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["tests/unit/test_doc_type_guide_service.py", "tests/integration/test_doc_type_guides.py", "tests/dashboard/test_docs_running_jobs.py"],
  "preflight": {"format": "ok|fixed|skipped:<reason>", "typecheck": "ok|skipped:<reason>", "lint": "ok|skipped:<reason>"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
