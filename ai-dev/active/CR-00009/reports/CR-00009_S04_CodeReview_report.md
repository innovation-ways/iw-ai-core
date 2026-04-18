# CR-00009 S04 Code Review Report

## What was reviewed

S03 (api-impl) added `module_name: str | None` to `QARequest` and threaded it through to `QAEngine.answer_stream` in `dashboard/routers/code_qa.py`.

## Files changed

- `dashboard/routers/code_qa.py`

## Review findings

### Contract ✅

| Check | Result |
|-------|--------|
| `module_name` declared `str \| None = None` | ✅ Line 43, right after `module_path` |
| Field name `module_name` (not `moduleName` or `module`) | ✅ Consistent |
| Forwarded to `engine.answer_stream` as kwarg | ✅ Line 98: `module_name=module_name` |
| POST without `module_name` returns 200 (AC7) | ✅ Pydantic defaults to `None`; no validation change |

### Architecture ✅

Router is thin. No module lookups, no DB joins, no business logic — only field declaration and forwarding to the engine.

### Security ✅

`module_name` is forwarded to `QAEngine.answer_stream` as a kwarg. In `orch/rag/qa.py:_build_system_prompt` (line 153–156), it is only injected into the system prompt string at the prompt-construction boundary. It is not used as a filter value for LanceDB queries or in file paths. No auth changes.

### Conventions ✅

Pydantic style matches existing file conventions (use of `Field(...)`, `str \| None`, field ordering). Read `dashboard/CLAUDE.md` — router stays thin per conventions.

### Test verification

| Command | Result |
|---------|--------|
| `make test-unit` | 795 passed, 0 failed |
| `make test-integration` | 8 passed, 0 failed |
| `uv run ruff check dashboard/routers/code_qa.py` | All checks passed |
| `uv run mypy dashboard/routers/code_qa.py` | Success: no issues found |

## Verdict

**pass**

## Mandatory fix count

0

## Notes

S03 is a clean implementation. The router correctly adds the optional field, forwards it as a kwarg, and introduces no business logic. AC7 is satisfied by the Pydantic default — no test was added in S03 to explicitly verify `module_name=None` returns 200, but the integration test suite confirms existing callers (which omit `module_name`) work without regression. The S07 tests-impl agent will add a spy-based test asserting `module_name` reaches the engine call, per the TDD note in S03.
