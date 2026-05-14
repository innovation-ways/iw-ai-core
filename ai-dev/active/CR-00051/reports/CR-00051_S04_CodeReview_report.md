# CR-00051 — S04 CodeReview Report (review of S03 Frontend)

**Work item**: CR-00051 — Semgrep baseline cleanup
**Step**: S04 — CodeReview (over S03)
**Reviewer**: `code-review-impl`
**Verdict**: **PASS**

## Summary

S03 added rationale-bearing `{# nosemgrep: python.flask.security.xss.audit.template-unescaped-with-safe.template-unescaped-with-safe — … #}` annotations to all `{{ … | safe }}` (Class B) sites in dashboard templates. No production template logic, CSS, htmx wiring, or Class C macro/caller files were touched. The dogfood gate `make security-sast` now reports **0 findings (0 blocking)** end-to-end across S01 + S03 — AC1 satisfied.

The review found a single **LOW** observation: S03's `files_changed` is **17** files, not the **16** enumerated in the S04 prompt. The 17th file (`components/confirm_dialog.html`) contains an actual `| safe` site at line 12 that was missed by the design's enumeration; the design listed it under the Class C "12 macro-caller files" bucket, but a grep confirms `confirm_dialog.html` does **not** call `write_button_attrs(request)` — it is a macro *definition* with its own independent Class B site. The S03 agent reasoned correctly: had it followed the prompt's count literally, the dogfood gate would have ended at 1 blocking finding and AC1 would have failed. The edit was placed at line 11 (preceding the Class B `| safe` at line 12), **not** at line 16 (the Class C `unquoted-attribute-var` site that S03 was explicitly told not to touch). This is well documented in S03's report and is recommended to be reconciled in the design during S06 cross-agent review.

## Verification Results

### Pre-Review Lint & Format Gate

| Command | Result |
|---|---|
| `make lint` | **PASS** — ruff + `scripts/check_templates.py` both clean ("All checks passed!") |
| `make format-check` | **PASS** — 682 files already formatted |

### Test Verification (NON-NEGOTIABLE)

| Command | Result |
|---|---|
| `make security-sast` | **PASS** — `Findings: 0 (0 blocking)` after scanning 463 files with 308 rules. Confirms AC1. |

### Scope (Section 1)

Expected 16 files; actual 17. The 17 changed templates:

| # | File | Expected? | Notes |
|---|------|-----------|-------|
| 1 | `dashboard/templates/chat/message.html` | ✓ | |
| 2 | `dashboard/templates/chat/parts/table.html` | ✓ | |
| 3 | `dashboard/templates/chat/parts/text.html` | ✓ | |
| 4 | `dashboard/templates/components/confirm_dialog.html` | **NOT in 16** | Independent Class B site at `:12`; not a `write_button_attrs` caller. Annotation placed at `:11`, away from `:16` Class C territory. See LOW finding below. |
| 5 | `dashboard/templates/docs_detail.html` | ✓ | Edit at `:223` only (preceding the `:224` Class B `| safe`); `:68` and `:78` Class C sites untouched ✓ |
| 6 | `dashboard/templates/exports/diff_pdf.html` | ✓ | |
| 7 | `dashboard/templates/fragments/code_architecture_diagram.html` | ✓ | |
| 8 | `dashboard/templates/fragments/code_architecture_view.html` | ✓ | |
| 9 | `dashboard/templates/fragments/code_module_detail.html` | ✓ | |
| 10 | `dashboard/templates/fragments/code_symbol_panel.html` | ✓ | |
| 11 | `dashboard/templates/fragments/docs_global_results.html` | ✓ | |
| 12 | `dashboard/templates/fragments/item_design_doc.html` | ✓ | |
| 13 | `dashboard/templates/fragments/item_functional_doc.html` | ✓ | |
| 14 | `dashboard/templates/fragments/item_reports.html` | ✓ | |
| 15 | `dashboard/templates/pages/project/batch_detail.html` | ✓ | |
| 16 | `dashboard/templates/pdf/doc_pdf.html` | ✓ | |
| 17 | `dashboard/templates/research_detail.html` | ✓ | |

**Hard-rule checks**:

- `dashboard/templates/macros/db_guard.html` — **NOT modified** ✓
- 12 `write_button_attrs(request)` caller files (`action_button.html`, `worktree_table.html`, `daemon_panel.html`, `containers_table.html`, `tests_launch.html`, `quality_launch.html`, `project_code.html`, `queue.html`, `running.html`, `worktrees.html`, `item_overview.html`, `docs_detail.html`) — **none modified** for Class C reasons. (`docs_detail.html` is annotated only at the Class B `:223` site; `:68` and `:78` Class C sites untouched. ✓)
- `dashboard/static/styles.css` — **NOT modified** ✓
- Any `.iw-collision` file — **none modified** ✓ (`containers_table.html.iw-collision` exists in the worktree but git status shows no diff)
- `confirm_dialog.html`: grep confirms the file does **not** call `write_button_attrs(request)`. The 17th edit is at `:11` (Class B), not at `:16` (Class C).

### Suppression correctness (Section 2)

For each of the 17 templates: `git diff` confirms exactly **one** `{# nosemgrep: … #}` comment added, immediately preceding the line it intends to silence, no blank line in between.

- **Rule ID** — every comment uses `python.flask.security.xss.audit.template-unescaped-with-safe.template-unescaped-with-safe` exactly. ✓
- **Comment shape** — every comment is well-formed Jinja `{# … #}`. ✓
- **Rationale specificity** — every comment carries a site-specific rationale after the em-dash: `chat message body (server-side citation rendering)`, `chat table snippet`, `chat text snippet`, `dialog form HTML composed server-side from router-supplied strings`, `doc-detail rendered HTML`, `diff PDF body`, `code architecture diagram (server-built SVG)`, `code architecture view (server-built HTML)`, `code module detail panel`, `code symbol panel`, `global docs search results`, `design-doc Markdown render`, `functional-doc Markdown render`, `item-report Markdown render`, `batch-plan content`, `ProjectDoc content`, `research-doc content`. None are generic placeholders. ✓

### No new `| safe` introduced (Invariant I2, Section 3)

`git diff HEAD -- 'dashboard/templates/**' | grep '^+' | grep '| safe' | grep -v nosemgrep` returns **empty** — no new `| safe` filter was added. The 18 `| safe` occurrences in `dashboard/templates/**` (17 `{{ … | safe }}` plus one `{% set snippet = item.snippet | safe %}` at `docs_global_results.html:61`) all pre-date this CR. Invariant I2 preserved. ✓

### Dashboard imports cleanly (Section 4)

`uv run python -c "from dashboard.app import create_app"` returns `factory import OK`. Direct `from dashboard.app import app` fails on `LiveDbConnectionRefusedError` from `orch/db/live_db_guard.py` at engine-creation time (because `IW_CORE_AGENT_CONTEXT=1` is set in the agent context) — this is the **expected** live-DB guard behaviour documented in CLAUDE.md and unrelated to S03's edits. Template-parse smoke test (custom Jinja2 environment + `env.parse()` on all 17 edited templates) reported **0 errors / 17 parsed**. ✓

### Code Quality / Conventions / Security / Testing (Section 5)

Largely N/A for a comments-only template change.

- `tdd_red_evidence` in S03's report uses the `"n/a — template comment-only edits, no production logic"` form ✓
- No production code path, route, dependency, or rendering output changed ✓
- No new dependencies introduced ✓
- No client-side script added ✓

## Findings

### F1 (LOW) — `files_changed` count diverges from the prompt (17 vs 16); design enumeration is empirically short by one

- **Severity**: LOW
- **Files**: `dashboard/templates/components/confirm_dialog.html`; design `CR-00051_CR_Design.md`
- **Detail**: The S04 prompt asserts S03's `files_changed` "must be exactly these 16 files"; actual is 17. The extra file is `components/confirm_dialog.html`, which contains a real `template-unescaped-with-safe` finding at `:12` (`{{ form_html | safe }}`). The design grouped this file under the "12 `write_button_attrs(request)` caller files" bucket, but a `grep -l "write_button_attrs" dashboard/templates/ -r` confirms the file does **not** call that macro — it is a macro *definition*, and its Class B site is independent of any Class C concern. Without an annotation here `make security-sast` would have ended at 1 blocking finding and AC1 would have failed.
- **Risk assessment**: The S03 agent's edit is at `:11` (Class B, immediately preceding the `:12` `| safe`), **not** at `:16` (a separate `unquoted-attribute-var` site that S03 was correctly told not to touch). So the spirit of the "don't touch Class C / macro-caller files" rule is preserved. The S03 report explicitly flags the discrepancy and recommends S05's integration test enumerate the post-CR residual count, not the design's number, to catch this kind of drift.
- **Recommendation (defer to S06)**:
  - S06 cross-review should update `CR-00051_CR_Design.md` Class B count (16 → 17), the affected-files table, and the design's "12 macro-caller files" list (remove `confirm_dialog.html` from that list, since it does not call `write_button_attrs`).
  - S05 integration test should assert "0 blocking findings", not "exactly 31 Class A+B+D+E findings before suppression" — i.e., be robust to design-vs-empirical drift.
- **Mandatory fix?**: **No.** The empirical outcome matches the CR's goal (sast → 0); the deviation is well-documented in S03's report; reverting the edit would regress AC1. Treated as an observation to be reconciled in design + S05/S06.

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "CR-00051",
  "step_reviewed": "S03",
  "verdict": "pass",
  "findings": [
    {
      "id": "F1",
      "severity": "LOW",
      "category": "scope",
      "files": ["dashboard/templates/components/confirm_dialog.html", "ai-dev/active/CR-00051/CR-00051_CR_Design.md"],
      "summary": "files_changed is 17 (vs prompt's 16); the 17th is a real Class B site the design missed. Edit is at the Class B line, not the Class C line. AC1 (sast=0) still satisfied. Recommend S06 update design.",
      "mandatory_fix": false
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "make security-sast: 0 blocking findings; make lint OK; make format-check OK; Jinja2 parse: 17/17 OK; dashboard factory import OK.",
  "notes": "S03's deviation from the prompt's 16-file scope is justified by an empirically-missing Class B site in confirm_dialog.html. The edit respects the underlying intent (no Class C / macro-caller-file edit). Dogfood gate passes."
}
```
