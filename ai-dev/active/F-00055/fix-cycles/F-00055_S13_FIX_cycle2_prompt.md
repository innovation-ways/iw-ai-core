# F-00055 S13 QV Fix Cycle 2/5

Quality gate S13 for work item F-00055 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: Lint gate failed with 48 errors

**Command output**:
```
...(truncated)...
s assigned to but never used
   --> tests/unit/test_f00055_boundaries.py:473:9
    |
471 |                 self.created_at = datetime(2025, 1, 1, tzinfo=UTC)
472 |
473 |         mock_wi = MockWorkItem()
    |         ^^^^^^^
474 |
475 |         async def mock_answer_stream_v2_error(**kwargs: object):
    |
help: Remove assignment to unused variable `mock_wi`

S108 Probable insecure usage of temporary file or directory: "/tmp/test-index"
  --> tests/unit/test_qa_engine_phase_events.py:25:29
   |
23 |         config.resolved_llm_model.return_value = "gemma4:26b"
24 |         config.ollama_url = "http://localhost:11434"
25 |         config.index_path = "/tmp/test-index"
   |                             ^^^^^^^^^^^^^^^^^
26 |         return config
   |

S108 Probable insecure usage of temporary file or directory: "/tmp/test-index"
  --> tests/unit/test_qa_engine_render_cache.py:33:29
   |
31 |         config.resolved_llm_model.return_value = "gemma4:26b"
32 |         config.ollama_url = "http://localhost:11434"
33 |         config.index_path = "/tmp/test-index"
   |                             ^^^^^^^^^^^^^^^^^
34 |         return config
   |

Found 48 errors.
No fixes available (29 hidden fixes can be enabled with the `--unsafe-fixes` option).
[0m
**FAIL** - 48 lint errors found.

Key issues:
- `PTH123`: `open()` should be replaced by `Path.open()` (scripts/regen_eval_set_f00055.py)
- `T201`: `print` statements in scripts/regen_eval_set_f00055.py
- `TC003`/`TC002`: Type-checking imports should be moved into `TYPE_CHECKING` blocks (tests/integration/)
- `F841`: Unused variable assignments across multiple test files
- `E501`: Line length violations
- `S108`: Insecure temp file usage (`/tmp/test-index`)
- `PT006`: Wrong type in `pytest.mark.parametrize`
[0m$ [0mmkdir -p ai-dev/active/F-00055/reports
[0m✗ [0mwrite failed
[91m[1mError: [0mYou must read file /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00055/ai-dev/active/F-00055/reports/F-00055_S13_QvGate_report.md before overwriting it. Use the Read tool first
[0m→ [0mRead ai-dev/active/F-00055/reports/F-00055_S13_QvGate_report.md
[0m
[0m← [0mWrite ai-dev/active/F-00055/reports/F-00055_S13_QvGate_report.md
Wrote file successfully.
[0m
[0m$ [0muv run iw step-fail F-00055 --step S13 --reason "Lint gate failed with 48 errors"
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Failed F-00055 step S13: Lint gate failed with 48 errors
[0m
**FAIL** — Lint gate found 48 errors across 11 files.

Key issues: line too long (15), unused variables (8), type-checking imports (15), insecure temp file usage (7), print statements (4), Path.open() usage (2), missing stacklevel (1), pytest.mark.parametrize (2), unnecessary assignment (1).

Report written to `ai-dev/active/F-00055/reports/F-00055_S13_QvGate_report.md`. Step marked as failed.

```

## Constraints

1. **Only fix the reported errors.** Do not refactor unrelated code.
2. **Preserve existing behavior.** Fixes must not break working functionality.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. **Run the gate command after every fix** to verify resolution.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
