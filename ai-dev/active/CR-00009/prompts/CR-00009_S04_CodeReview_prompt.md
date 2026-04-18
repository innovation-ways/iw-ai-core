# CR-00009_S04_CodeReview_prompt

**Work Item**: CR-00009 — Chat panel context awareness
**Step Being Reviewed**: S03 (api-impl)
**Review Step**: S04

---

## Input Files

- `ai-dev/active/CR-00009/CR-00009_CR_Design.md`
- `ai-dev/active/CR-00009/reports/CR-00009_S03_Api_report.md`
- All files listed in the S03 report's `files_changed` (expected: `dashboard/routers/code_qa.py`)

## Output Files

- `ai-dev/active/CR-00009/reports/CR-00009_S04_CodeReview_report.md`

## Context

Review S03 (api-impl) wiring of `module_name` into `QARequest` and the `/code/qa` endpoint.

## Review Checklist

### 1. Contract

- Is `module_name` declared `str | None = None`, positioned right after `module_path`?
- Is the field name `module_name` (not `moduleName`, not `module`)? Match the rest of the schema.
- Is it forwarded to `QAEngine.answer_stream` as a kwarg with the same name?
- Does POSTing without `module_name` still return 200 (AC7)? Confirm with an integration test or a manual pytest.

### 2. Architecture

- Routers stay thin. No module lookups, no DB joins, no business logic in the router. If S03 added any logic beyond field declaration + forwarding, that's a HIGH finding.

### 3. Security & Validation

- `module_name` is untrusted user input flowing into a system prompt. Is it being injected raw? That's acceptable for a prompt (not a SQL or shell context), but only at the prompt-construction boundary — NOT into LanceDB queries or file paths. Verify it isn't used as a filter value anywhere in the new code.
- No changes to auth dependency wiring.

### 4. Conventions

- Read `dashboard/CLAUDE.md`. Pydantic style matches the file.
- `uv run ruff check` and `mypy` pass on the file.

### 5. Testing

- Integration test (if S03 added one): does it actually assert `module_name` reaches the engine call? A test that just returns 200 is not enough — the spy/mock must confirm the forwarded kwarg.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit`
2. `make test-integration` if the router test file was touched
3. `uv run ruff check dashboard/routers/code_qa.py`
4. `uv run mypy dashboard/routers/code_qa.py`

## Severity Levels

Standard. Any broken contract (renamed field, missing forward) is HIGH. A Pydantic config mistake that makes POST without `module_name` fail validation is CRITICAL.

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "CR-00009",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
