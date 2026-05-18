# I-00091_S06_CodeReview_prompt

**Work Item**: I-00091 — Auto-merge settings form stays "Use global default" after partial-axis override
**Step Being Reviewed**: S05 (tests-impl)
**Review Step**: S06

---

## ⛔ Docker is off-limits

Standard policy.

## ⛔ Migrations: agents generate, daemon applies

N/A.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00091 --json`.
- `ai-dev/active/I-00091/I-00091_Issue_Design.md`
- `ai-dev/active/I-00091/reports/I-00091_S05_Tests_report.md`
- All files listed in S05's `files_changed`
- `tests/CLAUDE.md`, `skills/iw-ai-core-testing/SKILL.md`

## Output Files

- `ai-dev/active/I-00091/reports/I-00091_S06_CodeReview_report.md`

## Context

You are reviewing the regression test suite added in S05. The design
specifies four matrix tests at the dashboard layer and at the unit
layer, plus one integration test asserting the combined-fragment
response.

## Read the Design Document FIRST

- **TDD Approach** section names each test file and test function by
  path — every named test must appear in S05's `files_changed`. Missing
  ones are CRITICAL.
- **Acceptance Criteria** AC5 directly says "the reproducing test
  passes" — verify the test name in AC5 is one of the four added.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

## Review Checklist

### 1. Test placement (I-00067 lesson)

- Tests using the `client` fixture MUST live under `tests/dashboard/`.
  A test that uses `client` and is placed under `tests/unit/` or
  `tests/integration/` is a CRITICAL finding (it fails with
  `fixture 'client' not found`).
- Pure-Python aggregator tests under `tests/unit/`.
- Tests needing testcontainer DB under `tests/integration/`.

### 2. Semantic correctness over shape (I003 lesson) — CRITICAL CLASS

Open every new test and look for these red flags:

| Smell | Severity | Why |
|-------|----------|-----|
| `assert "selected" in html` | HIGH | Passes against the bug (the substring exists, on the wrong option) |
| `assert "<option" in html` | HIGH | Pure shape check |
| `assert "phase" in html` | HIGH | Doesn't verify the value |
| `assert response.status_code == 200` as the only assertion | CRITICAL | Doesn't verify any behaviour |
| `assert len(...) > 0` as the only assertion | HIGH | Shape-only |

What you WANT to see:

- `assert 'value="1" selected' in phase_block` (specific value)
- `assert 'value="global" selected' not in phase_block` (specific value
  absent)
- Use of a helper that scopes to a single `<select>` (e.g.
  `_extract_select_block`) so a `selected` in another select can't
  accidentally satisfy a Phase assertion.

### 3. Coverage matrix

The four-cell matrix MUST be covered at the dashboard layer:

- phase-only override
- runtime-only override
- both axes overridden
- neither overridden (clear-back-to-global)

Plus the unit-level matrix at `resolve_project_config`.

Plus the integration-level test for the combined-fragment response
(asserting `id="auto-merge-settings"` AND `hx-swap-oob` are both
present).

Missing matrix cells → HIGH finding per missing cell.

### 4. Test naming

The design references these exact names — they MUST exist verbatim:

- `test_settings_form_reflects_phase_only_override`
- `test_settings_form_reflects_runtime_only_override`
- `test_settings_form_reflects_both_axes_override`
- `test_settings_form_clears_back_to_global`
- `test_resolve_project_config_records_per_axis_source_phase_only_override`
- `test_resolve_project_config_records_per_axis_source_runtime_only_override`
- `test_resolve_project_config_records_per_axis_source_both_axes_override`
- `test_resolve_project_config_records_per_axis_source_no_override`
- `test_save_config_returns_combined_fragment`

A rename → HIGH finding (the design ACs reference these names).

### 5. Isolation & determinism (IW AI Core testing standards)

- No hardcoded project IDs that could collide across test runs — use
  factory-generated ids.
- No `importlib.reload(orch.config)` — use `monkeypatch.delenv`.
- No connection to live DB (port 5433).
- No use of `agent-browser`.
- No mocking the DB in integration tests (FOR UPDATE locking can't be
  tested otherwise — see CLAUDE.md).

### 6. CSS class assertions (I-00067)

If any test asserts on a CSS class, it MUST use the attribute-scoped
form, not the bare-substring form. See `tests/CLAUDE.md`.

### 7. Targeted-run discipline

S05's report `tests_passed` must reflect ONLY the targeted run, not
`make test-unit` / `make test-integration` (which are S12 / S13 QV
gates). If S05 ran the full suite inside the step, that's a MEDIUM
(fixable) finding — it routinely blows the step's timeout budget (see
I-00073/S03 post-mortem).

### 5a. TDD RED Evidence

Tests-impl is a coverage step (dedicated coverage step). Per the design
template's standard, `tdd_red_evidence` should read `n/a — coverage
step` with a reason. Verify.

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/unit/test_auto_merge_config_resolution.py tests/dashboard/test_auto_merge_routes.py tests/integration/test_auto_merge_control_surface.py -v
```

If any of the named matrix tests are missing from the collection list,
that is a CRITICAL finding (regardless of pass/fail of the rest).

## Severity Levels

Standard.

## Review Result Contract

```json
{
  "step": "S06",
  "agent": "code-review-impl",
  "work_item": "I-00091",
  "step_reviewed": "S05",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
