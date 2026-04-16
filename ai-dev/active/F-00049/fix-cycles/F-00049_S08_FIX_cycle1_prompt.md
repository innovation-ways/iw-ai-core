# F-00049 S08 QV Fix Cycle 1/5

Quality gate S08 for work item F-00049 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: Lint error: S108 insecure temp path in tests/unit/test_qa_engine.py:148

**Command output**:
```
[93m[1m! [0m agent "QvGate" not found. Falling back to default agent
[0m
> build · MiniMax-M2.7
[0m
[0m$ [0muv run iw step-start F-00049 --step S08
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Started F-00049 step S08 (already in progress)
[0m
[0m$ [0muv run ruff check .
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
S108 Probable insecure usage of temporary file or directory: "/tmp/lancedb"
   --> tests/unit/test_qa_engine.py:148:29
    |
146 |         config.resolved_llm_model.return_value = "gemma4:26b"
147 |         config.ollama_url = "http://localhost:11434"
148 |         config.index_path = "/tmp/lancedb"
    |                             ^^^^^^^^^^^^^^
149 |         return config
    |

Found 1 error.
[0m
**FAIL** - Exit code: 1

```
S108 Probable insecure usage of temporary file or directory: "/tmp/lancedb"
   --> tests/unit/test_qa_engine.py:148:29
```

Now I'll write the report and call step-fail:
[0m← [0mWrite ai-dev/active/F-00049/reports/F-00049_S08_QvGate_report.md
Wrote file successfully.
[0m
[0m$ [0muv run iw step-fail F-00049 --step S08 --reason "Lint error: S108 insecure temp path in tests/unit/test_qa_engine.py:148"
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Failed F-00049 step S08: Lint error: S108 insecure temp path in tests/unit/test_qa_engine.py:148
[0m
**FAIL** - Lint error found:

```
S108 Probable insecure usage of temporary file or directory: "/tmp/lancedb"
   --> tests/unit/test_qa_engine.py:148:29
```

Step S08 marked as **FAILED** with reason: `Lint error: S108 insecure temp path in tests/unit/test_qa_engine.py:148`

```

## Constraints

1. **Only fix the reported errors.** Do not refactor unrelated code.
2. **Preserve existing behavior.** Fixes must not break working functionality.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. **Run the gate command after every fix** to verify resolution.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
