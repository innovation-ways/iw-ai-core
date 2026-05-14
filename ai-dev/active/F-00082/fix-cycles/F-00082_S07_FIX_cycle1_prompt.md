# F-00082 S07 QV Fix Cycle 1/3

Quality gate S07 for work item F-00082 failed. Fix the issues below so the gate passes on re-run.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00082/ai-dev/active/F-00082/F-00082_Feature_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Errors to Address

The block below is **one hypothesis** generated from the failed gate. Verify it against the design doc spec above before applying any fix; the spec wins on conflict.

**Error**: lint failed: exit=2

**Unparseable output** (always surfaces):
  uv run python scripts/check_templates.py
  uv run ruff check .
  E501 Line too long (125 > 100)
     --> orch/test_runner.py:113:101
      |
  111 |         try:
  112 |             with Path(log_path).open("w") as log_file:
  113 |                 proc = subprocess.Popen(  # nosemgrep: python.lang.security.audit.subprocess-shell-true.subprocess-shell-true
      |                                                                                                     ^^^^^^^^^^^^^^^^^^^^^^^^^
  114 |                     command,
  115 |                     shell=True,  # nosemgrep: python.lang.security.audit.subprocess-shell-true.subprocess-shell-true
      |
  E501 Line too long (116 > 100)
     --> orch/test_runner.py:115:101
      |
  113 |                 proc = subprocess.Popen(  # nosemgrep: python.lang.security.audit.subprocess-shell-true.subprocess-shell-true
  114 |                     command,
  115 |                     shell=True,  # nosemgrep: python.lang.security.audit.subprocess-shell-true.subprocess-shell-true
      |                                                                                                     ^^^^^^^^^^^^^^^^
  116 |                     cwd=execution_dir,
  117 |                     stdout=log_file,
      |
  E501 Line too long (125 > 100)
     --> orch/test_runner.py:336:101
      |
  334 |         try:
  335 |             with Path(log_path).open("w") as log_file:
  336 |                 proc = subprocess.Popen(  # nosemgrep: python.lang.security.audit.subprocess-shell-true.subprocess-shell-true
      |                                                                                                     ^^^^^^^^^^^^^^^^^^^^^^^^^
  337 |                     agent_command,
  338 |                     shell=True,  # nosemgrep: python.lang.security.audit.subprocess-shell-true.subprocess-shell-true
      |
  E501 Line too long (116 > 100)
     --> orch/test_runner.py:338:101
      |
  336 |                 proc = subprocess.Popen(  # nosemgrep: python.lang.security.audit.subprocess-shell-true.subprocess-shell-true
  337 |                     agent_command,
  338 |                     shell=True,  # nosemgrep: python.lang.security.audit.subprocess-shell-true.subprocess-shell-true
      |                                                                                                     ^^^^^^^^^^^^^^^^
  339 |                     cwd=execution_dir,
  ...(4 lines omitted)...
      |
  392 |             with Path(log_path).open("a") as log_file:
  393 |                 log_file.write(f"\n\n{'=' * 60}\nFINAL VERIFICATION RUN\n{'=' * 60}\n")
  394 |                 verify_proc = subprocess.run(  # nosemgrep: python.lang.security.audit.subprocess-shell-true.subprocess-shell-true
      |                                                                                                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  395 |                     command,
  396 |                     shell=True,  # nosemgrep: python.lang.security.audit.subprocess-shell-true.subprocess-shell-true
      |
  E501 Line too long (116 > 100)
     --> orch/test_runner.py:396:101
      |
  394 |                 verify_proc = subprocess.run(  # nosemgrep: python.lang.security.audit.subprocess-shell-true.subprocess-shell-true
  395 |                     command,
  396 |                     shell=True,  # nosemgrep: python.lang.security.audit.subprocess-shell-true.subprocess-shell-true
      |                                                                                                     ^^^^^^^^^^^^^^^^
  397 |                     cwd=execution_dir,
  398 |                     stdout=log_file,
      |
  E501 Line too long (108 > 100)
     --> orch/test_runner.py:641:101
      |
  639 |     """
  640 |     with contextlib.suppress(Exception):
  641 |         subprocess.run(  # nosemgrep: python.lang.security.audit.subprocess-shell-true.subprocess-shell-true
      |                                                                                                     ^^^^^^^^
  642 |             command,
  643 |             shell=True,  # nosemgrep: python.lang.security.audit.subprocess-shell-true.subprocess-shell-true
      |
  E501 Line too long (108 > 100)
     --> orch/test_runner.py:643:101
      |
  641 |         subprocess.run(  # nosemgrep: python.lang.security.audit.subprocess-shell-true.subprocess-shell-true
  642 |             command,
  643 |             shell=True,  # nosemgrep: python.lang.security.audit.subprocess-shell-true.subprocess-shell-true
      |                                                                                                     ^^^^^^^^
  644 |             cwd=cwd,
  645 |             capture_output=True,
      |
  Found 8 errors.
  make: *** [Makefile:22: lint] Error 1


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
