# CR-00051 — S06 Final Code Review Report

**Step**: S06 (CodeReviewFinal — cross-agent review of S01+S03+S05)
**Verdict**: **PASS**
**Work item**: CR-00051 — Semgrep baseline cleanup

---

## Summary

CR-00051 drives `make security-sast` from 94 blocking findings to **0** via three coordinated mechanisms:

1. **S01** — `# nosemgrep` annotations on 14 Python lines + 4 `--exclude-rule` flags in `Makefile` `security-sast:` + new triage section in `docs/IW_AI_Core_Testing_Strategy.md`.
2. **S03** — `{# nosemgrep #}` comments before the 17 `template-unescaped-with-safe` (`| safe`) call sites in dashboard templates.
3. **S05** — Unit test locking `write_button_attrs` macro's constant-output invariant + integration test invoking semgrep with the same four `--exclude-rule` flags as the Makefile.

All ACs (AC1–AC8) are met. All Invariants (I1–I4) hold. `make lint`, `make format-check`, and `make security-sast` all pass; both new tests pass. One **INFO** observation noted below regarding scope discipline; not blocking.

---

## Pre-Review Gates

| Gate | Result |
|------|--------|
| `make lint` | **OK** (`check_templates.py` + `ruff check .` — All checks passed!) |
| `make format-check` | **OK** (`ruff format --check .` — 684 files already formatted) |

---

## AC Traceability Matrix

| AC | Met by | Evidence |
|----|--------|----------|
| AC1 — `make security-sast` exits 0 | S01 + S03 | `make security-sast` ran in this review: ✅ `Findings: 0 (0 blocking)` / `Ran 308 rules on 463 files: 0 findings` / `[security-sast] OK`. Exit 0. |
| AC2 — Every suppression carries rationale | S01 + S03 | Every `# nosemgrep` / `{# nosemgrep #}` introduced by this CR has a same-line rationale after an em-dash (see grep results for `nosec B602` in Python and `^+.*nosemgrep` in template diff). 12 Class A sites with site-specific rationale; 2 Class E sites with tiktoken-model-name rationale; 17 Class B sites with source-description rationale (e.g., "chat message body (server-side citation rendering)"). |
| AC3 — Existing `# nosec` / `# noqa` preserved | S01 | All 8 pre-existing `# nosec B602` markers retained alongside new `# nosemgrep` (grep `nosec B602` shows 16 retentions across 7 files — original 8 + 4 new in `orch/test_runner.py` added for consistency per S01 obs #1 + 4 elsewhere kept). All `# noqa: B701` retained on the 2 `chat_repo.py` logger lines. `# noqa: S701` was N/A — `worktree_compose.py:219` is now `select_autoescape()` upstream (S01 obs #2). |
| AC4 — Macro output locked by unit test | S05 | `tests/unit/test_db_guard_macro.py` asserts `==` for both `EXPECTED_FRESH = ""` and `EXPECTED_STALE = 'disabled aria-disabled="true" title="Orch DB schema mismatch — run \'make db-migrate\' to fix."'`. Test passed (3/3) in this review. `dashboard/templates/macros/db_guard.html` is byte-identical to `main` (`git diff main -- … exit=0`, empty diff). |
| AC5 — Makefile excludes `unquoted-attribute-var` project-wide | S01 | `--exclude-rule generic.html-templates.security.unquoted-attribute-var.unquoted-attribute-var` present on both `security-sast` semgrep invocations. Comment block above target explains the rationale and points to the unit test that locks the macro contract. |
| AC6 — Triage section in testing strategy | S01 | Section "11. Semgrep finding triage (CR-00051)" appended to `docs/IW_AI_Core_Testing_Strategy.md`. Verified contents (see "Triage Doc Completeness" below). |
| AC7 — Baseline asserted by integration test | S05 | `tests/integration/test_security_sast_baseline.py` invokes `uv run semgrep …` with three configs + four `--exclude-rule` flags + `--error --json`, parses results, asserts `len(findings) == 0` and exit 0. Passed (1/1) in this review. |
| AC8 — Four `--exclude-rule` flags carry rationale block above target | S01 | Comment block immediately above `security-sast:` enumerates all four rules (`unquoted-attribute-var`, `var-in-href`, `var-in-script-tag`, `plaintext-http-link`), each with the reason it's project-wide-suppressed. Confirmed by reading lines 224–248 of `Makefile`. |

---

## Invariants

| Invariant | Status | Evidence |
|-----------|--------|----------|
| I1 — No `# nosec` / `# noqa` removed | **HOLDS** | `rg "# nosec B602"` returns 16 matches (8 original lines + 8 same-line additions: in `orch/test_runner.py:115, :338, :396, :643` S01 deliberately added `# nosec B602` to align all 12 Class A sites with the "both markers" pattern — net additions, no removals; documented in S01 obs #1). `rg "# noqa: B701"` returns 2 matches (both retained on `chat_repo.py:53, :63` alongside new `# nosemgrep`). |
| I2 — No new `\| safe` introduced | **HOLDS** | `git diff main -- dashboard/templates/` shows zero `^+.*\| safe` lines (excluding context). Repo currently has 18 raw `\| safe` occurrences across 17 files (one file — `docs_global_results.html` — has two `\| safe` lines at `:61` and `:64`). All 17 files are pre-existing per S01 baseline (the design under-counted at 16; S03 obs #1 documented the 17th = `components/confirm_dialog.html:12`). |
| I3 — Tests use real Jinja2 (no mocks) | **HOLDS** | `tests/unit/test_db_guard_macro.py:41–46` builds a real `jinja2.Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=True)` and registers `is_db_stale` as a normal callable (no mock library, no `unittest.mock`). |
| I4 — Test rule-set = Makefile rule-set | **HOLDS** | `tests/integration/test_security_sast_baseline.py:29–34` `SEMGREP_EXCLUDE_RULES` tuple lists the 4 rules in the exact same order as `Makefile` lines 263–266 / 270–273. Diff by inspection: ✅ identical. |

---

## Behaviour Drift Sanity Check

| Check | Result |
|-------|--------|
| `git diff main -- dashboard/templates/macros/db_guard.html` | **empty** (exit 0) — macro byte-identical to `main`. |
| `git diff main -- dashboard/templates/ \| grep "^+.*\| safe"` | empty — no new `\| safe` added. |
| `git diff main -- dashboard/templates/ \| grep "^-.*\| safe"` | empty — no `\| safe` removed. |
| Dashboard import smoke (`from dashboard.app import app`) | Blocks on `LiveDbConnectionRefusedError` — this is the live-DB guard fired by `IW_CORE_AGENT_CONTEXT` env var inside the worktree, **not** a CR-00051 regression. Same behaviour on `main`. S03 report obs #4 also noted this. |
| Dashboard test slice (`pytest tests/dashboard/ -k "queue or running or worktrees or batch_detail or project_code or research"`) | **63 passed, 2 skipped, 785 deselected** — no behavioural drift in any of the touched templates. |
| Orch production code diffs (`orch/test_runner.py`, `orch/rag/chat_repo.py`, etc.) | Pure comment changes (verified by reading every diff hunk). `orch/test_runner.py` net `-8` lines because S01 collapsed four malformed multi-line `# nosemgrep:` comments (rule-id on a continuation line — semantically invalid for semgrep) into the canonical single-line form; the Python statements (`subprocess.Popen(...)` / `subprocess.run(...)` and their argv) are untouched. |

---

## Triage Doc Completeness

Section "11. Semgrep finding triage (CR-00051)" in `docs/IW_AI_Core_Testing_Strategy.md` checked against the prompt's required content:

- [x] States `# nosec` does NOT silence Semgrep (explicit sentence under the section header).
- [x] Notes in-macro `{# nosemgrep #}` does NOT propagate to call-site analyses (explicit subsection "Macro-emitted findings do not propagate").
- [x] Python syntax shown: `# nosemgrep: <rule-id>`.
- [x] Jinja2 syntax shown: `{# nosemgrep: <rule-id> — <rationale> #}`.
- [x] Makefile syntax shown: `--exclude-rule <rule-id>` + rationale comment block above the target.
- [x] Four legitimate reasons enumerated: confirmed FP, trusted-source rendering, deliberate-but-audited pattern, project-wide structural FP.
- [x] Requires same-line rationale after em-dash for per-line suppressions (with full example).
- [x] Requires rationale comment block above the target for Makefile excludes.

---

## Test Quality

`tests/unit/test_db_guard_macro.py`:

- [x] Strong assertions: `assert rendered == EXPECTED_FRESH/EXPECTED_STALE` (byte-equality), `assert open_count == 2`.
- [x] No `assert is not None` / no `assert len(...) > 0` / no boolean truthiness checks.
- [x] No fixture leakage: `jinja_env` is `@pytest.fixture` (function-scoped by default); no env vars set; no `tmp_path` reuse.
- [x] No `importlib.reload(orch.config)` (forbidden per `tests/CLAUDE.md`).
- [x] Does NOT modify `db_guard.html`. RED was captured at write time via the wrong-constant technique (`EXPECTED_STALE = "WRONG_INTENTIONALLY_TO_CAPTURE_RED"`), per S05 report. The actual file on disk is byte-identical to `main`.
- [x] Real `jinja2.Environment` + `FileSystemLoader` (Invariant I3).

`tests/integration/test_security_sast_baseline.py`:

- [x] Strong assertion: `len(findings) == 0` with a helpful failure message enumerating up to 20 finding sites.
- [x] Clear skip reason: `"semgrep not installed (install with \`uv sync --dev\`)"`.
- [x] No env var pollution; no fixture state across tests.
- [x] Uses `subprocess.run(... shell=False ...)` with controlled `cmd` argv — `# noqa: S603` rationale ("controlled argv, no shell") is on the line.
- [x] `SEMGREP_EXCLUDE_RULES` tuple at module top is the single source of truth aligned with the Makefile (Invariant I4).

---

## Scope Discipline

`git diff --name-only main...HEAD` is empty because the changes are uncommitted in the worktree; the equivalent `git diff --name-only` against `main` gives **27 files**:

```
Makefile
dashboard/routers/staleness.py
dashboard/templates/chat/message.html
dashboard/templates/chat/parts/table.html
dashboard/templates/chat/parts/text.html
dashboard/templates/components/confirm_dialog.html   ← INFO: not in workflow-manifest scope.allowed_paths
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
docs/IW_AI_Core_Testing_Strategy.md
orch/archive/batch_archiver.py
orch/daemon/batch_manager.py
orch/daemon/browser_env.py
orch/daemon/doc_job_poller.py
orch/daemon/fix_cycle.py
orch/rag/chat_repo.py
orch/test_runner.py
```

Plus the two added test files (`tests/unit/test_db_guard_macro.py`, `tests/integration/test_security_sast_baseline.py`) — both explicitly in `scope.allowed_paths`.

Verifications:

- `dashboard/templates/macros/db_guard.html` — **not in diff** ✓ (byte-identical to main).
- 11 of the 12 `write_button_attrs(request)` caller files (queue.html, running.html, worktrees.html, project_code.html, action_button.html, containers_table.html, daemon_panel.html, quality_launch.html, tests_launch.html, worktree_table.html) — **not in diff** ✓.
- `docs_detail.html` is in the diff (expected — Class B `:223` annotation; Class C lines `:68, :78` left untouched per the design).

### INFO finding (one)

**INFO — `dashboard/templates/components/confirm_dialog.html` is in the diff but absent from `workflow-manifest.json:scope.allowed_paths`.**

S03 added the Class B `{# nosemgrep #}` annotation at line 12 (`{{ form_html | safe }}`). The file was originally listed in the design (line 58) as a Class C `write_button_attrs(request)` caller, but a `grep` confirms it does NOT call `write_button_attrs` — it is a `confirm_dialog` macro definition with its own independent Class B `| safe` site. The S03 report (obs #1) explicitly documents this discrepancy and the decision to treat it as Class B.

Why this is INFO, not CRITICAL:

1. Not editing this file would have left a residual Class B finding and failed AC1 (`make security-sast` exit 0). The edit was forced by the deliverable.
2. The change is mechanically identical to the 16 other Class B template edits (single `{# nosemgrep #}` comment line, no logic change, no markup change).
3. S04 (per-step review) accepted the edit.
4. The design's `Impacted Paths` section grouped this file ambiguously under Class C — a design defect, not an S03 scope violation.

Recommendation (future-only): update the workflow manifest's `scope.allowed_paths` whenever a discovery during S03 reveals a file mis-classification, so the scope artefact stays accurate. No action needed for this CR.

---

## Self-Assessment Readiness (for S15)

- [x] Reports for S01, S02, S03, S04, S05 are present under `ai-dev/active/CR-00051/reports/`.
- [x] No retried fix cycles visible in `iw item-status CR-00051 --json` (all 5 prior steps `completed`; no `failed`/`retry` entries).
- [x] Each step's report contains a clean subagent-result JSON block with `completion_status: complete`, `tests_passed: true`, and `blockers: []`.

---

## Test Verification (mandatory)

```bash
$ uv run pytest tests/unit/test_db_guard_macro.py -v
tests/unit/test_db_guard_macro.py::test_write_button_attrs_when_db_is_fresh PASSED [ 33%]
tests/unit/test_db_guard_macro.py::test_write_button_attrs_when_db_is_stale PASSED [ 66%]
tests/unit/test_db_guard_macro.py::test_write_button_attrs_output_is_well_formed_html_attrs PASSED [100%]
============================== 3 passed in 0.04s ===============================

$ uv run pytest tests/integration/test_security_sast_baseline.py -v
tests/integration/test_security_sast_baseline.py::test_semgrep_baseline_is_zero_blocking_findings PASSED [100%]
============================== 1 passed in 5.71s ===============================

$ make security-sast
[security-sast] semgrep ...
…
✅ Scan completed successfully.
 • Findings: 0 (0 blocking)
 • Rules run: 308
 • Targets scanned: 463
Ran 308 rules on 463 files: 0 findings.
[security-sast] OK
```

All three gates passed.

---

## Findings

| Sev | Title | File | Notes |
|-----|-------|------|-------|
| INFO | `confirm_dialog.html` outside `scope.allowed_paths` | `ai-dev/active/CR-00051/workflow-manifest.json` | See "Scope Discipline" section above. Edit was forced by AC1; design mis-classified the file. No fix required for this CR. |

No CRITICAL, HIGH, MEDIUM_FIXABLE, or LOW findings.

---

## Subagent Result Contract

```json
{
  "step": "S06",
  "agent": "CodeReview_Final",
  "work_item": "CR-00051",
  "step_reviewed": "S01+S03+S05",
  "verdict": "pass",
  "findings": [
    {
      "severity": "info",
      "title": "confirm_dialog.html edit outside workflow-manifest scope.allowed_paths",
      "file": "ai-dev/active/CR-00051/workflow-manifest.json",
      "rationale": "S03 added a Class B {# nosemgrep #} annotation to dashboard/templates/components/confirm_dialog.html:12 (form_html | safe) because grep confirmed the file does not call write_button_attrs — the design's Class C grouping was a mis-classification. Editing the file was required by AC1 (make security-sast exit 0). S04 accepted the edit. No fix needed for this CR; future improvement is to refresh scope.allowed_paths during step execution when design defects are discovered."
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "All 3 gates passed: tests/unit/test_db_guard_macro.py (3 passed in 0.04s); tests/integration/test_security_sast_baseline.py (1 passed in 5.71s, semgrep installed locally — full SAST scan, 0 blocking findings); make security-sast (Findings: 0 (0 blocking); Ran 308 rules on 463 files; exit 0). make lint and make format-check also passed.",
  "notes": "AC1–AC8 all met (full traceability matrix in the report body). Invariants I1–I4 all hold. dashboard/templates/macros/db_guard.html is byte-identical to main (git diff exit 0). orch/test_runner.py shows -8 net lines: S01 collapsed four malformed multi-line # nosemgrep: comments (semantically invalid — rule-id on a continuation line) into the canonical single-line form; the Python statements are untouched. Dashboard test slice (63 passed, 2 skipped) confirms no behavioural drift in touched templates. Live-DB guard blocking `from dashboard.app import app` is pre-existing agent-context behaviour, not a CR-00051 regression. CR-00051 is ready for QV gates S07–S14."
}
```
