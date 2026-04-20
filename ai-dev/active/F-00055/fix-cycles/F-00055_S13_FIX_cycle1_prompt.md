# F-00055 S13 QV Fix Cycle 1/5

Quality gate S13 for work item F-00055 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: 48 lint errors found by ruff

**Command output**:
```
...(truncated)...
, i, tzinfo=UTC)) for i in range(1, 12)]
    |
help: Remove assignment to unused variable `now`

S108 Probable insecure usage of temporary file or directory: "/tmp/test-index"
   --> tests/unit/test_f00055_boundaries.py:460:34
    |
458 |         mock_config.resolved_llm_model.return_value = "gemma4:26b"
459 |         mock_config.ollama_url = "http://localhost:11434"
460 |         mock_config.index_path = "/tmp/test-index"
    |                                  ^^^^^^^^^^^^^^^^^
461 |
462 |         engine = QAEngine(project_id="test-project", config=mock_config)
    |

F841 Local variable `mock_wi` is assigned to but never used
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
[0m$ [0mmkdir -p ai-dev/active/F-00055/reports
[0m
[0m← [0mWrite ai-dev/active/F-00055/reports/F-00055_S13_QvGate_report.md
Wrote file successfully.
[0m
[0m$ [0muv run iw step-fail F-00055 --step S13 --reason "48 lint errors found by ruff"
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Failed F-00055 step S13: 48 lint errors found by ruff
[0m
**FAIL** — `uv run ruff check .` found **48 errors** across 11 files.

Key issues:
- **11** line length violations (E501)
- **8** unused variables (F841)  
- **7** insecure temp file paths (S108)
- **15** type-checking imports (TC002/TC003) that should be behind `TYPE_CHECKING`
- **4** print statements (T201) that should use logging
- **2** `open()` should use `Path.open()`

Most errors can be auto-fixed with `uv run ruff check . --unsafe-fixes`, but manual review needed for unused variables, line lengths, and temp file patterns. Report written to `ai-dev/active/F-00055/reports/F-00055_S13_QvGate_report.md`.

```

## Constraints

1. **Only fix the reported errors.** Do not refactor unrelated code.
2. **Preserve existing behavior.** Fixes must not break working functionality.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. **Run the gate command after every fix** to verify resolution.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
