# I-00077 S08 QV Fix Cycle 1/3

Quality gate S08 for work item I-00077 failed. Fix the issues below so the gate passes on re-run.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00077/ai-dev/active/I-00077/I-00077_Issue_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Errors to Address

The block below is **one hypothesis** generated from the failed gate. Verify it against the design doc spec above before applying any fix; the spec wins on conflict.

**Error**: lint failed: exit=2

**Unparseable output** (always surfaces):
  uv run python scripts/check_templates.py
  uv run ruff check .
  I001 [*] Import block is un-sorted or un-formatted
     --> tests/integration/test_doc_instance_guides.py:126:5
      |
  124 |       _make_doc(db_session, doc_id="unknown-doc", doc_type=DocType.module)
  125 |
  126 | /     from sqlalchemy import delete
  127 | |     from orch.db.models import DocTypeGuide
      | |___________________________________________^
  128 |       db_session.execute(delete(DocTypeGuide))
  129 |       db_session.commit()
      |
  help: Organize imports
  E501 Line too long (103 > 100)
     --> tests/integration/test_doc_instance_guides.py:140:101
      |
  139 | def test_falls_back_to_default_guide_when_no_instance_or_type_guide(db_session: Session) -> None:
  140 |     """When no instance guide and no type guide but _default exists, snapshot is the _default guide."""
      |                                                                                                     ^^^
  141 |     _make_project(db_session)
  142 |     _make_doc(db_session, doc_id="diagram-doc", doc_type=DocType.module)
      |
  Found 2 errors.
  [*] 1 fixable with the `--fix` option.
  make: *** [Makefile:21: lint] Error 1


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
