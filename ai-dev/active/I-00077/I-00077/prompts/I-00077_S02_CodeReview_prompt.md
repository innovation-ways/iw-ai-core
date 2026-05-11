# I-00077_S02_CodeReview_prompt

**Work Item**: I-00077 — Doc-generation jobs abort on missing editorial guide and the failure is invisible on the Docs page
**Step Being Reviewed**: S01 (backend-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits

No Docker state-changing commands. Allowed: testcontainers via pytest fixtures; read-only `docker ps|inspect|logs`; `./ai-core.sh` / `make` targets. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

No migrations in this item. Do not apply migrations to the live DB.

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00077 --json`.
- `ai-dev/active/I-00077/I-00077_Issue_Design.md` — design document
- `ai-dev/active/I-00077/reports/I-00077_S01_backend-impl_report.md` — S01 report
- All files in S01's `files_changed` (expect: `orch/doc_service.py`, `skills/iw-doc-generator/SKILL.md`, `skills/iw-doc-system/SKILL.md`, `tests/unit/test_doc_type_guide_service.py`)

## Output Files

- `ai-dev/active/I-00077/reports/I-00077_S02_CodeReview_report.md` — review report

## Context

Review S01's implementation of Fix #1 (`_effective_guide` `_default` fallback) and Fix #2 (skill "Job lifecycle" wording). Read the design doc first — note **AC1**, **AC2**, and the **TDD Approach** test files by name; carry those into your checklist.

## Read the Design Document FIRST

- Read `## Acceptance Criteria` (AC1, AC2) and `## TDD Approach` in full.
- The design names `tests/unit/test_doc_type_guide_service.py` as carrying the `_effective_guide` reproduction test. Confirm it appears in S01's `files_changed` and that the test genuinely fails pre-fix / passes post-fix.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

Any NEW violation in the changed files vs `main` → a **CRITICAL** finding (`category: conventions`, with file/line and the exact code/message). If `make` is unavailable, STOP and raise a blocker.

## Review Checklist

### 1. Fix #1 correctness

- Resolution order is exactly: instance guide → `get_type_guide(doc_type)` → `get_type_guide("_default")` → `None`.
- The `doc_type == "_default"` case does not double-query / infinite-loop.
- `create_doc_job` is unchanged (it already stores `_effective_guide(...)` into `guide_snapshot`); no incidental edits there.
- `section_guides_snapshot` behaviour is unchanged (still `None` for docs with no section guides — that is correct, not a bug to "fix").
- No behaviour change for docs that already have an instance guide or a `doc_type`-specific guide.

### 2. Fix #2 correctness

- Both `skills/iw-doc-generator/SKILL.md` AND `skills/iw-doc-system/SKILL.md` were edited, consistently.
- The new wording clearly says: null `section_guides_snapshot`/`guide_snapshot` is normal → proceed using the static `references/…-guidelines.md`; abort with `--error` only on a non-zero `iw doc-job-status` exit (or a concrete generation blocker), never merely because the snapshot was empty.
- The pre-existing "if `doc-job-status` exits non-zero, close the job immediately" guidance is retained, not deleted.
- Markdown style matches the surrounding sections.

### 3. Conventions / quality / security

- `CLAUDE.md` conventions respected; no hardcoded values; no scope creep into the dashboard layer (that's S03).

### 4. Testing

- `tests/unit/test_doc_type_guide_service.py` covers the new fallback (instance → doc_type → `_default`) with semantic assertions, and the `_default`-missing case still returns `None`.

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/unit/test_doc_type_guide_service.py -v
```

Report results accurately.

## Severity Levels

CRITICAL / HIGH / MEDIUM (fixable) / MEDIUM (suggestion) / LOW — only the first three trigger a fix cycle.

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "I-00077",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [{"severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW", "category": "architecture|code_quality|conventions|security|testing", "file": "", "line": 0, "description": "", "suggestion": ""}],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```

`verdict`: `pass` only if zero CRITICAL/HIGH/MEDIUM(fixable) findings.
