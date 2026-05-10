# I-00077_S06_CodeReview_prompt

**Work Item**: I-00077 — Doc-generation jobs abort on missing editorial guide and the failure is invisible on the Docs page
**Step Being Reviewed**: S05 (tests-impl)
**Review Step**: S06

---

## ⛔ Docker is off-limits

No Docker state-changing commands. Allowed: testcontainers via pytest fixtures; read-only `docker ps|inspect|logs`; `./ai-core.sh` / `make`. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

No migrations in this item.

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00077 --json`.
- `ai-dev/active/I-00077/I-00077_Issue_Design.md` — design document (read **Test to Reproduce**, **Acceptance Criteria**, **TDD Approach**)
- `ai-dev/active/I-00077/reports/I-00077_S05_tests-impl_report.md` — S05 report
- All files in S05's `files_changed` (expect `tests/unit/test_doc_type_guide_service.py`, `tests/integration/test_doc_type_guides.py` and/or `tests/integration/test_i00077_doc_job_editorial_fallback.py`, `tests/dashboard/test_docs_running_jobs.py`)
- The implementation files under review: `orch/doc_service.py`, `dashboard/routers/docs.py`, `dashboard/templates/docs_library.html`, `dashboard/templates/fragments/docs_running_jobs.html`

## Context

Review S05's tests. The central question: would these tests have FAILED against the pre-fix code, and do they verify **semantic correctness** (specific values), not just response shape?

## Read the Design Document FIRST

- Read `## Acceptance Criteria` (AC1–AC4) and `## TDD Approach` in full. Every test file the design names must be present in S05's `files_changed`; a missing one is a **CRITICAL** finding.
- Map each AC to a concrete assertion in the tests. AC1 → `_effective_guide` / `create_doc_job` `_default` snapshot; AC3 → failed job in the strip + dismiss control + `docJobFailed` handler; AC4 → the reproduction tests exist and pass. AC2 (skill wording) is not unit-testable — confirm the design acknowledges that and don't penalise its absence from the test suite.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

NEW violations in changed files vs `main` → CRITICAL (`category: conventions`, file/line + code/message). If `make` is unavailable, STOP and raise a blocker.

## Review Checklist

### 1. RED→GREEN integrity

- `_effective_guide` `_default` test: asserts the **exact** seeded `_default` markdown (not `is not None`). Would fail pre-fix (pre-fix returns `None`).
- `create_doc_job` test: seeds `_default` explicitly (tests don't run migrations, so `doc_type_guides` is empty otherwise), uses a `diagram` doc with no instance/`doc_type` guide, asserts `job.guide_snapshot == <seeded string>` and `job.section_guides_snapshot is None`. The instance-guide-wins sibling exists.
- `docs_running_jobs` test: seeds a `failed` job with a recent `completed_at`; asserts the `error` string is present, the failed-row distinct CSS state (attribute-scoped, not bare substring — I-00067), a Dismiss control present, a Cancel control **absent** from that row. A bounded-window case (old failed job excluded) exists. A running-job-still-works regression case exists.
- `docs_library.html` `docJobFailed` handler test exists (rendered HTML or template source).

### 2. Test quality

- Semantic assertions throughout (no shape-only `assert key in data` / `len > 0`).
- Tests isolated and deterministic (no reliance on the live DB on port 5433; no leftover rows across tests; no real network).
- Correct test-dir placement: dashboard tests under `tests/dashboard/`, DB tests under `tests/integration/`, mock-session tests under `tests/unit/`.
- Test names clearly describe what they verify.

### 3. No production-code edits in this step

- S05 is a tests-only step. If `orch/doc_service.py` / `dashboard/**` were modified here (beyond test files), flag it (HIGH) — production fixes belong to S01/S03 and should already be in place.

## Test Verification (NON-NEGOTIABLE)

Run the unit suite to confirm no regressions, plus the new files:

```bash
uv run pytest tests/unit/ -q
uv run pytest tests/integration/test_doc_type_guides.py tests/dashboard/test_docs_running_jobs.py -v
```

Report results accurately. (Do not run the full integration suite — that's the QV gate's job; the targeted files above are sufficient for review.)

## Severity Levels

CRITICAL / HIGH / MEDIUM (fixable) / MEDIUM (suggestion) / LOW — only the first three trigger a fix cycle.

## Review Result Contract

```json
{
  "step": "S06",
  "agent": "CodeReview",
  "work_item": "I-00077",
  "step_reviewed": "S05",
  "verdict": "pass|fail",
  "findings": [{"severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW", "category": "architecture|code_quality|conventions|security|testing", "file": "", "line": 0, "description": "", "suggestion": ""}],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```

`verdict`: `pass` only if zero CRITICAL/HIGH/MEDIUM(fixable) findings.
