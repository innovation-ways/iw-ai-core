# I-00074 S06 QV Fix Cycle 3/3

Quality gate S06 for work item I-00074 failed. Fix the issues below so the gate passes on re-run.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00074/ai-dev/active/I-00074/I-00074_Issue_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Errors to Address

The block below is **one hypothesis** generated from the failed gate. Verify it against the design doc spec above before applying any fix; the spec wins on conflict.

**Error**: lint failed: exit=2

**Unparseable output** (always surfaces):
  uv run python scripts/check_templates.py
  uv run ruff check .
  E501 Line too long (117 > 100)
     --> tests/dashboard/test_docs_pdf_chromium.py:99:101
      |
   97 |         doc_type=DocType.architecture,
   98 |         status=DocStatus.published,
   99 |         content="# Hello\n\nSome text with a Mermaid diagram:\n\n```mermaid\ngraph TD\n    A[Start] --> B[End]\n```",
      |                                                                                                     ^^^^^^^^^^^^^^^^^
  100 |         version=1,
  101 |     )
      |
  W292 [*] No newline at end of file
     --> tests/dashboard/test_docs_pdf_chromium.py:276:26
      |
  275 |     fn = _make_render_pdf_fn()
  276 |     assert fn is expected
      |                          ^
      |
  help: Add trailing newline
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


**ESCALATION**: This is the FINAL fix cycle (3/3). **PREFER honest escalation over a Hail-Mary fix that drifts from the design spec.** If you cannot resolve every issue while staying aligned with the design doc, document which issues remain and why — the human reviewer can act on the evidence.

**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
