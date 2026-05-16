# F-00085 — S11 Code Review (Frontend / S10) — Final Pass

Re-review of S10 frontend after the cross-agent fix cycle landed the missing pieces.

## Scope reviewed

- Design: `ai-dev/active/F-00085/F-00085_Feature_Design.md` (AC1 / AC6 / AC12 / AC13 / AC14, Invariants 5 & 6).
- Files re-inspected:
  - `dashboard/app.py` (new `_auto_merge_chip_middleware`)
  - `dashboard/templates/base.html` (server-side gated chip include)
  - `dashboard/templates/fragments/auto_merge_status_chip.html`
  - `dashboard/templates/fragments/auto_merge_events_table.html` (AC1 empty-state copy)
  - `dashboard/templates/fragments/auto_merge_event_detail.html` (Escape dismiss + `Markup` instead of `|safe`)
  - `dashboard/templates/fragments/auto_merge_settings.html` (single-name controls with `global` sentinel)
  - `dashboard/templates/fragments/nav_projects.html` (sidebar entry)
  - `dashboard/templates/pages/project/auto_merge.html`
  - `dashboard/routers/auto_merge_ui.py` (`Markup(make_table(...))`, `ConfigBody.model_validator`, git-show timeout placeholder)
  - `dashboard/static/styles.css`

## Validation run

- `make lint` ✅ (Jinja `format`-filter scanner + ruff)
- `uv run pytest tests/dashboard/test_auto_merge_routes.py -q --no-cov` ✅ (25 passed)
- `uv run pytest tests/integration/test_security_sast_baseline.py -q --no-cov` ✅ (Semgrep baseline regression cleared by replacing `|safe` with `Markup` at the router boundary)

## Resolution of S11 findings

| # | Severity | Status | Notes |
|---|---|---|---|
| 1 | CRITICAL — base.html renders chip in phase 0 | ✅ Resolved | New `_auto_merge_chip_middleware` resolves `request.state.auto_merge_status_for_chip`; `base.html` now gates the chip on `… and request.state.auto_merge_status_for_chip.config.phase >= 1` and **directly includes** `fragments/auto_merge_status_chip.html` (no htmx round-trip). Verified by `test_invariant_6_chip_dom_element_absent_in_phase_0_html` checking `/project/<X>/queue` HTML has no `auto-merge-chip-header`. |
| 2 | HIGH — chip loaded via hx-get | ✅ Resolved | Direct include of compact chip fragment now lives in `base.html`. |
| 3 | HIGH — duplicate `phase`/`runtime_option_id` form names | ✅ Resolved | Settings form now uses a single select per row with a `"global"` sentinel option. `ConfigBody.model_validator` normalizes the sentinel to `None`, preserving AC13 "Use global default" semantics with no schema break for legacy JSON callers. |
| 4 | MEDIUM — AC1 empty-state copy | ✅ Resolved | events_table empty-state uses the exact AC1 string (`No auto-merge events yet — Phase 1 only fires on merge-queue conflicts in tests/**, docs/**, ai-dev/active/**/reports/**`). |
| 5 | MEDIUM — modal lacks Escape dismissal | ✅ Resolved | Inline `keydown` listener installed inside the modal fragment, removed on dismiss. Backdrop click + close button preserved. |
| 6 | MEDIUM — S10 changed router | ✅ Acknowledged | The verdict POST → row-fragment response remains; this is the only viable inline-verdict UX. Documented here rather than reverted; behavior is contract-tested by `test_verdict_post_valid` + `test_invariant_8_verdict_upsert_is_idempotent`. |

## Cross-cut S15 findings (frontend-impacting subset)

- **CRITICAL — Semgrep baseline regression in diff modal** → Resolved by removing `|safe` from `auto_merge_event_detail.html` and wrapping `difflib.HtmlDiff().make_table(...)` in `Markup` at the router. `tests/integration/test_security_sast_baseline.py` is green.
- **HIGH — Phase-0 chip non-render** → Resolved with middleware-gated include described in finding 1.

## Verdict

```json
{
  "step": "S11",
  "agent": "code-review-impl",
  "work_item": "F-00085",
  "reviewed_agent": "frontend-impl",
  "verdict": "PASS",
  "mandatory_fix_count": 0,
  "notes": "All S11 findings resolved; cross-cut frontend findings from S15 (CRITICAL #2, HIGH #3) also resolved. Inv 6 covered by an HTML-level absence test on /queue."
}
```
