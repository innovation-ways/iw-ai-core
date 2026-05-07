# F-00079_S11_CodeReview_Final_prompt

**Work Item**: F-00079 — Files view: per-item git changes explorer with step drilldown and PDF export
**Review Step**: S11 (Final Cross-Agent Review)
**Implementation Steps Reviewed**: S01..S09

---

## ⛔ Docker is off-limits

Standard policy. Read-only docker introspection allowed.

## ⛔ Migrations: agents generate, daemon applies

Read-only inspection only.

## Input Files

- `ai-dev/active/F-00079/F-00079_Feature_Design.md`
- `ai-dev/active/F-00079/F-00079_Functional.md`
- All implementation reports: `ai-dev/active/F-00079/reports/F-00079_S0*_*_report.md` (S01..S09)
- All per-agent code review reports: `..._S02_CodeReview_report.md`, `..._S04_CodeReview_report.md`, `..._S08_CodeReview_API_FE_Tmpl_report.md`, `..._S10_CodeReview_Tests_report.md`
- All files listed in all `files_changed` lists across S01..S09

## Output Files

- `ai-dev/active/F-00079/reports/F-00079_S11_CodeReview_Final_report.md`

## Context

You are performing the **final cross-agent review** of all implementation work for **F-00079: Files view**. Per-agent reviews have already been done (S02, S04, S08, S10). Your job is to catch cross-cutting issues those reviews could not — integration correctness, completeness against the design, and consistency across the entire feature surface.

Read the design document and the functional doc fully. Read all S0*_report.md files. Then inspect the union of all changed files holistically.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

ANY violation in the changed files → CRITICAL `category: "conventions"`.

## Review Checklist

### 1. Completeness vs Design Document

- ALL functional requirements from the design are implemented (the In Scope list is fully covered).
- ALL Out of Scope items are absent (no scope creep).
- ALL Acceptance Criteria (AC1..AC8) have corresponding code AND tests.
- ALL Boundary Behavior rows have test coverage.
- ALL Invariants are enforced or tested.
- The Functional Design (`F-00079_Functional.md`) accurately describes what shipped — review it as if you are a non-engineer reading the dashboard for the first time.

### 2. Cross-Agent Integration

- Migration columns (S01) are referenced correctly by the resolver (S03), the routes (S05), the templates (S06), and the PDF (S07).
- The `GENERATED_FILE_GLOBS` constant (Invariant 8) is used as a single source of truth across S03 (Python) and S06 (JS).
- `iw step-done` writes to the correct columns; the daemon writes to the correct columns; the resolver reads from the correct columns.
- The route handler in S05 calls the resolver in S03 (no inline diff logic in routes).
- The frontend in S06 consumes the documented route contract (text/plain for `/files/diff`, JSON for `/files/untracked`, application/pdf for export).
- The PDF template (S07) consumes the canonical context shape (`summary_files`, `truncated_files`, `aggregate_added`, `aggregate_removed`, `aggregate_file_count`, `step_label`, `item`, `project_id`, `generated_at`) — same names used by the route in S05. CRITICAL on mismatch.
- The 100-file PDF body cap is enforced by the route (alphabetical-by-path) and the template renders body diffs only for `summary_files`, with a footer note covering `truncated_files`.
- diff2html-ui is vendored under `dashboard/static/vendor/diff2html/<version>/` — no CDN URLs anywhere in `dashboard/templates/` or `dashboard/static/`.
- Per-file collapse on the Files tab is purely client-side (no `/files/diff` roundtrip per file).

### 3. Architecture Compliance

- Routers stay thin (validation + delegation).
- Business logic is in `orch/`.
- Append-only convention on `step_runs` is preserved (Invariant 6).
- No psycopg2 imports anywhere.
- No `importlib.reload(orch.config)` in tests.
- No live-DB connections in tests.
- No `chromium.launch()` or `agent-browser` in browser tests.

### 4. Removal Completeness

- `dashboard/templates/fragments/item_artifacts.html` is gone.
- `/tab/artifacts` route is removed.
- `_list_artifact_tree`, `_build_artifact_tree`, `ArtifactNode` are either gone or justified.
- `/artifact-raw` is preserved (untracked sub-panel needs it).
- `item_detail.html` no longer references the Artifacts tab.

### 5. Security

- No hardcoded secrets, credentials, paths.
- Path traversal protection in `/artifact-raw` and `/files/untracked` (untrusted `path` param must be validated against the worktree root).
- No SQL injection (parameterised queries everywhere).
- WeasyPrint receives sanitized HTML; Pygments output is the only un-escaped content (acceptable because Pygments output is trusted-generated).
- No XSS in the Files tab: diff content rendered via diff2html or Pygments — both produce escaped HTML.

### 6. Performance

- Diffs >5000 lines are not loaded inline.
- Files >500 lines are auto-collapsed with htmx lazy-load.
- Generated files are auto-collapsed regardless of count.
- Aggregate diff fetch is one round-trip per step toggle, not per file.

### 7. Observability

- Failed captures emit `daemon_events` warnings (not errors that scare operators).
- No full diff text in logs.
- Module-level loggers everywhere.

### 8. Documentation

- Migration file has a clear message.
- New module `orch/diff_service.py` has a module docstring explaining the resolver contract.
- `dashboard/CLAUDE.md` and `orch/CLAUDE.md` do NOT need updates unless a new pattern was introduced — assess and note in your report.

## Test Verification (NON-NEGOTIABLE)

```bash
make test-unit
make test-integration
make test-frontend
```

If any suite fails → CRITICAL finding.

## Severity Levels

| Severity | Meaning | Action |
|---|---|---|
| CRITICAL | Breaks functionality, missing requirement, security | Must fix before merge |
| HIGH | Significant integration failure, architectural violation | Must fix before merge |
| MEDIUM (fixable) | Code quality, missing edge case | Should fix |
| MEDIUM (suggestion) | Better pattern available | Optional |
| LOW | Nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S11",
  "agent": "CodeReview_Final",
  "work_item": "F-00079",
  "steps_reviewed": ["S01", "S03", "S05", "S06", "S07", "S09"],
  "verdict": "pass|fail",
  "findings": [...],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit, Y integration, Z frontend, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```

- `missing_requirements`: list any design requirements without corresponding code; each is automatically a CRITICAL finding.
