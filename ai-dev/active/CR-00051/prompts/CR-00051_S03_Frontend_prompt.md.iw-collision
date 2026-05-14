# CR-00051_S03_Frontend_prompt

**Work Item**: CR-00051 — Semgrep baseline cleanup
**Step**: S03
**Agent**: Frontend (`frontend-impl`)

---

## ⛔ Docker is off-limits

Standard policy.

## ⛔ Migrations: agents generate, daemon applies

This step adds no migrations.

## Input Files

- **Runtime step state** (authoritative): `uv run iw item-status CR-00051 --json`.
- `ai-dev/active/CR-00051/CR-00051_CR_Design.md` — design doc (read in full; especially Class B under "Current Behavior" and Invariants I1, I2).
- `ai-dev/active/CR-00051/reports/CR-00051_S01_Backend_report.md` — what S01 changed (you should NOT re-touch any of those files; S01 added per-line annotations to 15 Python lines and added four `--exclude-rule` flags + a rationale block to the `Makefile` `security-sast` target).
- `dashboard/CLAUDE.md` — Jinja patterns, the htmx convention, Tailwind CSS rules.
- The 16 Class B template files (see §1 below).

## Output Files

- `ai-dev/active/CR-00051/reports/CR-00051_S03_Frontend_report.md`

## Context

You are adding rationale-bearing `{# nosemgrep #}` comments to **16 template files**, one per file, silencing the `template-unescaped-with-safe` rule on the existing `| safe` filter call sites. Every value passed through `| safe` is server-side Markdown→HTML or pre-built HTML/SVG from trusted in-DB content (design docs, research notes, doc-system output, RAG citations, code-understanding panels).

**Class C is NOT in your scope.** S01 already added a Makefile `--exclude-rule` flag for `unquoted-attribute-var` covering all 26 `write_button_attrs(request)` call sites at the project level. The `db_guard.html` macro and the 12 macro-caller files are NOT modified by this step (or by this CR at all). An empirical test before this CR was written confirmed that in-macro `{# nosemgrep #}` does NOT propagate to call-site analyses, which is why the Makefile-exclude approach is used instead.

Read `dashboard/CLAUDE.md` first — particularly the rules about fragment templates, htmx, and the prebuilt Tailwind CSS. None of this changes the dashboard's CSS or htmx wiring, but the convention reading is required.

## Requirements

### 1. Class B — `template-unescaped-with-safe` (16 sites, 16 files)

For each line listed below, **prepend** a Jinja comment carrying the rationale on its own line immediately before the line (no blank line between). The comment must be well-formed Jinja (`{# ... #}`, not `{## ... ##}` or `{%- comment -%}`).

The canonical comment pattern is:
```
{# nosemgrep: python.flask.security.xss.audit.template-unescaped-with-safe.template-unescaped-with-safe — server-rendered Markdown→HTML from trusted <SOURCE> #}
```

Replace `<SOURCE>` with the site-specific description from the table below.

| File | Line | `<SOURCE>` to substitute |
|---|---|---|
| `dashboard/templates/chat/message.html` | 3 | chat message body (server-side citation rendering) |
| `dashboard/templates/chat/parts/table.html` | 13 | chat table snippet (server-side citation rendering) |
| `dashboard/templates/chat/parts/text.html` | 2 | chat text snippet (server-side citation rendering) |
| `dashboard/templates/docs_detail.html` | 223 | doc-detail rendered HTML |
| `dashboard/templates/exports/diff_pdf.html` | 450 | diff PDF body |
| `dashboard/templates/fragments/code_architecture_diagram.html` | 10 | code architecture diagram (server-built SVG) |
| `dashboard/templates/fragments/code_architecture_view.html` | 30 | code architecture view (server-built HTML) |
| `dashboard/templates/fragments/code_module_detail.html` | 80 | code module detail panel |
| `dashboard/templates/fragments/code_symbol_panel.html` | 13 | code symbol panel |
| `dashboard/templates/fragments/docs_global_results.html` | 63 | global docs search results |
| `dashboard/templates/fragments/item_design_doc.html` | 61 | design-doc Markdown render |
| `dashboard/templates/fragments/item_functional_doc.html` | 60 | functional-doc Markdown render |
| `dashboard/templates/fragments/item_reports.html` | 37 | item-report Markdown render |
| `dashboard/templates/pages/project/batch_detail.html` | 113 | batch-plan content |
| `dashboard/templates/pdf/doc_pdf.html` | 172 | ProjectDoc content |
| `dashboard/templates/research_detail.html` | 131 | research-doc content |

(Line numbers may have drifted by ±2 since the design was captured; anchor on the `| safe` filter expression in each file to confirm placement.)

If a file uses `{%- -%}` whitespace-trim variants on the surrounding markup, mirror that style for the comment line so the rendered output stays byte-equivalent.

### 2. Verify with Semgrep

Run `make security-sast` and confirm zero blocking findings. Class B (16) is the entire residual from S01. Combined with S01's work, the count goes from 16 → 0.

If the count is non-zero, identify which rule still fires and adjust the marker placement. Do NOT modify any template logic to silence a finding — annotations only.

### 3. Don't touch anything else

- Do **not** edit `dashboard/templates/macros/db_guard.html`. It is out of scope (Class C is handled in S01 via Makefile `--exclude-rule`).
- Do **not** edit any of the 12 `write_button_attrs(request)` caller files (action_button.html, confirm_dialog.html, containers_table.html, daemon_panel.html, docs_detail.html [the call-site lines — `:68`, `:78` — but DO add the `template-unescaped-with-safe` annotation at `:223`], quality_launch.html, tests_launch.html, worktree_table.html, queue.html, running.html, worktrees.html, project_code.html). They are out of scope.
- Do **not** edit `dashboard/static/styles.css`. No CSS changes are needed.
- Do **not** run `make css`. No new Tailwind classes are introduced.
- Do **not** introduce a new `| safe` filter anywhere (Invariant I2).
- Do **not** touch any `.iw-collision` files.

Note on `docs_detail.html`: this file appears in BOTH lists (Class B `:223` and Class C `:68, :78`). You add the Class B annotation at `:223` only; the `:68` and `:78` lines are not edited (Class C is Makefile-handled).

## Project Conventions

`dashboard/CLAUDE.md` — read it. Key rules that apply here:
- Fragment templates under `templates/fragments/` MUST NOT extend `base.html`. (You're editing fragments here for Class B — confirm you're only adding `{# nosemgrep #}` comments and not changing the file's extends/include structure.)
- htmx POSTs return HTML fragments — irrelevant for this CR, but don't accidentally break a partial.
- Tailwind CSS is prebuilt; do not change class names.

## TDD Requirement

This step adds no behavioural template logic. Use `tdd_red_evidence: "n/a — template comment-only edits, no production logic"` in your result contract. The unit test that locks the `write_button_attrs` macro's constant-output invariant is S05's responsibility, not yours.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

1. `make format` — Jinja templates aren't ruff-formatted; this gate is mostly a no-op here.
2. `make typecheck` — irrelevant for template edits but run it anyway.
3. `make lint` — must pass. `make lint` also invokes `scripts/check_templates.py` — ensure your Jinja edits do not violate template lint rules (e.g., the `%`-style `format` filter rule from I-00075).

## Test Verification (NON-NEGOTIABLE)

Run `make security-sast` and confirm zero blocking findings. The CR's S05 step adds an integration test for this; you are establishing the precondition.

Also do a quick dashboard-import sanity check to confirm no Jinja syntax error:
```bash
uv run python -c "from dashboard.app import app; print('import OK')"
```

Do NOT run `make test-unit` or `make test-integration` here — those are downstream QV gate steps (S12, S13, S14).

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "Frontend",
  "work_item": "CR-00051",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/templates/chat/message.html",
    "dashboard/templates/chat/parts/table.html",
    "dashboard/templates/chat/parts/text.html",
    "dashboard/templates/docs_detail.html",
    "dashboard/templates/exports/diff_pdf.html",
    "dashboard/templates/fragments/code_architecture_diagram.html",
    "dashboard/templates/fragments/code_architecture_view.html",
    "dashboard/templates/fragments/code_module_detail.html",
    "dashboard/templates/fragments/code_symbol_panel.html",
    "dashboard/templates/fragments/docs_global_results.html",
    "dashboard/templates/fragments/item_design_doc.html",
    "dashboard/templates/fragments/item_functional_doc.html",
    "dashboard/templates/fragments/item_reports.html",
    "dashboard/templates/pages/project/batch_detail.html",
    "dashboard/templates/pdf/doc_pdf.html",
    "dashboard/templates/research_detail.html"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "make security-sast: 0 blocking findings (was 16 → after S03: 0; full pipeline 94 → after S01: 16 → after S03: 0)",
  "tdd_red_evidence": "n/a — template comment-only edits, no production logic",
  "blockers": [],
  "notes": "Confirm db_guard.html is untouched and that the 12 macro-caller files were not edited."
}
```
