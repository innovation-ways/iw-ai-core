# F-00088 S06 QV Fix Cycle 2/3

Quality gate S06 for work item F-00088 failed. Fix the issues below so the gate passes on re-run.

## Scope (allowed_paths from workflow-manifest.json)

You MAY only modify files matching these globs:

  tests/e2e/**
  pyproject.toml
  uv.lock
  Makefile
  scripts/e2e_seed.py
  .github/workflows/e2e.yml
  docs/IW_AI_Core_Testing_Strategy.md
  skills/iw-ai-core-testing/**
  .claude/skills/iw-ai-core-testing/**
  ai-dev/work/TESTS_ENHANCEMENT.md

Edits to files outside this list will block the cycle. If the failing gate
appears to require an out-of-scope edit, do NOT make it — instead document
the required out-of-scope path(s) under "blockers" in your result contract,
and the operator will amend allowed_paths.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00088/ai-dev/active/F-00088/F-00088_Feature_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Errors to Address

The block below is **one hypothesis** generated from the failed gate. Verify it against the design doc spec above before applying any fix; the spec wins on conflict.

**Error**: lint failed: exit=2

**Unparseable output** (always surfaces):
  uv run python scripts/check_templates.py
  uv run ruff check .
  E501 Line too long (101 > 100)
     --> tests/e2e/playwright_wrapper.py:130:101
      |
  128 |         if not log_dir.exists():
  129 |             return ""
  130 |         yml_files = sorted(log_dir.glob("page-*.yml"), key=lambda p: p.stat().st_mtime, reverse=True)
      |                                                                                                     ^
  131 |         if not yml_files:
  132 |             return ""
      |
  E501 Line too long (104 > 100)
     --> tests/e2e/test_journey_docs_export.py:156:101
      |
  154 |     for line in lines:
  155 |         lower = line.lower()
  156 |         if ("architecture" in lower and any(tag in lower for tag in ("heading", "level-1", "level-3"))):
      |                                                                                                     ^^^^
  157 |             return line
  158 |     return ""
      |
  E741 Ambiguous variable name: `l`
     --> tests/e2e/test_journey_jobs_filters.py:106:33
      |
  104 |     #    the job-type rows.  A genuine filter narrows both.
  105 |     # ------------------------------------------------------------------
  106 |     raw_filtered_lines = [l for l in snap_filtered.splitlines() if "row " in l]
      |                                 ^
  107 |     raw_filtered_count = len(raw_filtered_lines)
  108 |     filtered_rows = _extract_job_rows(snap_filtered)
      |
  F841 Local variable `raw_filtered_count` is assigned to but never used
     --> tests/e2e/test_journey_jobs_filters.py:107:5
      |
  105 |     # ------------------------------------------------------------------
  106 |     raw_filtered_lines = [l for l in snap_filtered.splitlines() if "row " in l]
  107 |     raw_filtered_count = len(raw_filtered_lines)
      |     ^^^^^^^^^^^^^^^^^^
  108 |     filtered_rows = _extract_job_rows(snap_filtered)
  109 |     filtered_count = len(filtered_rows)
      |
  help: Remove assignment to unused variable `raw_filtered_count`
  Found 4 errors.
  No fixes available (1 hidden fix can be enabled with the `--unsafe-fixes` option).
  make: *** [Makefile:28: lint] Error 1


## Gate Command

The quality gate that failed runs:
```bash
make lint
```

After applying fixes, re-run this command to verify the issues are resolved.

## Pre-fix Procedure

1. **Read the design doc** at the path above. Skim the section that covers this step's scope; quote-of-the-doc lives in this prompt when available.
2. **Diff your target file(s) against the spec** — list deviations explicitly before editing.
3. **Apply the minimum patch** to align code with the spec; the reported errors should resolve as a side effect of that alignment.
4. **If the errors disagree with the spec, the spec wins.** Note the disagreement in your output rather than silently following the errors.

## Constraints

1. **Only fix the reported errors.** Do not refactor unrelated code.
2. **Preserve existing behavior.** Fixes must not break working functionality.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. **Run the gate command after every fix** to verify resolution.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
