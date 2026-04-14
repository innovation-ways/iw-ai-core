# F-00041 S05 QV Fix Cycle 1/5

Quality gate S05 for work item F-00041 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: 5 lint errors: 2x E501 line length, 1x B904 bare raise, 2x ERA001 commented-out code in test file

**Command output**:
```
...(truncated)...
"doc-9",
261 |         content="# Test Doc\n\n## Purpose\nSome purpose content.\n\n## Architecture\nArchitecture details.",
    |                                                                                                     ^^^^^^^^
262 |     )
    |

ERA001 Found commented-out code
   --> tests/integration/api/test_docs_ide_api.py:287:1
    |
286 | # ---------------------------------------------------------------------------
287 | # POST /project/{id}/api/docs/{doc_id}/guide/sections/{section_name}
    | ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
288 | # ---------------------------------------------------------------------------
    |
help: Remove commented-out code

ERA001 Found commented-out code
   --> tests/integration/api/test_docs_ide_api.py:341:1
    |
340 | # ---------------------------------------------------------------------------
341 | # DELETE /project/{id}/api/docs/{doc_id}/guide/sections/{section_name}
    | ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
342 | # ---------------------------------------------------------------------------
    |
help: Remove commented-out code

Found 5 errors.
[0m
There are 5 linting errors to fix. Let me address them:
[0m→ [0mRead dashboard/routers/docs.py[90m [limit=12, offset=120][0m
[0m✗ [0mread failed
[91m[1mError: [0mFile not found: /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00041/tests/integration/api/test_docs_ide_api.py
[0m
[0m$ [0mcd /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00041 && git status --short tests/
[0m→ [0mRead tests/integration/test_docs_routes.py[90m [limit=30, offset=255][0m
[0m
[0m$ [0mmkdir -p /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00041/ai-dev/active/F-00041/reports
[0m
[0m← [0mWrite ai-dev/active/F-00041/reports/F-00041_S05_QvGate_report.md
Wrote file successfully.
[0m
[0m$ [0muv run iw step-fail F-00041 --step S05 --reason "5 lint errors: 2x E501 line length, 1x B904 bare raise, 2x ERA001 commented-out code in test file"
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Failed F-00041 step S05: 5 lint errors: 2x E501 line length, 1x B904 bare raise, 2x ERA001 commented-out code in test file
[0m
**S05 failed** — `ruff check` found 5 errors:

- `E501` (line too long) × 2 — in `dashboard/routers/docs.py:124` (pre-existing PDF inline CSS) and `test_docs_ide_api.py:261`
- `B904` (bare raise) — in `dashboard/routers/docs.py:172` (pre-existing WeasyPrint exception)  
- `ERA001` (commented-out code) × 2 — in `test_docs_ide_api.py:287,341`

The test file `tests/integration/api/test_docs_ide_api.py` is in the parent repo but not in the worktree. Two blocks of section guide POST/DELETE tests are commented out (ERA001). Report written to `ai-dev/active/F-00041/reports/F-00041_S05_QvGate_report.md`.

```

## Constraints

1. **Only fix the reported errors.** Do not refactor unrelated code.
2. **Preserve existing behavior.** Fixes must not break working functionality.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. **Run the gate command after every fix** to verify resolution.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
