# I-00091_S04_CodeReview_prompt

**Work Item**: I-00091 — Auto-merge settings form stays "Use global default" after partial-axis override
**Step Being Reviewed**: S03 (frontend-impl)
**Review Step**: S04

---

## ⛔ Docker is off-limits

Standard policy — see `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

N/A — S03 does not touch migrations.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00091 --json`.
- `ai-dev/active/I-00091/I-00091_Issue_Design.md`
- `ai-dev/active/I-00091/reports/I-00091_S01_Backend_report.md` (for the
  ResolvedConfig contract)
- `ai-dev/active/I-00091/reports/I-00091_S03_Frontend_report.md`
- All files listed in S03's `files_changed`

## Output Files

- `ai-dev/active/I-00091/reports/I-00091_S04_CodeReview_report.md`

## Context

You are reviewing the template + router half of the I-00091 fix. S03
updated `auto_merge_settings.html`, `auto_merge_status_chip.html`,
`auto_merge_ui.py:auto_merge_set_config`, and `styles.css` to:

1. Use per-axis `_phase_override` / `_runtime_override` booleans in the
   settings dropdowns.
2. Wrap the section in `id="auto-merge-settings"` and target it from the
   form's `hx-target`.
3. Return a combined fragment (settings + hx-swap-oob chip) from
   `auto_merge_set_config`.
4. Render the chip's source line per-axis.
5. Append plain CSS for a "Saving…"/"Saved" indicator.

## Read the Design Document FIRST

- Read **Acceptance Criteria** AC1..AC4 — each is a directly-verifiable
  claim against the new HTML.
- Read **Affected Components** for the exact file scope.
- Read **TDD Approach** — note that the dashboard/integration tests in
  S05 will assert specific substrings (`id="auto-merge-settings"`,
  `hx-swap-oob`, `value="1" selected`). The S03 implementation MUST emit
  those exact tokens.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint   # runs ruff + node --check + scripts/check_templates.py
make format
```

`scripts/check_templates.py` is part of `make lint` (CLAUDE.md). Any
violation it flags in the touched Jinja2 templates → CRITICAL finding.

In particular:

- Verify no `format`-filter call regressed to `{}`-style — must remain
  `%`-style (I-00075). Example bad: `"{}m{}s"|format(m, s)`.

## Review Checklist

### 1. Per-axis selected logic

- Phase dropdown: `selected` ONLY when `_phase_override` AND
  `status.config.phase == option_value`.
- Runtime dropdown: same shape using `_runtime_override` and matching
  ids.
- "Use global default" is `selected` exactly when its axis is NOT
  overridden.
- Footer line: renders `Last changed:` when EITHER axis is overridden;
  `Using global default` only when NEITHER is.

### 2. htmx wiring

- The form's `hx-target` is `#auto-merge-settings` (NOT
  `#auto-merge-status-chip`).
- The outer `<section>` carries `id="auto-merge-settings"`.
- The response from `auto_merge_set_config` for non-JSON requests
  contains BOTH the settings fragment AND a chip element marked with
  `hx-swap-oob`.
- The OOB chip element still has `id="auto-merge-status-chip"` so htmx
  can locate it.
- `hx-indicator="#auto-merge-saving"` points to an element that exists
  in the same fragment.

### 3. CSS

- New rules are appended to `dashboard/static/styles.css` (plain CSS),
  NOT injected as a `<style>` block in a template or routed through
  `make css`.
- New class names follow the existing `auto-merge-*` BEM-ish prefix.
- No accidental `!important` use.

### 4. Router response

- The non-JSON branch returns an `HTMLResponse` whose body contains both
  fragments. Helpers `_get_project_or_404`, `_load_status`,
  `_render_fragment` are reused — no duplicated logic.
- The JSON branch (`_accepts_json(request)`) is unchanged in payload
  shape: `{"ok": True, "project_id": ..., "phase": ..., "runtime_option_id": ...}`.
- `DaemonEvent` emission for `auto_merge_config_updated` is preserved.

### 5. Status chip template

- The new per-axis source line uses **both** `phase_source` and
  `runtime_source` from `ResolvedConfig`.
- No regression on the chip's existing layout / health colour classes.

### 6. JavaScript hygiene

- No new `<script>` blocks added to templates.
- No new `navigator.clipboard.writeText(...)` calls.
- No new files under `dashboard/static/scripts/`.

### 7. Existing dashboard tests

- If S03 had to update existing test assertions (e.g., a test that
  asserted on the old chip text), each edit must be justified in the
  S03 report's `notes`. Spot-check 2–3 of those edits and confirm they
  are narrow (asserting the new correct text), not blanket deletions.

### 5a. TDD RED Evidence

S03 is a Frontend step — not behaviour-implementing in the Backend
sense. The expected `tdd_red_evidence` value is `"n/a — frontend/template
+ route response shape; behavioural tests written in S05"`. Anything
else is suspect.

### 8. Security

- No HTML injection: `request.path_params.project_id` and similar are
  auto-escaped by Jinja2; verify no new `| safe` filter was added.
- No new server-rendered untrusted JSON inlined unescaped.

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/dashboard/test_auto_merge_routes.py -v
```

## Severity Levels

Standard.

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "I-00091",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
