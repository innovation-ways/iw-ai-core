# CR-00030_S02_CodeReview_prompt

**Work Item**: CR-00030 -- Show remaining time (not end time) on Claude 5h usage slot
**Step Being Reviewed**: S01 (backend-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits

(Standard policy — see CLAUDE.md and docs/IW_AI_Core_Agent_Constraints.md.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy — this work item touches no migrations and no DB schema.)

## Input Files

- **Runtime step state** — prefer `uv run iw item-status CR-00030 --json`.
- `ai-dev/active/CR-00030/CR-00030_CR_Design.md`
- `ai-dev/active/CR-00030/reports/CR-00030_S01_Backend_report.md`
- `orch/llm_usage.py` (the only file S01 should have changed)

## Output Files

- `ai-dev/active/CR-00030/reports/CR-00030_S02_CodeReview_report.md`

## Context

Review the backend change in S01. The change is small and surgical — the review must be just as surgical.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

If either reports NEW violations in `orch/llm_usage.py`, file each as a CRITICAL finding with `category: "conventions"`, the file/line, and the exact tool message. Do NOT auto-fix.

## Review Checklist

### 1. Scope discipline

- Did S01 modify ONLY `orch/llm_usage.py`? Any other file changed (especially `dashboard/templates/fragments/llm_usage_footer.html`, `dashboard/routers/usage.py`, or `_format_reset`) is a CRITICAL scope violation.
- Did S01 leave `_format_resets_at` intact? It must still be defined and still called by the 7d branch. Removing it is CRITICAL — it breaks the 7d label.
- Did S01 preserve the `_claude_usage()` return-dict shape (`block_pct`, `week_pct`, `block_reset`, `week_reset`)? Renaming or removing keys is CRITICAL — the dashboard router reads them by name.

### 2. Helper correctness

Inspect `_format_remaining_from_ts`:
- Returns `None` for `resets_at <= 0`.
- Returns `None` for any `resets_at` strictly in the past relative to `datetime.now(UTC).timestamp()`.
- Returns `"0m"` (not `None`) when `remaining_s` is between 0 and 59 inclusive.
- Returns `"<M>m"` for `0 <= remaining_s < 3600` with no leading zero, no leading `"0h "`.
- Returns `"<H>h <M>m"` for `remaining_s >= 3600` with no leading zero on hours, single space, lowercase `h`/`m`.
- Uses `datetime.now(UTC).timestamp()`, not `time.time()` or `datetime.utcnow()` (deprecated).

Bugs in any of the above are HIGH or CRITICAL depending on whether they break the AC.

### 3. Naming & docstring

- Helper name should be private (`_` prefix) and clearly distinct from `_format_reset` (millis) and `_format_resets_at` (wall-clock timestamp).
- Docstring should state input units (Unix timestamp, seconds) and output formats. MEDIUM_FIXABLE if absent or misleading.
- Module docstring (lines 1-23) should mention the 5h-vs-7d format split. MEDIUM_SUGGESTION if not updated.

### 4. Conventions (`CLAUDE.md`, `orch/CLAUDE.md`)

- `from __future__ import annotations` present at top — already in file, do not add a duplicate.
- No new imports unless necessary; if added, they sort with `ruff format`.
- Type hints: `float` in, `str | None` out (PEP 604 union, not `Optional[str]`).
- No `print` statements, no debug logging at INFO level for hot path.

### 5. No unrelated edits

- No reformatting of untouched lines (creates noisy diffs).
- No "drive-by" refactors of `_format_reset` or `_format_resets_at`.
- No edits to `_cache` / TTL logic — pre-existing staleness near deadline is documented in the design doc as **not a regression**.

### 6. Testing

- Tests are S03's responsibility — don't fail S02 on coverage gaps. But verify `make test-unit` still passes after S01 (no regressions in the existing 7d-cache tests).

## Test Verification (NON-NEGOTIABLE)

Run `make test-unit`. Report results faithfully.

## Severity Levels

(Standard table — see template.)

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "CR-00030",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
