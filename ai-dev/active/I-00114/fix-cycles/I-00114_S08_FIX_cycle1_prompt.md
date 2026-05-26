# I-00114 S08 QV Fix Cycle 1/3

Quality gate S08 for work item I-00114 failed. Fix the issues below so the gate passes on re-run.

## Scope (allowed_paths from workflow-manifest.json)

You MAY only modify files matching these globs:

  orch/cli/event_commands.py
  orch/cli/__init__.py
  executor/pi_narration_guard.py
  orch/daemon/batch_manager.py
  orch/daemon/fix_cycle.py
  tests/unit/test_pi_narration_guard.py
  tests/integration/test_pi_narration_guard.py
  tests/unit/test_event_command.py
  tests/unit/test_daemon_command_builders.py
  tests/integration/_stub_pi.py

The following paths are ALSO allowed by daemon convention (do NOT flag them as out-of-scope; the workflow itself writes here):

  ai-dev/active/I-00114/**
  ai-dev/archive/I-00114/**
  ai-dev/work/I-00114/**

Edits to files outside the combined list will block the cycle. If the
failing gate appears to require an out-of-scope edit, do NOT make it —
instead document the required out-of-scope path(s) under "blockers" in
your result contract, and the operator will amend allowed_paths.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00114/ai-dev/active/I-00114/I-00114_Issue_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Errors to Address

The block below is **one hypothesis** generated from the failed gate. Verify it against the design doc spec above before applying any fix; the spec wins on conflict.

**Error**: lint failed: exit=2

**Unparseable output** (always surfaces):
  uv run python scripts/check_templates.py
  uv run ruff check .
  PT018 Assertion should be broken down into multiple parts
    --> tests/unit/test_event_command.py:15:1
     |
  13 |     "event_commands", Path("orch/cli/event_commands.py")
  14 | )
  15 | assert _SPEC and _SPEC.loader
     | ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  16 | _MODULE = importlib.util.module_from_spec(_SPEC)
  17 | sys.modules[_SPEC.name] = _MODULE
     |
  help: Break down assertion into multiple parts
  PT018 Assertion should be broken down into multiple parts
    --> tests/unit/test_pi_narration_guard.py:11:1
     |
   9 |     "pi_narration_guard", Path("executor/pi_narration_guard.py")
  10 | )
  11 | assert _SPEC and _SPEC.loader
     | ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  12 | _MODULE = importlib.util.module_from_spec(_SPEC)
  13 | sys.modules[_SPEC.name] = _MODULE
     |
  help: Break down assertion into multiple parts
  Found 2 errors.
  No fixes available (2 hidden fixes can be enabled with the `--unsafe-fixes` option).
  make: *** [Makefile:30: lint] Error 1


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
5. **Post-edit cross-gate check (MANDATORY before exit).** When the
   failing gate is NOT lint/format, your edits may still introduce a
   new ruff violation that the next review run trips on. Before exiting,
   run `make format-check` and `make lint` and resolve any NEW violation
   your edits introduced (`uv run ruff format <file>` for format issues;
   targeted edit for lint). Diagnosed 2026-05-25 from CR-00082 S04's
   ping-pong between fix cycles where each agent re-broke the gate the
   previous one fixed.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
