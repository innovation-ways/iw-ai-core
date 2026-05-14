# CR-00051_S04_CodeReview_prompt

**Work Item**: CR-00051 — Semgrep baseline cleanup
**Step Being Reviewed**: S03 (Frontend)
**Review Step**: S04

---

## ⛔ Docker is off-limits

Standard policy.

## ⛔ Migrations: agents generate, daemon applies

This CR leaves migrations unchanged.

## Input Files

- **Runtime step state** (authoritative): `uv run iw item-status CR-00051 --json`.
- `ai-dev/active/CR-00051/CR-00051_CR_Design.md`
- `ai-dev/active/CR-00051/reports/CR-00051_S03_Frontend_report.md`
- All files listed in S03's `files_changed`.

## Output Files

- `ai-dev/active/CR-00051/reports/CR-00051_S04_CodeReview_report.md`

## Context

S03 added Jinja `{# nosemgrep #}` comments to 16 template lines across 16 files, one per file, silencing the `template-unescaped-with-safe` rule on the existing `| safe` filter call sites. **No production template logic should have changed. No edit should have leaked to `db_guard.html` or to any `write_button_attrs(request)` caller file.**

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

Both must report zero NEW violations on S03's `files_changed`. `make lint` also runs `scripts/check_templates.py` — that gate enforces Jinja `format`-filter conventions (see I-00075) and must still pass.

## Review Checklist

### 1. Scope

S03's `files_changed` must be exactly these 16 files (in any order):

- `dashboard/templates/chat/message.html`
- `dashboard/templates/chat/parts/table.html`
- `dashboard/templates/chat/parts/text.html`
- `dashboard/templates/docs_detail.html`
- `dashboard/templates/exports/diff_pdf.html`
- `dashboard/templates/fragments/code_architecture_diagram.html`
- `dashboard/templates/fragments/code_architecture_view.html`
- `dashboard/templates/fragments/code_module_detail.html`
- `dashboard/templates/fragments/code_symbol_panel.html`
- `dashboard/templates/fragments/docs_global_results.html`
- `dashboard/templates/fragments/item_design_doc.html`
- `dashboard/templates/fragments/item_functional_doc.html`
- `dashboard/templates/fragments/item_reports.html`
- `dashboard/templates/pages/project/batch_detail.html`
- `dashboard/templates/pdf/doc_pdf.html`
- `dashboard/templates/research_detail.html`

Any other file in `files_changed` is **CRITICAL** (scope violation). In particular:
- Any edit to `dashboard/templates/macros/db_guard.html` is **CRITICAL** (S03 must NOT modify the macro — Class C is handled in S01 via Makefile `--exclude-rule`).
- Any edit to the 12 macro-caller files outside the 16 above is **CRITICAL** (those are out of scope; the Makefile-exclude approach makes per-call-site annotation unnecessary).
- Any edit to `dashboard/static/styles.css` or any `.iw-collision` file is **CRITICAL**.

Special case: `docs_detail.html` appears legitimately in the 16-file list AND in the 12 macro-caller list (it has `template-unescaped-with-safe` at `:223` AND `unquoted-attribute-var` at `:68, :78`). Verify S03's edit to `docs_detail.html` touched only `:223` (the `template-unescaped-with-safe` site), not `:68` or `:78`. Any edit at `:68`/`:78` is **CRITICAL** (Class C is out of scope for S03).

### 2. Suppression correctness

For every `{# nosemgrep #}` added, confirm:
- It immediately precedes the line it intends to silence (no blank line between).
- The rule ID is exactly `python.flask.security.xss.audit.template-unescaped-with-safe.template-unescaped-with-safe`.
- The comment carries a site-specific rationale after the `—` (e.g., "batch-plan content", "ProjectDoc content", "code architecture diagram (server-built SVG)", etc.) — generic placeholders like "trusted content" or "safe" are **MEDIUM_FIXABLE**.
- The comment is well-formed Jinja (`{# ... #}`, not `{## ... ##}` or `{%- comment -%}`).

### 3. No new `| safe` introduced (Invariant I2)

Grep S03's `files_changed` for `| safe`. The only `| safe` filters present must be the **16 pre-existing ones**. Any NEW `| safe` is **CRITICAL**.

### 4. Dashboard imports cleanly

Run a quick smoke check:
```bash
uv run python -c "from dashboard.app import app; print('import OK')"
```
Any ImportError or template-parse error in S03's edits is **CRITICAL**.

### 5. Code Quality / Conventions / Security / Testing

Standard checklist. Most items N/A for a comments-only template change. Confirm `tdd_red_evidence` in S03's report uses the `"n/a — …"` form.

## Test Verification (NON-NEGOTIABLE)

Run `make security-sast` and confirm the count of blocking findings is **exactly 0**.

If non-zero, identify which class still fires:
- Class A/C/D/E/F/G/H still firing → flag as **HIGH** with reference to S01 (this means S02 missed it).
- Class B still firing → **HIGH** on S03.

## Severity Levels

Standard table.

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "CR-00051",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "make security-sast: 0 blocking findings",
  "notes": ""
}
```
