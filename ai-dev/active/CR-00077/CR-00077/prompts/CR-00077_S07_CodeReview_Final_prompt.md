# CR-00077_S07_CodeReview_Final_prompt

**Work Item**: CR-00077 -- Overlap details popup (read-only)
**Step**: S07
**Agent**: code-review-final-impl

---

## ⛔ Docker is off-limits
(Standard policy.)

## ⛔ Migrations: agents generate, daemon applies
This CR adds no migrations.

## Scope

Global cross-agent review across all six implementation/review steps. Verify each Acceptance Criterion end-to-end and check scope discipline.

## Input Files

- `ai-dev/active/CR-00077/CR-00077_CR_Design.md`
- All step reports under `ai-dev/active/CR-00077/reports/`.
- Full diff: `git diff origin/main..HEAD`.

## Output Files

- `ai-dev/active/CR-00077/reports/CR-00077_S07_CodeReview_Final_report.md` — global review findings.

## Checks

### 1. Acceptance Criteria coverage

| AC | Owner | Verification |
|----|-------|--------------|
| AC1 — clickable pill | S03 + S14 | Trigger button present in `batch_items_rows.html`; browser_verification clicks it. |
| AC2 — grouped sections | S01 helper + S03 partial + S05 test | Happy-path test asserts blocking_item_ids appear; partial loops over `sections`. |
| AC3 — no truncation | S05 test | Every glob asserted individually. |
| AC4 — dismissal (Esc, backdrop, ×) | S03 + S14 | Script in partial implements all three; browser_verification covers at least one. |
| AC5 — 404 when no recent event | S01 + S05 | Endpoint returns 404; test asserts 404 + body content. |
| AC6 — read-only | S04 + S06 | No POST endpoints, no form elements in the modal partial. |

If any AC has no concrete verification artifact, flag CRITICAL and require a fix-cycle to add coverage.

### 2. Scope discipline

```bash
git diff origin/main -- orch/ executor/ ai-dev/iw-config/
```

Must be empty. Any non-empty diff in `orch/`, `executor/`, or `ai-dev/iw-config/` is a CRITICAL scope violation — this CR is dashboard-only.

```bash
git diff origin/main -- orch/db/migrations/
```

Must be empty.

### 3. Single modal partial

There must be exactly ONE `dashboard/templates/fragments/batch_overlap_modal.html` file, referenced by the `batch_items_rows.html` trigger and structured for CR-00078 reuse. `queue.html` must be unchanged — the Queue-page trigger is out of scope for this CR.

### 4. Tailwind discipline

`dashboard/static/styles.tailwind.css` and `tailwind.config.js` must be unchanged. Only `dashboard/static/styles.css` was appended to (per the plain-CSS-fallback rule from root `CLAUDE.md`).

### 5. Lint + format + type-check on the diff

Run `make lint`, `make format-check`, `make type-check` on the full diff. Zero new errors.

### 6. Targeted test verification

Run only the two new test modules:

```bash
uv run pytest tests/unit/test_batch_overlap_grouping.py tests/dashboard/test_batch_overlap_modal.py -v
```

Both must pass. Do NOT run `make test-unit` or `make test-integration` here — the full suite is owned by QV gates S11/S12; re-running it inside this review step duplicates that work and risks a step timeout (see I-00073).

### 7. Carry-forward for CR-00078

Note in your report whether the modal partial's block structure is extensible for CR-00078 (which adds per-file Ignore buttons inside `<li>` rows and a master button at the bottom). If the layout has hardcoded structure that would force CR-00078 to rewrite it, flag MEDIUM with a refactor suggestion.

## Severity

- CRITICAL: scope violation, missing AC artifact, broken read-only contract.
- HIGH: failing test suite, missing AC test that can't be salvaged by S14.
- MEDIUM: rigid template structure that pushes work into CR-00078.

## Subagent Result Contract

```json
{
  "step": "S07",
  "agent": "code-review-final-impl",
  "work_item": "CR-00077",
  "completion_status": "complete",
  "files_changed": [],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "<X> passed across unit + integration",
  "tdd_red_evidence": "n/a — final review step",
  "blockers": [],
  "notes": "<one-line summary>"
}
```
