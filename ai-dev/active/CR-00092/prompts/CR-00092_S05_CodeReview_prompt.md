# CR-00092_S05_CodeReview_prompt

**Work Item**: CR-00092 -- Column-docs baseline scrub
**Steps Being Reviewed**: S01–S04 (all four database-impl waves)
**Review Step**: S05

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY docker commands that change container/volume/network state. Testcontainers from pytest fixtures and read-only introspection are the only exceptions. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This CR adds NO migration. If the diff includes any file under `orch/db/migrations/versions/**`, that is a CRITICAL scope-creep finding.

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00092 --json`.
- `ai-dev/active/CR-00092/CR-00092_CR_Design.md` — read end-to-end, especially Acceptance Criteria (AC1–AC8), Notes (description sourcing rule + gate-surface trade-off), and Impacted Paths.
- `ai-dev/work/CR-00092/reports/CR-00092_S01_Database_report.md` through `S04_Database_report.md` — all four wave reports.
- `orch/db/models.py` (modified)
- `Makefile` and `.github/workflows/test-quality.yml` (modified — both should now lack `|| true` on the `check-column-docs` step)
- `docs/IW_AI_Core_Testing_Strategy.md` and `ai-dev/work/TESTS_ENHANCEMENT.md` (modified)
- Confirm `orch/db/column_docs_baseline.txt` is DELETED (`git ls-files` returns nothing).

## Output Files

- `ai-dev/work/CR-00092/reports/CR-00092_S05_CodeReview_report.md`.

## Context

You are reviewing the four-wave column-docs scrub + gate flip for CR-00092. Read the design FIRST — especially the Notes section, which governs every `doc=` string. Then walk the diff systematically.

## Read the Design Document FIRST

Specifically:
- AC1–AC8 — each is a mandatory check, exercised below.
- Notes → Description sourcing rule — schema doc first, inferred second; NEVER edit `docs/IW_AI_Core_Database_Schema.md`.
- Notes → Wave boundaries are mechanical — the wave splits in the Implementation Plan are NOT renegotiated.
- Impacted Paths — exactly six files (plus the implicit `ai-dev/active/CR-00092/**` and `ai-dev/work/CR-00092/**`).

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint          # ruff check on all modified files
make format        # ruff format --check
```

Any NEW violation in `orch/db/models.py` (the heaviest-touch file) → CRITICAL with `"category": "conventions"`.

## Scope Discipline — Implicitly Allowed Paths

`ai-dev/active/CR-00092/**`, `ai-dev/archive/CR-00092/**`, and `ai-dev/work/CR-00092/**` are implicitly allowed even though the manifest doesn't list them. Do NOT flag those.

### Scope diff — directional

```bash
git diff main...HEAD --name-only
git status -s
```

Expected list (besides the implicit allows): `orch/db/models.py`, `orch/db/column_docs_baseline.txt` (D), `Makefile`, `.github/workflows/test-quality.yml`, `docs/IW_AI_Core_Testing_Strategy.md`, `ai-dev/work/TESTS_ENHANCEMENT.md`. ANYTHING else → CRITICAL (especially: `docs/IW_AI_Core_Database_Schema.md`, any `orch/db/migrations/versions/**` file, any `tests/**` change beyond auto-format).

## Review Checklist

### 1. Wave-count consistency (cross-step numeric anchor)

Read each wave report's `wave_scrub_count`. Confirm:
- S01 `wave_scrub_count` = 103
- S02 `wave_scrub_count` = 90
- S03 `wave_scrub_count` = 123
- S04 `wave_scrub_count` ≈ 134 (the remainder — may differ slightly if a class was mis-counted upstream, but should be within ±5 of 134)
- S04 `cumulative_scrub_count` = 450
- S04 `remaining_baseline_count` = 0
- S04 `baseline_deleted` = true
- S04 `gate_flipped_in_makefile` = true
- S04 `gate_flipped_in_gh_workflow` = true
- S04 `ac8_demonstrated` = true

Mismatch → HIGH finding.

### 2. Scanner exits clean (AC1)

```bash
uv run python scripts/check_db_column_docs.py --baseline /dev/null
echo "Exit code: $?"
```

Non-zero → CRITICAL.

### 3. Baseline file is gone (AC2)

```bash
git ls-files orch/db/column_docs_baseline.txt
# Expected: (empty)
test ! -e orch/db/column_docs_baseline.txt && echo "absent" || echo "PRESENT"
# Expected: absent
```

Present → CRITICAL.

### 4. Gate is blocking — Makefile (AC3) and GH workflow (AC4)

```bash
grep -n "check-column-docs" Makefile
grep -n "check-column-docs" .github/workflows/test-quality.yml
```

Either match still contains `|| true` → CRITICAL.

### 5. `make quality` exits 0 (AC5)

```bash
make quality
echo "Exit code: $?"
```

Non-zero → CRITICAL (it means the scrub missed at least one column).

### 6. Docs and tracker updated (AC6)

- `docs/IW_AI_Core_Testing_Strategy.md` §5: find the `check-column-docs` row; confirm it no longer says warn-first / burn-in and references CR-00092.
- `ai-dev/work/TESTS_ENHANCEMENT.md` §8 row 4.5.followup: Status = `✅ (CR-00092, 2026-05-28, blocking)`, Link = CR-00092.
- `ai-dev/work/TESTS_ENHANCEMENT.md` §11: new changelog entry at the top dated 2026-05-28 mentioning CR-00092, the 450-count, baseline deletion, gate flip, and the AC8 demonstration.
- Header version bumped (v1.8 → v1.9).

Any missing → HIGH (MEDIUM_FIXABLE if the row is updated but the wording differs from the design).

### 7. Scope discipline (AC7)

The diff list must be **exactly** the six files listed in Impacted Paths plus implicitly-allowed `ai-dev/**`. Specifically:
- `docs/IW_AI_Core_Database_Schema.md` NOT in diff → required.
- No file under `orch/db/migrations/versions/` → required.
- No `tests/**` change apart from auto-format → required.

Violation → CRITICAL.

### 8. `doc=` quality spot-check

Sample 10 columns across the four waves (e.g. `WorkItem.id`, `StepRun.status`, `DaemonEvent.event_metadata`, `IdSequence.next_value`, `ChatTab.tab_id`, `OssFinding.severity`, `KeepAliveSlot.slot_id`, `Project.id`, `BatchItem.status`, `FixCycle.cycle_index`). For each:
- Is the `doc=` argument present?
- Is it one line (no multi-line strings)?
- Does it describe WHAT the column holds, not implementation mechanics?
- For SAEnum columns, does it reference the enum class name?
- For FK columns, does it name the referenced table?
- For `DaemonEvent.event_metadata` specifically: confirm `doc=` is on the `Column(...)` declaration (NOT on the python attribute alias).

Generic placeholders ("ID column.", "Status.") that add nothing over the column name → MEDIUM_FIXABLE.

### 9. AC8 deliberate-break demonstration recorded in S04 report

Read the "AC8 deliberate-break demonstration" section of `CR-00092_S04_Database_report.md`. Confirm:
- A specific column was named.
- The breaking-side `make check-column-docs` invocation exited non-zero and the output named that column.
- The restoring-side invocation exited 0.
- `git diff` was confirmed empty post-restore.

Missing or unconvincing → HIGH.

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/orch/db/test_column_docs.py -v
```

Plus a narrow unit-test sweep to confirm no model-import regression (the scanner walks `Base.registry.mappers`, so a broken `mapped_column` argument would break import):

```bash
uv run pytest tests/unit/ -k "model or column" -v
```

## Severity Levels

Same as the standard template (CRITICAL / HIGH / MEDIUM_FIXABLE / MEDIUM_SUGGESTION / LOW).

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "CodeReview",
  "work_item": "CR-00092",
  "step_reviewed": "S01-S04",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "path/to/file.py",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```

- `verdict`: `pass` only if zero CRITICAL + zero HIGH + zero MEDIUM_FIXABLE.
- `mandatory_fix_count`: count of CRITICAL + HIGH + MEDIUM_FIXABLE.
