# I-00056_S02_CodeReview_Backend_prompt

**Work Item**: I-00056 -- Code page lands on a wall of prose — components hidden, hard to scan
**Step Being Reviewed**: S01 (Backend)
**Review Step**: S02

---

## ⛔ Docker is off-limits

Read-only `docker ps/inspect/logs` only. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Do not run alembic upgrade/downgrade/stamp. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status I-00056 --json`.
- `ai-dev/active/I-00056/I-00056_Issue_Design.md`
- `ai-dev/active/I-00056/reports/I-00056_S01_Backend_report.md`
- All files in S01's `files_changed`

## Output Files

- `ai-dev/active/I-00056/reports/I-00056_S02_CodeReview_report.md`

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

NEW violations on changed files → CRITICAL (`category: conventions`).

## Review Checklist

### 1. `wrap_h2_sections_collapsible` correctness

- The first H2 in document order has the `open` attribute on its `<details>` element. Subsequent H2s do NOT have `open`.
- The `<summary>` text matches the H2's text content (whitespace-trimmed; no nested HTML in the summary).
- Body content between an H2 and the next H2 (or end of document) is preserved verbatim — no element loss, no reordering.
- Content BEFORE the first H2 (typically the H1 + intro paragraph) is left at top level (not pulled inside any `<details>`).
- Idempotent: applying the helper twice produces the same string. Verify by walking the implementation; if the helper does not detect already-wrapped sections it must at least be a no-op when re-run on its own output.
- Pure function — no I/O, no globals.

### 2. Render-time wiring

- `_render_architecture_html` calls helpers in this order: `strip_trailing_arch_diagram_section` (from I-00055) → `_preprocess_mermaid` → `render_markdown` → `wrap_h2_sections_collapsible`.
- Empty/None content still returns `None` (no NPE on the new step).

### 3. Chips endpoint

- Route is `GET /modules/chips` under the existing `/api/projects/{project_id}/code` prefix.
- Reuses `parse_modules_from_level1` — no duplicated parser.
- Returns the new `fragments/code_module_chips.html` template (template itself created in S03; the import path string is fine to set up in advance).
- 404 path falls through to `code_empty_state.html` like the cards endpoint does.
- No new DB connection; uses `Depends(get_db)`.

### 4. Mapgen prompt edit

- Exactly one line changed in `_GROUNDING_TEMPLATE`: `2–5 concise sentences` → `1–3 concise sentences`.
- The Unicode en-dash (`–`) is preserved (not replaced with `-`); other rules in the template are untouched.

### 5. CLAUDE.md conformance

- No new direct DB queries from utils/markdown.py (it's a pure renderer).
- Routers stay thin; helper is in utils/.
- No fallbacks or backwards-compatibility shims that aren't required.

## Test Verification (NON-NEGOTIABLE)

```bash
make test-unit
```

## Severity Levels

| Severity | Meaning | Action |
|----------|---------|--------|
| CRITICAL | Helper drops content / corrupts HTML; prompt edit broken | Must fix |
| HIGH | Wrong open-state on first H2; endpoint route mismatch | Must fix |
| MEDIUM (fixable) | Convention drift, missing typing | Should fix |
| MEDIUM (suggestion) | Optional improvement | Author decides |
| LOW | Nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "I-00056",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
