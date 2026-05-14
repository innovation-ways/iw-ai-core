# CR-00051 — S03 Frontend Report

**Work item**: CR-00051 — Semgrep baseline cleanup
**Step**: S03 — Frontend annotations for `template-unescaped-with-safe`
**Agent**: `frontend-impl`
**Status**: complete

## What was done

Added rationale-bearing `{# nosemgrep: python.flask.security.xss.audit.template-unescaped-with-safe.template-unescaped-with-safe — ... #}` comments immediately preceding every `| safe` filter call site in the Class B set. Each comment carries a site-specific source description (e.g., "chat message body (server-side citation rendering)", "doc-detail rendered HTML", "ProjectDoc content").

No template logic, structure, CSS, or htmx wiring was changed. No new `| safe` filters were introduced (Invariant I2 preserved).

## Files changed (17)

The design enumerated 16 Class B sites; the actual residual after S01 was **17**. The unenumerated 17th site is `dashboard/templates/components/confirm_dialog.html:11` (`{{ form_html | safe }}`).

The design's "out of scope" list grouped `confirm_dialog.html` among "12 `write_button_attrs(request)` caller files", but a Grep confirms `confirm_dialog.html` does **not** call `write_button_attrs` — it is a macro *definition* with its own independent Class B `| safe` site. The "don't edit" rule was scoped to Class C (`unquoted-attribute-var`, Makefile-handled); this Class B edit does not interact with that concern. The same precedent is set by `docs_detail.html`, which appears in both lists and where the design instructs to add the Class B annotation at `:223` while not touching the Class C lines at `:68, :78`.

`form_html` originates from `dashboard/templates/fragments/confirm_action_form.html`, which composes the HTML server-side from router-supplied strings (`default_reason`, `reset_field_name`, `reset_field_label`).

Edited templates:

1. `dashboard/templates/chat/message.html` (chat message body)
2. `dashboard/templates/chat/parts/table.html` (chat table snippet)
3. `dashboard/templates/chat/parts/text.html` (chat text snippet)
4. `dashboard/templates/components/confirm_dialog.html` (dialog form HTML — **NOT in original enumeration**; see note above)
5. `dashboard/templates/docs_detail.html` (doc-detail rendered HTML; only `:223` Class B touched, `:68 / :78` Class C lines untouched)
6. `dashboard/templates/exports/diff_pdf.html` (diff PDF body)
7. `dashboard/templates/fragments/code_architecture_diagram.html` (server-built SVG)
8. `dashboard/templates/fragments/code_architecture_view.html` (server-built HTML)
9. `dashboard/templates/fragments/code_module_detail.html` (code module detail panel)
10. `dashboard/templates/fragments/code_symbol_panel.html` (code symbol panel)
11. `dashboard/templates/fragments/docs_global_results.html` (global docs search results — annotation placed before line `{{ snippet | replace(...) | safe }}`)
12. `dashboard/templates/fragments/item_design_doc.html` (design-doc Markdown render)
13. `dashboard/templates/fragments/item_functional_doc.html` (functional-doc Markdown render)
14. `dashboard/templates/fragments/item_reports.html` (item-report Markdown render)
15. `dashboard/templates/pages/project/batch_detail.html` (batch-plan content)
16. `dashboard/templates/pdf/doc_pdf.html` (ProjectDoc content)
17. `dashboard/templates/research_detail.html` (research-doc content)

## Pre-flight quality gates

- `make lint` — **OK** (ruff + `scripts/check_templates.py` both pass; no Jinja `format`-filter or unsafe-pattern regressions introduced).
- `make format` — N/A (Jinja templates aren't ruff-formatted; comment-only edits).
- `make typecheck` — N/A for template-only edits.

## Test verification

- `make security-sast` — **0 findings (0 blocking)**. Before this step the pipeline reported 1 blocking finding remaining after S01 (was 17 after S01, dropped to 0 here).
- Counts: pipeline went from 94 (pre-S01) → 17 residual after S01 → 0 after S03.
  - The S01 design assumed 16 Class B sites; the empirical residual after S01 was 17. The 17th was `components/confirm_dialog.html:11` (handled here).
- Jinja parse sanity-check of all 17 templates passed (custom app-registered filter `fmt_ts_time` is loaded at runtime, not at standalone parse time — not a template defect).
- Dashboard import (`from dashboard.app import app`) is blocked by the live-DB guard (`IW_CORE_AGENT_CONTEXT` is set; see `orch/db/live_db_guard.py`) — unrelated to this step's edits.

`make test-unit` / `make test-integration` not run here (downstream QV gates S12–S14).

## TDD evidence

n/a — template comment-only edits, no production logic.

## Notes & observations

1. **Design count discrepancy (16 vs 17)**. The design captured 16 Class B sites; one additional `template-unescaped-with-safe` site lives in `components/confirm_dialog.html:11`. It was not enumerated either because it was assumed to be Class-C-only (the file is in the design's "12 macro-caller files" list, but Grep shows the file does not call `write_button_attrs`), or because line-drift since the design caused it to be overlooked. Treated as a Class B fix consistent with the rest of the set. Recommend the S05 integration test enumerate the post-CR residual count, not just the design's number, to catch this kind of drift.
2. **`docs_detail.html` split** handled per design: Class B annotation added at the `content_html | safe` line; the `write_button_attrs(request)` call-sites (Class C) left untouched.
3. **`dashboard/templates/macros/db_guard.html`** — not touched (confirmed unchanged).
4. **The 12 macro-caller files for `write_button_attrs(request)`** — none of them were edited.
5. **`dashboard/static/styles.css`** — not touched. `make css` not run. No new Tailwind classes introduced.
6. No `.iw-collision` files exist in the worktree (confirmed).

## Blockers

None.
