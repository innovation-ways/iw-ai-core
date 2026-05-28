# CR-00091 S10 QV Fix Cycle 2/5

Quality gate S10 for work item CR-00091 failed. Fix the issues below so the gate passes on re-run.

## Scope (allowed_paths from workflow-manifest.json)

You MAY only modify files matching these globs:

  scripts/rewrite_down_revision.py
  scripts/resolve_pending_migration.py
  Makefile
  tests/unit/test_rewrite_down_revision.py
  tests/unit/daemon/test_migration_rebase.py
  tests/unit/test_resolve_pending_migration.py
  tests/integration/test_migrations_round_trip.py
  orch/daemon/migration_rebase.py
  CLAUDE.md
  orch/CLAUDE.md
  ai-dev/templates/Implementation_Prompt_Template.md
  skills/iw-new-cr/SKILL.md
  skills/iw-new-feature/SKILL.md
  skills/iw-new-incident/SKILL.md
  .claude/skills/iw-new-cr/SKILL.md
  .claude/skills/iw-new-feature/SKILL.md
  .claude/skills/iw-new-incident/SKILL.md

The following paths are ALSO allowed by daemon convention (do NOT flag them as out-of-scope; the workflow itself writes here):

  ai-dev/active/CR-00091/**
  ai-dev/archive/CR-00091/**
  ai-dev/work/CR-00091/**

Edits to files outside the combined list will block the cycle. If the
failing gate appears to require an out-of-scope edit, do NOT make it —
instead document the required out-of-scope path(s) under "blockers" in
your result contract, and the operator will amend allowed_paths.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00091/ai-dev/active/CR-00091/CR-00091_CR_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Errors to Address

The block below is **one hypothesis** generated from the failed gate. Verify it against the design doc spec above before applying any fix; the spec wins on conflict.

**Error**: Process exited without reporting completion (PID dead)

**Unparseable output** (always surfaces):
  [narration-guard] running: pi -p # CR-00091 S10 QV Fix Cycle 1/5
  Quality gate S10 for work item CR-00091 failed. Fix the issues below so the gate passes on re-run.
  You MAY only modify files matching these globs:
    scripts/rewrite_down_revision.py
    scripts/resolve_pending_migration.py
    Makefile
    tests/unit/test_rewrite_down_revision.py
    tests/unit/daemon/test_migration_rebase.py
    tests/unit/test_resolve_pending_migration.py
    tests/integration/test_migrations_round_trip.py
    orch/daemon/migration_rebase.py
    CLAUDE.md
    orch/CLAUDE.md
    ai-dev/templates/Implementation_Prompt_Template.md
    skills/iw-new-cr/SKILL.md
    skills/iw-new-feature/SKILL.md
    skills/iw-new-incident/SKILL.md
    .claude/skills/iw-new-cr/SKILL.md
    .claude/skills/iw-new-feature/SKILL.md
    .claude/skills/iw-new-incident/SKILL.md
  The following paths are ALSO allowed by daemon convention (do NOT flag them as out-of-scope; the workflow itself writes here):
    ai-dev/active/CR-00091/**
    ai-dev/archive/CR-00091/**
    ai-dev/work/CR-00091/**
  Edits to files outside the combined list will block the cycle. If the
  failing gate appears to require an out-of-scope edit, do NOT make it —
  instead document the required out-of-scope path(s) under "blockers" in
  your result contract, and the operator will amend allowed_paths.
  The design document for this work item is the authoritative spec for the change. Read it before applying any fix:
  - **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00091/ai-dev/active/CR-00091/CR-00091_CR_Design.md`
  - Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**
  The block below is **one hypothesis** generated from the failed gate. Verify it against the design doc spec above before applying any fix; the spec wins on conflict.
  **Error**: unit-tests failed: exit=2
  **New Failures**:
    [test] tests/unit/test_tdd_red_evidence_contract.py::test_template_pair_is_byte_identical[templates/design/Implementation_Prompt_Template.md-ai-dev/templates/Implementation_Prompt_Template.md]
  **Unparseable output** (always surfaces):
    uv run pytest tests/unit/ --cov=orch --cov=dashboard --cov=executor --cov-report=term-missing:skip-covered --cov-report=html:tests/output/coverage/htmlcov --cov-report=xml:tests/output/coverage/coverage.xml --cov-report=json:tests/output/coverage/coverage.json -v
    platform linux -- Python 3.12.3, pytest-9.0.3, pluggy-1.6.0 -- /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00091/.venv/bin/python
    cachedir: .pytest_cache
    benchmark: 4.0.0 (defaults: timer=time.perf_counter disable_gc=False min_rounds=5 min_time=0.000005 max_time=1.0 calibration_precision=10 warmup=False warmup_iterations=100000)
  ...(1 lines omitted)...
  The quality gate that failed runs:
  ```bash
  make test-unit
  ```
  After applying fixes, re-run this command to verify the issues are resolved.
  1. **Read the design doc** at the path above. Skim the section that covers this step's scope; quote-of-the-doc lives in this prompt when available.
  2. **Diff your target file(s) against the spec** — list deviations explicitly before editing.
  3. **Apply the minimum patch** to align code with the spec; the reported errors should resolve as a side effect of that alignment.
  4. **If the errors disagree with the spec, the spec wins.** Note the disagreement in your output rather than silently following the errors.
  1. **Only fix the reported errors.** Do not refactor unrelated code.
  2. **Preserve existing behavior.** Fixes must not break working functionality.
  3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
  4. **Run the gate command after every fix** to verify resolution.
  After your final edit, run these two commands and fix any NEW violation
  your edits introduced:
  ```bash
  make format-check
  make lint
  ```
  If either command reports a violation in a file you touched this cycle,
  resolve it before exiting — `uv run ruff format <file>` for format-check
  failures, targeted edit for lint failures. Re-run both commands to confirm
  green. The next review run WILL fail on these gates and burn another fix
  cycle, so closing them now is strictly cheaper.
  (Diagnosed 2026-05-25: in CR-00082 S04, cycle N reformatted
  `playwright_wrapper.py` while cycle N+1 introduced a new line-length
  violation in the same file; the loop never converged because no fix
  agent self-checked these gates. This gate exists to break that loop.)
  **IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest. --model openai-codex/gpt-5.3-codex --no-context-files --append-system-prompt /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00091/CLAUDE.md --append-system-prompt WORKTREE ISOLATION (IW AI Core): your current working directory is the root of your project and it is a git worktree. Every file you read, write, edit, or run a shell command against MUST stay inside this working directory. Never cd to, read, or write any path outside it. A separate checkout of this same repository may exist at a parent or sibling path on disk; it is NOT your project. Ignore it entirely and use paths relative to your working directory.
  Done — fixed the S10 failure with a minimal in-scope patch.
  - Read design doc: `ai-dev/active/CR-00091/CR-00091_CR_Design.md`
  - Verified deviation causing failure:
    - `ai-dev/templates/Implementation_Prompt_Template.md` was not byte-identical to `templates/design/Implementation_Prompt_Template.md` (extra CR-00091 migration note block in the ai-dev copy).
  - Edited:
    - `ai-dev/templates/Implementation_Prompt_Template.md`
  - Removed the extra inserted migration-note lines so it matches the master template byte-for-byte.
  - `make test-unit` ✅ pass
  - `make format-check` ✅ pass
  - `make lint` ✅ pass
  No blockers.


## Gate Command

The quality gate that failed runs:
```bash
make test-unit
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

## Post-Edit Gate (MANDATORY before exit)

After your final edit, run these two commands and fix any NEW violation
your edits introduced:

```bash
make format-check
make lint
```

If either command reports a violation in a file you touched this cycle,
resolve it before exiting — `uv run ruff format <file>` for format-check
failures, targeted edit for lint failures. Re-run both commands to confirm
green. The next review run WILL fail on these gates and burn another fix
cycle, so closing them now is strictly cheaper.

(Diagnosed 2026-05-25: in CR-00082 S04, cycle N reformatted
`playwright_wrapper.py` while cycle N+1 introduced a new line-length
violation in the same file; the loop never converged because no fix
agent self-checked these gates. This gate exists to break that loop.)



**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
