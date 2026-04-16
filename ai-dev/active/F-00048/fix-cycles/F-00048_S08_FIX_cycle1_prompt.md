# F-00048 S08 QV Fix Cycle 1/5

Quality gate S08 for work item F-00048 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: Lint check failed with 8 errors (7 fixable). Files: tests/integration/test_code_module_routes.py, tests/integration/test_module_gen_integration.py, tests/unit/test_module_parser.py

**Command output**:
```
...(truncated)...
om orch.db.models import DocTier, DocType, EditorialCategory, ProjectDoc
   |                                             ^^^^^^^
79 |         from orch.rag.config import CodeUnderstandingConfig
80 |         from orch.rag.module_gen import ModuleGenerator
   |
help: Remove unused import

F401 [*] `orch.db.models.EditorialCategory` imported but unused
  --> tests/integration/test_module_gen_integration.py:78:54
   |
76 |     ):
77 |         """Second call returns same doc without regenerating"""
78 |         from orch.db.models import DocTier, DocType, EditorialCategory, ProjectDoc
   |                                                      ^^^^^^^^^^^^^^^^^
79 |         from orch.rag.config import CodeUnderstandingConfig
80 |         from orch.rag.module_gen import ModuleGenerator
   |
help: Remove unused import

F401 [*] `orch.db.models.ProjectDoc` imported but unused
  --> tests/integration/test_module_gen_integration.py:78:73
   |
76 |     ):
77 |         """Second call returns same doc without regenerating"""
78 |         from orch.db.models import DocTier, DocType, EditorialCategory, ProjectDoc
   |                                                                         ^^^^^^^^^^
79 |         from orch.rag.config import CodeUnderstandingConfig
80 |         from orch.rag.module_gen import ModuleGenerator
   |
help: Remove unused import

I001 [*] Import block is un-sorted or un-formatted
 --> tests/unit/test_module_parser.py:6:1
  |
4 |   """
5 |
6 | / from __future__ import annotations
7 | |
8 | | import pytest
  | |_____________^
  |
help: Organize imports

F401 [*] `pytest` imported but unused
 --> tests/unit/test_module_parser.py:8:8
  |
6 | from __future__ import annotations
7 |
8 | import pytest
  |        ^^^^^^
  |
help: Remove unused import: `pytest`

Found 8 errors.
[*] 7 fixable with the `--fix` option (1 hidden fix can be enabled with the `--unsafe-fixes` option).
[0m
FAIL — 8 lint errors found.
[0m$ [0mmkdir -p ai-dev/active/F-00048/reports
[0m
[0m← [0mWrite ai-dev/active/F-00048/reports/F-00048_S08_QvGate_report.md
Wrote file successfully.
[0m
[0m$ [0muv run iw step-fail F-00048 --step S08 --reason "Lint check failed with 8 errors (7 fixable). Files: tests/integration/test_code_module_routes.py, tests/integration/test_module_gen_integration.py, tests/unit/test_module_parser.py"
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Failed F-00048 step S08: Lint check failed with 8 errors (7 fixable). Files: tests/integration/test_code_module_routes.py, tests/integration/test_module_gen_integration.py, tests/unit/test_module_parser.py
[0m
**FAIL** - 8 lint errors found.

Report written to `ai-dev/active/F-00048/reports/F-00048_S08_QvGate_report.md`.

Run `uv run ruff check . --fix` to auto-fix 7 of 8 issues. The TC002 (move import to TYPE_CHECKING block) requires manual fix.

```

## Constraints

1. **Only fix the reported errors.** Do not refactor unrelated code.
2. **Preserve existing behavior.** Fixes must not break working functionality.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. **Run the gate command after every fix** to verify resolution.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
