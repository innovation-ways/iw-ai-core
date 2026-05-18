# I-00091 S04 Code Review — Step Report

**Work Item**: I-00091 — Auto-merge settings form stays "Use global default" after partial-axis override
**Step Reviewed**: S03 (frontend-impl)
**Review Step**: S04 (code-review-impl)
**Verdict**: PASS

---

## What Was Reviewed

S03 updated four files to fix the per-axis override rendering bug and wire up the post-save in-place form refresh via htmx.

## Files Changed (by S03)

| File | Change Summary |
|------|----------------|
| `dashboard/templates/fragments/auto_merge_settings.html` | Per-axis `_phase_override` / `_runtime_override` booleans; `id="auto-merge-settings"` on `<section>`; form `hx-target` changed to `#auto-merge-settings`; `hx-indicator` + saving/saved indicator; footer uses `OR` of both overrides |
| `dashboard/templates/fragments/auto_merge_status_chip.html` | `hx-swap-oob` conditional on `oob` param; per-axis source lines (`phase_source` + `runtime_source`) |
| `dashboard/routers/auto_merge_ui.py` | `auto_merge_set_config` non-JSON branch returns concatenated `settings_html + chip_html`; chip rendered with `oob=True` |
| `dashboard/static/styles.css` | Plain CSS rules for `.auto-merge-save-indicator` and keyframe animation appended at EOF |

## Pre-Flight Checks

| Check | Result |
|-------|--------|
| `make lint` (ruff + node --check + `scripts/check_templates.py`) | PASS — all checks passed, no Jinja2 `format`-filter regressions |
| `make format` | PASS — 750 files already formatted |
| `make typecheck` | PASS (reported by S03) |

## Test Results

```
tests/dashboard/test_auto_merge_routes.py: 25 passed, 0 failed
```

Coverage failure (19.89% vs 50% required) is pre-existing — not caused by S03.

**Unit tests** (`tests/unit/test_auto_merge_config_resolution.py`): 3 failures are **expected** — they are the existing tests that assert old `.source` property semantics that are superseded by S01's new per-axis design. These are explicitly owned by S05 (tests-impl) per S01's report.

## Review Checklist — All Items PASS

### 1. Per-axis selected logic ✅
- Phase dropdown: `selected` on `Use global default` iff `not _phase_override`; on `0`/`1` options iff `_phase_override AND status.config.phase == option_value` — correct.
- Runtime dropdown: `selected` on `Use global default` iff `not _runtime_override OR status.config.runtime_option_id is none` — correct.
- Footer: `Last changed: …` renders iff `_phase_override OR _runtime_override`; `Using global default` otherwise — correct.

### 2. htmx wiring ✅
- Form `hx-target` is `#auto-merge-settings` — targets the `<section>`, not the chip.
- Outer `<section>` has `id="auto-merge-settings"`.
- Response from `auto_merge_set_config` non-JSON branch is a single `HTMLResponse` whose body concatenates both fragments.
- Chip element carries `hx-swap-oob="outerHTML:#auto-merge-status-chip"` via `{% if oob %}` conditional.
- `hx-indicator="#auto-merge-saving"` points to an element within the same settings fragment.

### 3. CSS ✅
- Rules appended to `dashboard/static/styles.css` (plain CSS), not as `<style>` block.
- No `!important` usage.
- Class names use `auto-merge-save-indicator` prefix (BEM-ish, matches existing `auto-merge-*` pattern).

### 4. Router response ✅
- Non-JSON branch uses existing helpers (`_get_project_or_404`, `_load_status`, `_render_fragment`) — no duplicated logic.
- JSON branch unchanged: `{"ok": True, "project_id": ..., "phase": ..., "runtime_option_id": ...}`.
- `DaemonEvent` emission (`EVENT_AUTO_MERGE_CONFIG_UPDATED`) preserved in `db.commit()` path.

### 5. Status chip template ✅
- Per-axis source line uses both `phase_source` and `runtime_source`.
- Health colour classes (`auto-merge-health--healthy`, etc.) preserved.

### 6. JavaScript hygiene ✅
- No new `<script>` blocks in templates.
- No `navigator.clipboard.writeText(...)` calls.
- No new files under `dashboard/static/scripts/`.

### 7. TDD RED evidence ✅
- Value is `"n/a — frontend/template + route response shape; behavioural tests written in S05"` — matches expected.

### 8. Security ✅
- No `| safe` filter added — Jinja2 auto-escapes all `request.path_params.project_id` and similar.
- No untrusted JSON inlined unescaped.

## Notes

- The `localdt` filter is registered globally in `dashboard/app.py:352` and is available in all fragment templates — no new dependency introduced.
- The S03 report states no existing dashboard tests needed updating; spot-check confirms the `id="auto-merge-settings"` change does not affect any existing test assertion.
- The 3 failing unit tests in `test_auto_merge_config_resolution.py` are documented in S01's report and correctly failing due to the new `source` property semantics — S05 owns these.

## Mandatory Fix Count

**0**

---

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "I-00091",
  "step_reviewed": "S03",
  "verdict": "pass",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "25 passed, 0 failed (dashboard routes); 3 pre-existing expected failures in unit tests (owned by S05)",
  "notes": "S03 implementation is correct and complete. Per-axis override logic, htmx wiring (hx-target=settings + OOB chip swap), CSS appended as plain CSS, JSON contract preserved, no security issues. Pre-existing 3 unit test failures are expected and documented in S01 report — S05 owns updating them to match new source property semantics."
}
```