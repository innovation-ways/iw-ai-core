# I-00058_S07_CodeReview_Final_prompt

**Work Item**: I-00058 — DocGenerationJob IDs are UUIDs instead of sequential DOC-NNNNN identifiers
**Review Step**: S07 (Final Review)
**Implementation Steps Reviewed**: S01..S05

---

## ⛔ Docker is off-limits

Allowed exceptions: testcontainers (pytest), read-only introspection, `./ai-core.sh` / `make` targets.
Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Do NOT run `alembic upgrade/downgrade/stamp` against the live DB.
Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status I-00058 --json`
- `ai-dev/active/I-00058/I-00058_Issue_Design.md` — Design document
- All implementation reports: `ai-dev/active/I-00058/reports/I-00058_S01_Database_report.md`, `I-00058_S03_Backend_report.md`, `I-00058_S05_Tests_report.md`
- All per-agent review reports: `I-00058_S02_CodeReview_Database_report.md`, `I-00058_S04_CodeReview_Backend_report.md`, `I-00058_S06_CodeReview_Tests_report.md`
- All changed files listed across all implementation reports

## Output Files

- `ai-dev/active/I-00058/reports/I-00058_S07_CodeReview_Final_report.md` — Final review report

## Context

You are performing the **final cross-agent review** of ALL implementation for **I-00058**. Three agents built this fix in sequence:

- **S01 (Database)**: Added `public_id TEXT UNIQUE NULL` column to `DocGenerationJob` + Alembic migration.
- **S03 (Backend)**: Added `@event.listens_for(DocGenerationJob, "before_insert")` listener in `models.py`; updated `_fetch_doc_generation` and `_get_doc_generation` in `aggregator.py` to surface `public_id` as display ID.
- **S05 (Tests)**: Wrote reproduction test + sequential increment test + aggregator unit tests.

Your job: verify everything integrates correctly end-to-end and no cross-cutting issue was missed.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

## Review Checklist

### 1. Completeness vs Design Document
- Is the `public_id` column present in both the model (S01) and the migration (S01)?
- Is the `before_insert` listener in `models.py` (S03) using prefix `'DOC'`?
- Does the aggregator (S03) expose `public_id` in both `_fetch_doc_generation` and `_get_doc_generation`?
- Are there reproduction, sequential, and aggregator tests (S05)?
- Is `orch/doc_service.py` unchanged (UUID PK stays)?

### 2. Cross-agent integration
- Does the `public_id` column defined in S01 match what the listener in S03 populates? (Same column name, same type.)
- Does the aggregator in S03 reference `DocGenerationJob.public_id` — does that attribute exist after S01's model change?
- Does the `_get_doc_generation` lookup by `public_id` use the correct SQLAlchemy 2.0 `select()` pattern (not legacy `query()`)?

### 3. Migration correctness
- Does the migration chain from S01 include only the `public_id` column addition?
- No unrelated schema changes captured?

### 4. Test semantic correctness (I003 lesson — mandatory check)
- Does the reproduction test assert `re.match(r"^DOC-\d{5}$", job.public_id)` or equivalent exact regex?
- Does the sequential test assert exact values `"DOC-00001"` and `"DOC-00002"`?
- Does any test only check shape (non-null, non-empty)? Flag as HIGH.

### 5. Legacy row safety
- Does the aggregator's `job_id` fallback to `job.id` (UUID) when `public_id is None`?
- Does `_get_doc_generation` fall back to PK lookup when no row matches by `public_id`?
- Is there no `NOT NULL` constraint on `public_id` in the migration (would break legacy rows)?

### 6. Architecture compliance
- No new cross-layer imports?
- SQLAlchemy 2.0 style throughout?

## Test Verification (NON-NEGOTIABLE)

Run the full test suite:

```bash
make test-unit
make allure-integration
```

Both must pass with zero failures. Integration test failure is a CRITICAL finding.

## Review Result Contract

```json
{
  "step": "S07",
  "agent": "code-review-final-impl",
  "work_item": "I-00058",
  "steps_reviewed": ["S01", "S02", "S03", "S04", "S05", "S06"],
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```
