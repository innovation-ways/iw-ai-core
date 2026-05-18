# I-00091_S07_CodeReview_Final_prompt

**Work Item**: I-00091 — Auto-merge settings form stays "Use global default" after partial-axis override
**Review Step**: S07 (Final Review)
**Implementation Steps Reviewed**: S01..S06

---

## ⛔ Docker is off-limits

Standard policy.

## ⛔ Migrations: agents generate, daemon applies

This item adds no migrations. If any new file appeared under
`orch/db/migrations/versions/**`, raise a CRITICAL finding.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00091 --json`.
- `ai-dev/active/I-00091/I-00091_Issue_Design.md`
- `ai-dev/active/I-00091/I-00091_Functional.md`
- All step reports under `ai-dev/active/I-00091/reports/`
- All files listed in any S01 / S03 / S05 `files_changed`

## Output Files

- `ai-dev/active/I-00091/reports/I-00091_S07_CodeReview_Final_report.md`

## Context

You are performing the final cross-agent review of I-00091. Per-step
reviews (S02, S04, S06) have already happened. Your job is to catch
issues that ONLY appear at the seam between the steps:

- Does `ResolvedConfig.phase_source` / `runtime_source` as emitted by
  S01 line up exactly with what S03's templates consume? (Field names,
  literal values "per_project_db"/"toml"/"hardcoded".)
- Do S05's tests assert on the actual DOM tokens S03 emits? (Token
  drift between implementation and tests is the classic seam defect.)
- Does the combined-fragment response from `auto_merge_set_config`
  contain the literal `id="auto-merge-status-chip"` AND
  `hx-swap-oob="outerHTML"` (or similar) that S05's integration test
  searches for?

## Read the Design Document FIRST

- Every Acceptance Criterion (AC1..AC5) must map to at least one
  test in S05's `files_changed`. AC5 is "regression test exists" — that
  is the four-cell dashboard matrix.
- The TDD Approach section's named tests must all exist verbatim.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

Any NEW violation in any S01/S03/S05 changed file → CRITICAL.

## Review Checklist

### 1. Completeness vs Design

- AC1..AC5 are each satisfied by code + tests.
- The four-cell matrix is fully covered (phase-only / runtime-only /
  both / neither) at the dashboard layer AND at the unit layer.
- The combined-fragment integration test exists.
- The Functional Design Document (`I-00091_Functional.md`) accurately
  describes the user-facing behaviour delivered.

### 2. Cross-Agent Consistency

- S01's `ResolvedConfig.phase_source` field name matches the template
  expression in S03's settings + chip files (exact case + spelling).
- The `Literal["per_project_db", "toml", "hardcoded"]` literal values
  match the template's string comparisons. A mismatch like
  `"per-project-db"` vs `"per_project_db"` is a CRITICAL finding.
- The id `auto-merge-settings` is the same token in the template,
  the form's `hx-target`, the router response (no leaked
  `#auto_merge_settings` typo), and S05's test assertions.

### 3. Integration Points

- The router `auto_merge_set_config`:
  - Non-JSON request → HTMLResponse containing settings fragment AND
    OOB chip.
  - JSON request → unchanged JSON payload.
  - `DaemonEvent` for `auto_merge_config_updated` still emitted.
- The settings template's `hx-target` matches the section's `id`.
- The OOB chip element retains its `id="auto-merge-status-chip"`.

### 4. Test Coverage (Holistic)

- Every assertion targets a specific value, not just shape (I003).
- CSS class assertions are attribute-scoped (I-00067).
- Test placement is correct: `client` fixture → `tests/dashboard/`.

### 5. Architecture / Conventions

- No new docker invocations.
- No new alembic command.
- No new `<script>` blocks in templates.
- Plain CSS rules appended to `styles.css` (not Tailwind-recompile-only
  classes) — per CLAUDE.md `make css` mitigation.
- Jinja2 `format` filter calls remain `%`-style (I-00075).

### 6. Security

- No `| safe` filter added to user-controlled data.
- No new hardcoded credentials.
- No new endpoints; the existing `/auto-merge/config` retains its
  validation (phase ∈ {None,0,1}; runtime_option_id must be enabled).

### 7. Backwards compatibility

- If S01 kept `.source` as a property, the chip's old "Source: …" line
  in any callers we didn't migrate still works.
- If S01 removed `.source`, the grep for old call sites is exhaustive.

## Test Verification (NON-NEGOTIABLE)

Targeted only — re-run the three files this item touches, no more:

```bash
uv run pytest \
  tests/unit/test_auto_merge_config_resolution.py \
  tests/dashboard/test_auto_merge_routes.py \
  tests/integration/test_auto_merge_control_surface.py -v
```

Full-suite execution (`make test-unit`, `make allure-integration`) is
owned by QV gates S12 / S13 — do NOT duplicate them here. Duplicating
the full suite inside an `*-impl` step is a routine cause of step
timeout (I-00073/S03, 2026-05-08).

Any failure in the targeted run → CRITICAL.

## Severity Levels

Standard.

## Review Result Contract

```json
{
  "step": "S07",
  "agent": "code-review-final-impl",
  "work_item": "I-00091",
  "steps_reviewed": ["S01", "S03", "S05"],
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "completeness|consistency|integration|testing|architecture|security",
      "file": "",
      "line": 0,
      "description": "",
      "suggestion": "",
      "cross_cutting": true
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```
