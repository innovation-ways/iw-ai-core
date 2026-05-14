# CR-00051: Semgrep baseline cleanup — drive `make security-sast` to zero blocking findings

**Type**: Change Request
**Priority**: High
**Reason**: Unblock the S11 `security-sast` quality gate. CR-00050 promoted Semgrep to blocking before the baseline of pre-existing findings was triaged, so every in-flight work item now fails S11 on issues outside its own scope. F-00082 already had S11 skipped to unblock its merge — see the skip reason in `iw item-status F-00082`. This CR resolves the baseline so no further item has to skip the gate.
**Created**: 2026-05-14
**Status**: Draft

---

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

Leaves migrations unchanged.

## Description

Drive `make security-sast` from 94 blocking findings to 0 using two mechanisms: (a) per-line `# nosemgrep` / `{# nosemgrep #}` annotations with rationale on the 31 sites whose rule is high-signal (subprocess shell invocations ×12, `| safe` Markdown rendering ×16, Jinja autoescape on YAML ×1, logger-credential false positives ×2); (b) four `--exclude-rule` flags added to the Makefile `security-sast` target for rules whose entire finding population in this codebase is structurally false-positive: `unquoted-attribute-var` (26 findings, all `write_button_attrs(request)` macro callers — empirically verified that in-macro Jinja `{# nosemgrep #}` does NOT propagate to the call-site analysis), `var-in-href` (31 findings, all route-supplied or template-author URLs), `var-in-script-tag` (5 findings, all `{{ … | tojson }}` inside `<script>` — Semgrep does not model the `tojson` filter), and `plaintext-http-link` (1 finding, a dev-only localhost link). Add a short triage convention to `docs/IW_AI_Core_Testing_Strategy.md`. Make the CR dogfood its own change by running `make security-sast` as its S11 gate and refusing to merge unless exit code is zero.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Critical for this CR: every change here is a comment, a Makefile flag, a config edit, or a new test — no production behaviour changes. The `dashboard/` layer rules (thin routers, htmx, Tailwind prebuilt) are unaffected; the `orch/` layer rules (no docker / no live alembic) are unaffected.

## Current Behavior

`make security-sast` runs Semgrep with three rule packs (`p/python`, `p/owasp-top-ten`, `p/security-audit`) over `orch/`, `dashboard/`, and `executor/`. A clean run on `main` today exits **2** with **94 blocking findings**, distributed across eight rules:

- **Class A (12 findings, 7 files)** — `python.lang.security.audit.subprocess-shell-true.subprocess-shell-true`:
  - `dashboard/routers/staleness.py:178`
  - `orch/archive/batch_archiver.py:325`
  - `orch/daemon/batch_manager.py:875`, `:1302`
  - `orch/daemon/browser_env.py:421`, `:650`
  - `orch/daemon/doc_job_poller.py:248`
  - `orch/daemon/fix_cycle.py:1258`
  - `orch/test_runner.py:115`, `:338`, `:396`, `:643`

  Every site already carries `# nosec B602` from a prior bandit cleanup. Each is a deliberate shell invocation of a constructed command (executor scripts, docker compose, agent launches) where no user input flows through `argv`. Semgrep does not honour bandit's `# nosec` markers.

- **Class B (16 findings, 16 files)** — `python.flask.security.xss.audit.template-unescaped-with-safe.template-unescaped-with-safe`:
  - `dashboard/templates/chat/message.html:3` (`content | safe`)
  - `dashboard/templates/chat/parts/table.html:13`, `dashboard/templates/chat/parts/text.html:2` — citation/RAG snippet rendering
  - `dashboard/templates/docs_detail.html:223` (`rendered_html | safe`)
  - `dashboard/templates/exports/diff_pdf.html:450`
  - `dashboard/templates/fragments/code_architecture_diagram.html:10`, `dashboard/templates/fragments/code_architecture_view.html:30`, `dashboard/templates/fragments/code_module_detail.html:80`, `dashboard/templates/fragments/code_symbol_panel.html:13` — code-understanding panels rendering server-built HTML/SVG
  - `dashboard/templates/fragments/docs_global_results.html:63`
  - `dashboard/templates/fragments/item_design_doc.html:61`, `dashboard/templates/fragments/item_functional_doc.html:60`, `dashboard/templates/fragments/item_reports.html:37` — Markdown-rendered design / functional / report docs
  - `dashboard/templates/pages/project/batch_detail.html:113` (`plan_html | safe`)
  - `dashboard/templates/pdf/doc_pdf.html:172` (`rendered_content | safe`)
  - `dashboard/templates/research_detail.html:131` (`content_html | safe`)

  Every value passed through `| safe` is server-side Markdown→HTML or pre-rendered HTML/SVG built from trusted in-DB content (design docs, research notes, doc-system output, RAG citations, code-understanding panels). No user-derived data flows through `| safe` on these lines.

- **Class C (project-wide-excluded — `unquoted-attribute-var`, 26 findings, 12 files — all `write_button_attrs(request)` call sites)** — `generic.html-templates.security.unquoted-attribute-var.unquoted-attribute-var`:
  - `dashboard/templates/components/action_button.html:9, :21, :33, :45, :57, :70, :82` (7 sites)
  - `dashboard/templates/components/confirm_dialog.html:16`
  - `dashboard/templates/docs_detail.html:68, :78`
  - `dashboard/templates/fragments/containers_table.html:167`
  - `dashboard/templates/fragments/daemon_panel.html:87, :96, :105`
  - `dashboard/templates/fragments/quality_launch.html:94, :104`
  - `dashboard/templates/fragments/tests_launch.html:94`
  - `dashboard/templates/fragments/worktree_table.html:259`
  - `dashboard/templates/pages/project/queue.html:117, :174`
  - `dashboard/templates/pages/system/running.html:137`
  - `dashboard/templates/pages/system/worktrees.html:23`
  - `dashboard/templates/project_code.html:52, :63, :74, :85`

  Every one of these 26 sites is a `{{ write_button_attrs(request) }}` macro call. The `write_button_attrs` macro (`dashboard/templates/macros/db_guard.html`) renders a constant string of pre-quoted HTML attributes — `disabled aria-disabled="true" title="Orch DB schema mismatch — run 'make db-migrate' to fix."` — with no user input.

  **Empirically verified** (semgrep 1.158.0): an in-macro Jinja `{# nosemgrep #}` in `db_guard.html` does NOT silence the call-site findings — the count remains 26. Wrapping the macro output in `markupsafe.Markup()` or `|safe` also does not help (and introduces a new `template-unescaped-with-safe` finding). Per-line `{# nosemgrep #}` annotation at each of the 26 call sites would work but requires editing 12 caller files for a rule whose entire finding population is structurally false-positive. The chosen approach is a Makefile `--exclude-rule` flag for this rule, identical in mechanism to Classes F/G/H below. The macro itself is NOT modified by this CR.

- **Class D (1 finding)** — `python.jinja2.security.audit.autoescape-disabled-false.incorrect-autoescape-disabled` on `orch/daemon/worktree_compose.py:219`. The Jinja `Environment` here renders YAML, not HTML. The line already carries `# noqa: S701  YAML output, not HTML`. Confirmed false positive.

- **Class E (2 findings)** — `python.lang.security.audit.logging.logger-credential-leak.python-logger-credential-disclosure` on `orch/rag/chat_repo.py:53, :63`. The rule fires because the format string contains the word "model" and treats `%s` as a credential placeholder. Both call sites log only a tiktoken model name in a fallback warning. Confirmed false positive.

- **Class F (project-wide noise rule — `var-in-href`, 31 findings, 29 files)** — `generic.html-templates.security.var-in-href.var-in-href`. Every flagged site is one of: a hardcoded route path in a literal tuple (`base.html:133`, `nav_projects.html:28`), a server-computed URL from a route helper (`page_url(...)`, `seg.report_file`), a template-author-supplied macro parameter (`empty_state.html:7, :9`), or a route-supplied "docs link" parameter in the help partials (`_partials/help/*.html:25–27` — 22 files). The rule cannot prove safety statically for any `<a href="{{ … }}">`, but inspection confirms 0 of the 31 sites take user-controlled input. Per-line annotation across 31 sites in 29 files would create churn and would be re-triggered by every new template that adds a server-supplied href.

- **Class G (project-wide noise rule — `var-in-script-tag`, 5 findings, 1 file)** — `generic.html-templates.security.var-in-script-tag.var-in-script-tag` on `dashboard/templates/fragments/item_files.html:132–136`. Every flagged value is rendered through Jinja's `tojson` filter (`{{ project_id | tojson }}`, etc.), which emits a syntactically valid JSON literal — i.e., a safe JS expression. The rule does not model the `tojson` filter and fires blanket on any `{{ … }}` inside a `<script>` tag. False positive.

- **Class H (project-wide noise rule — `plaintext-http-link`, 1 finding, 1 file)** — `html.security.plaintext-http-link.plaintext-http-link` on `dashboard/templates/fragments/worktree_table.html:229`. The link is `<a href="http://localhost:{{ wt.app_port }}">` — a dev-only link to the per-worktree app stack running on a local port. Never reachable in production; never a target for MITM.

All 94 findings come from CR-00050's promotion of Semgrep to blocking. No new issues have been introduced since.

## Desired Behavior

`make security-sast` exits **0** with **0 blocking findings** on `main`. Every per-line suppression carries a same-line rationale comment. The four `--exclude-rule` flags in the Makefile each carry an inline rationale (one comment per rule above the target). The Semgrep S11 gate works again for every in-flight work item; no further `iw step-skip` workarounds are needed for security-sast. A short section in `docs/IW_AI_Core_Testing_Strategy.md` documents how future Semgrep findings should be triaged (fix vs. suppress with per-line rationale vs. add a Makefile rule-exclude with rationale).

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `make security-sast` exit code on `main` | 2 (94 blocking findings) | 0 (0 blocking findings) |
| `orch/` and `dashboard/routers/` `subprocess.run(..., shell=True)` call sites (12 lines) | `# nosec B602` only | `# nosec B602` retained **and** `# nosemgrep: <rule>` added with rationale |
| Jinja `\| safe` call sites in dashboard templates (16 lines) | flagged blocking | precede with `{# nosemgrep: <rule> — <rationale> #}` |
| `write_button_attrs` macro (`db_guard.html`) | flagged on all 26 callers | unchanged — rule excluded project-wide via Makefile `--exclude-rule` for `unquoted-attribute-var` |
| `orch/daemon/worktree_compose.py:219` Jinja autoescape=False | `# noqa: S701` only | `# noqa: S701` retained **and** `# nosemgrep: <rule>` added |
| `orch/rag/chat_repo.py:53, :63` logger.warning | unannotated | `# nosemgrep: <rule>` added with rationale |
| `Makefile` `security-sast` target | `semgrep --config p/python --config p/owasp-top-ten --config p/security-audit orch dashboard executor --error` (×2 invocations) | same invocations + four `--exclude-rule` flags (`unquoted-attribute-var`, `var-in-href`, `var-in-script-tag`, `plaintext-http-link`), with an inline comment block above the target documenting the rationale for each excluded rule |
| Triage doc | no convention | new section in `docs/IW_AI_Core_Testing_Strategy.md` |

### Breaking Changes

None. Every change in this CR is a comment, a Makefile flag, or a new test. No production code path changes shape, behaviour, or rendering output.

### Data Migration

None.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | Backend (`backend-impl`) | Add `# nosemgrep` to the 15 Python lines (Classes A, D, E). Add four `--exclude-rule` flags + rationale comment block to `Makefile` `security-sast` target (covers Classes C, F, G, H). Append the Semgrep triage section to `docs/IW_AI_Core_Testing_Strategy.md`. | — |
| S02 | CodeReview (`code-review-impl`) | Review S01 | — |
| S03 | Frontend (`frontend-impl`) | Add `{# nosemgrep #}` to the 16 Class B template lines (`template-unescaped-with-safe` `\| safe` filter sites). No edits to `db_guard.html` or to any of the 12 macro-caller files. | — |
| S04 | CodeReview (`code-review-impl`) | Review S03 | — |
| S05 | Tests (`tests-impl`) | Unit test for the `write_button_attrs` macro (locks the macro's constant-attribute output as a regression guard — Class C's Makefile-exclude is justified only as long as the macro emits a constant attribute string); integration test asserting `semgrep` exit 0 / zero blocking findings against the current source tree via the same arguments the Makefile uses (including all four `--exclude-rule` flags). | — |
| S06 | CodeReview_Final (`code-review-final-impl`) | Cross-agent review S01+S03+S05 | — |
| S07–S14 | QV Gates (`qv-gate`) | lint, format-check, type-check, arch-check, security-sast (dogfood), unit-tests, frontend-tests, integration-tests | — |
| S15 | SelfAssess (`self-assess-impl`) | Self-assessment via the iw-item-analyze skill (project has `self_assess = true`) | — |

No `qv-browser` step — this CR has zero user-visible behaviour change.

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None — no alembic revision in this CR.

### API Changes

- **New endpoints**: None
- **Modified endpoints**: None
- **Removed endpoints**: None

### Frontend Changes

- **New components**: None
- **Modified components**: None — annotations only on existing macros and pages.
- **Removed components**: None

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `CR-00051_CR_Design.md` | Design | This document |
| `CR-00051_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/CR-00051_S01_Backend_prompt.md` | Prompt | S01 — Python suppressions + Makefile rule-excludes + triage doc |
| `prompts/CR-00051_S02_CodeReview_prompt.md` | Prompt | S02 — review S01 |
| `prompts/CR-00051_S03_Frontend_prompt.md` | Prompt | S03 — Class B per-line annotations (Class C is handled in S01 via Makefile `--exclude-rule`) |
| `prompts/CR-00051_S04_CodeReview_prompt.md` | Prompt | S04 — review S03 |
| `prompts/CR-00051_S05_Tests_prompt.md` | Prompt | S05 — macro unit test + baseline integration test |
| `prompts/CR-00051_S06_CodeReview_Final_prompt.md` | Prompt | S06 — cross-agent review |
| `prompts/CR-00051_S15_SelfAssess_prompt.md` | Prompt | S15 — self-assessment |

Reports are created during execution in `ai-dev/active/CR-00051/reports/`.

## Acceptance Criteria

### AC1: `make security-sast` exits 0

```
Given the CR-00051 branch with all suppressions and Makefile rule-excludes applied
When the merge-queue dry-run executes `make security-sast`
Then the command exits 0 with "Findings: 0 (0 blocking)"
```

### AC2: All per-line suppressions carry a rationale

```
Given any new `# nosemgrep` or `{# nosemgrep #}` comment introduced by this CR
When a reviewer inspects the same line or the preceding line
Then a same-line rationale comment is present (e.g., `— constant title string, no user input`)
```

### AC3: Existing `# nosec` / `# noqa` annotations are preserved

```
Given any line that currently carries `# nosec B602` or `# noqa: S701`
When this CR adds a `# nosemgrep` annotation to the same line
Then the existing `# nosec` / `# noqa` marker is retained (Invariant I1)
```

### AC4: `write_button_attrs` macro output is locked-in as a regression guard

```
Given the existing `write_button_attrs` macro (unchanged by this CR)
When a unit test renders it with `is_db_stale(request) == False` and again with `True`
Then the output is exactly `""` for `False` and exactly `disabled aria-disabled="true" title="Orch DB schema mismatch — run 'make db-migrate' to fix."` for `True` (the test locks this so that any future drift toward user-input interpolation in the macro fails CI — preserving the rationale for excluding `unquoted-attribute-var` project-wide)
```

### AC5: Class C suppression covers every present and future `write_button_attrs(request)` call site

```
Given the Makefile `--exclude-rule generic.html-templates.security.unquoted-attribute-var.unquoted-attribute-var` flag
When a new template adds `{{ write_button_attrs(request) }}` and `make security-sast` runs
Then the new call site does not produce a blocking `unquoted-attribute-var` finding (the rule is excluded project-wide; rationale is in the Makefile comment block and is justified only as long as the macro emits a constant attribute string — see AC4)
```

### AC6: Triage convention is documented

```
Given `docs/IW_AI_Core_Testing_Strategy.md` after this CR
When a developer triages a new Semgrep finding
Then the file contains a section that distinguishes "fix it" from "suppress per-line with rationale" from "add to Makefile --exclude-rule with rationale" and gives the exact comment syntax / Makefile flag syntax to use
```

### AC7: Baseline-zero is asserted by an integration test

```
Given the new integration test `tests/integration/test_security_sast_baseline.py`
When `make test-integration` runs
Then the test invokes Semgrep against the source tree using the same argument set the Makefile uses (including `--exclude-rule` flags) and asserts zero blocking findings (xfail-skip with a clear reason if `semgrep` is not installed in the test environment)
```

### AC8: The four `--exclude-rule` flags each carry a rationale comment in the Makefile

```
Given the `security-sast` target in `Makefile` after this CR
When a reviewer inspects the target
Then a comment block immediately above the target lists each of the four excluded rules (`unquoted-attribute-var`, `var-in-href`, `var-in-script-tag`, `plaintext-http-link`) and the reason it is project-wide-suppressed (false-positive density across the codebase, no true positives on inspection)
```

## Invariants

- **I1**: No existing `# nosec` or `# noqa` annotation is removed by this CR. Every new `# nosemgrep` is added alongside the existing marker, not in place of it.
- **I2**: `| safe` is preserved only on values that are demonstrably rendered server-side from trusted Markdown / HTML / SVG / JSON — i.e., the existing 16 sites. No new `| safe` is introduced.
- **I3**: Tests use real Jinja2 rendering (no mocking) when asserting macro output (per `tests/CLAUDE.md`).
- **I4**: The four Makefile `--exclude-rule` flags are rule-id-specific. No blanket rule-pack disable is introduced. The integration test invokes Semgrep with the same `--exclude-rule` set the Makefile uses (single source of truth: a tuple at the top of the test file, kept aligned with the Makefile by S04/S06 code review), so the test cannot pass against a different rule set.

## Rollback Plan

- **Database**: N/A.
- **Code**: Revert the merge commit. All changes are additive comments / Makefile flags / new test files / a new doc section. Reverting restores the pre-CR state cleanly.
- **Data**: No data loss possible — no runtime behaviour changes.

## Dependencies

- **Depends on**: CR-00050 (which introduced the `security-sast` gate).
- **Blocks**: Any future work item that would otherwise fail S11 on baseline findings. No specific items are listed today, but every new feature/incident/CR after F-00082 inherits the same blocker.

## Impacted Paths

```
dashboard/routers/staleness.py
dashboard/templates/chat/message.html
dashboard/templates/chat/parts/table.html
dashboard/templates/chat/parts/text.html
dashboard/templates/docs_detail.html
dashboard/templates/exports/diff_pdf.html
dashboard/templates/fragments/code_architecture_diagram.html
dashboard/templates/fragments/code_architecture_view.html
dashboard/templates/fragments/code_module_detail.html
dashboard/templates/fragments/code_symbol_panel.html
dashboard/templates/fragments/docs_global_results.html
dashboard/templates/fragments/item_design_doc.html
dashboard/templates/fragments/item_functional_doc.html
dashboard/templates/fragments/item_reports.html
dashboard/templates/pages/project/batch_detail.html
dashboard/templates/pdf/doc_pdf.html
dashboard/templates/research_detail.html
orch/archive/batch_archiver.py
orch/daemon/batch_manager.py
orch/daemon/browser_env.py
orch/daemon/doc_job_poller.py
orch/daemon/fix_cycle.py
orch/daemon/worktree_compose.py
orch/rag/chat_repo.py
orch/test_runner.py
Makefile
docs/IW_AI_Core_Testing_Strategy.md
tests/unit/test_db_guard_macro.py
tests/integration/test_security_sast_baseline.py
ai-dev/active/CR-00051/**
ai-dev/archive/CR-00051/**
```

Note on Class C: `dashboard/templates/macros/db_guard.html` is **not** modified by this CR. The 26 `write_button_attrs(request)` call sites are silenced via the Makefile `--exclude-rule generic.html-templates.security.unquoted-attribute-var.unquoted-attribute-var` flag — empirically necessary because in-macro `{# nosemgrep #}` and `markupsafe.Markup`/`|safe`-wrap approaches were both verified ineffective. The 12 caller files (queue.html, running.html, worktrees.html, project_code.html, action_button.html, confirm_dialog.html, containers_table.html, daemon_panel.html, quality_launch.html, tests_launch.html, worktree_table.html, docs_detail.html) are NOT modified.

Note on Classes F/G/H: these are silenced via the same Makefile `--exclude-rule` mechanism. All four exclude flags (Classes C, F, G, H) are documented inline above the `security-sast` target so reviewers can see at a glance which rules are project-wide-suppressed and why.

## TDD Approach

- **Unit test** — `tests/unit/test_db_guard_macro.py`: render the `write_button_attrs` macro in both `is_db_stale=True` / `=False` states (using a standalone Jinja2 `Environment` + `FileSystemLoader` per `tests/CLAUDE.md`); assert the output is exactly `""` for `False` and exactly `disabled aria-disabled="true" title="Orch DB schema mismatch — run 'make db-migrate' to fix."` for `True`. The macro is **not modified** by this CR — the test is a forward-looking regression guard that locks the rationale for the Makefile `--exclude-rule` decision (Class C is suppressed project-wide only because the macro emits a constant attribute string; if a future edit introduces user-input interpolation in the macro, this test fails and forces a review of the exclude flag).
- **Integration test** — `tests/integration/test_security_sast_baseline.py`: invoke `semgrep --config p/python --config p/owasp-top-ten --config p/security-audit --exclude-rule <each of the four rules> orch dashboard executor --error --json` as a subprocess, parse the JSON, assert `len(results['results']) == 0`; `pytest.skip` if `semgrep` is not on `PATH` with a clear reason (CI installs it; local devs may not). The test imports its `--exclude-rule` list from a Python tuple at the top of the test file (kept in sync with the Makefile by inspection during code review — Invariant I4).
- **Updated tests**: None — no existing tests need modification.

## Notes

- The original design plan for Class C relied on a `.semgrepignore` rule-scoped path filter. Semgrep's `.semgrepignore` is gitignore-style — path-scoped only, **not** rule-scoped. An intermediate plan switched to an in-macro Jinja `{# nosemgrep #}` inside `db_guard.html`; empirical verification (semgrep 1.158.0) showed that the in-macro comment does not propagate to the call-site analysis (count remained 26) and that wrapping the output in `|safe` introduces a new `template-unescaped-with-safe` finding without silencing the original 26. The final, empirically-verified strategy is the Makefile `--exclude-rule` mechanism applied identically to all four high-density-FP rules (Classes C, F, G, H). With this strategy in place, semgrep reports exactly 31 residual findings — matching Classes A (12) + B (16) + D (1) + E (2) — which S01 and S03 then drive to zero via per-line annotations.
- The CR's own S11 gate is the dogfood test for AC1 — if AC1 is not met, the CR will not merge.
- This CR deliberately does NOT relax the `security-sast` gate to advisory. The original intake floated a "advisory until clean, then re-promote" plan; since this CR drives baseline to zero in one shot, the gate stays blocking on every PR.
- The triage doc section must explicitly mention that `# nosec` (bandit) does not silence Semgrep, and that the project requires one of: per-line `# nosemgrep: <rule-id> — <reason>`, per-line `{# nosemgrep: <rule-id> — <reason> #}`, or a Makefile `--exclude-rule <rule-id>` flag accompanied by a rationale comment.
