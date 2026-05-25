# I-00111 S03 Tests — Step Report

## Summary

Added the regression test net for I-00111 (AC2) and removed the schemathesis
`openapi()` workaround (AC3). Both targeted verification runs exited 0.

## Files Changed

| File | Change |
|------|--------|
| `tests/dashboard/test_openapi_schema.py` | **Created** — new regression test file with 2 tests |
| `tests/dashboard/test_schemathesis_contract.py` | **Modified** — workaround removed, docstring updated, fixture docstring updated |

## Details

### 1. `tests/dashboard/test_openapi_schema.py` (new)

Two regression tests for AC2:

**`test_i_00111_openapi_endpoint_returns_valid_schema`**
- Uses a `client` fixture that mirrors the pattern in every other
  `tests/dashboard/` test (pops `IW_CORE_EXPECTED_INSTANCE_ID`, overrides
  `get_db` with the testcontainer session, yields a `TestClient`).
- Calls `client.get("/openapi.json")` and asserts status 200 with a diagnostic
  failure message that quotes the response body (so a 500-regression shows
  the Pydantic traceback).
- Semantic assertions (PT018-compliant, split per check):
  - `"openapi"` key exists AND value starts with `"3."`
  - `"info"` key exists AND `info.title` is non-empty
  - `"paths"` key exists AND `len(paths) > 0`

**`test_i_00111_app_openapi_callable_returns_dict`**
- No fixture — purely in-process.
- Lazily imports `dashboard.app.create_app` inside the function (live-DB guard
  bypass via `os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID")`).
- Calls `app.openapi()` and asserts: `isinstance(dict)`, `"paths"` key exists,
  `len(paths) > 0` — all with diagnostic failure messages.

Module docstring names I-00111 and explains the regression net contract
(pre-fix: `ForwardRef('Response')` error; post-fix: valid OpenAPI 3.x dict).

### 2. `tests/dashboard/test_schemathesis_contract.py` (modified — AC3)

Three edits:

**Edit 2.1 — Workaround removed (`contract_app` fixture, former lines 163-173):**
- Deleted: `from fastapi.openapi.utils import get_openapi` import
- Deleted: `json_api_path_set`, `json_api_routes`, `_json_api_openapi()` closure
- Deleted: `monkeypatch.setattr(app, "openapi", _json_api_openapi, raising=False)`
- Fixture now `yield app` directly after `app.dependency_overrides[get_db] = …`
- Updated fixture docstring: "No `openapi()` override is needed — I-00111 fixed
  the underlying Pydantic ForwardRef resolution error."

**Edit 2.2 — `contract_schema` fixture docstring updated:**
- Old: "Load the app's OpenAPI schema (built from the JSON_API_PATHS routes)"
- New: "Load the app's full OpenAPI schema (I-00111 restored full-app schema
  generation; the JSON_API_FUZZ_PATHS filter narrows the fuzz target downstream)"

**Edit 2.3 — Module docstring at lines 21-30 updated:**
- Replaced "OpenAPI generation work-around" section with the I-00111 fix note
  (full-app schema now generated cleanly; no production override needed).

**`Any` import retained:** The `from typing import TYPE_CHECKING, Any` at line 51
is still needed because the module uses `Any` in fixture return annotations and
in the `schema = schemathesis.pytest.from_fixture(...)` line — so no additional
cleanup was needed.

## Test Results

```
$ uv run pytest tests/dashboard/test_openapi_schema.py -v --no-cov
tests/dashboard/test_openapi_schema.py::test_i_00111_app_openapi_callable_returns_dict PASSED
tests/dashboard/test_openapi_schema.py::test_i_00111_openapi_endpoint_returns_valid_schema PASSED
============================== 2 passed in 6.89s ===============================

$ uv run pytest tests/dashboard/test_schemathesis_contract.py::test_json_api_paths_exist_in_schema -v --no-cov -m contract_fuzz
tests/dashboard/test_schemathesis_contract.py::test_json_api_paths_exist_in_schema PASSED
============================== 1 passed in 7.06s ===============================
```

## Preflight Quality Gates

| Gate | Result |
|------|--------|
| `make format` | ok — all 891 files formatted |
| `make typecheck` | ok — Success: no issues found in 276 source files |
| `make lint` | ok — All checks passed |

## TDD Retroactive RED Evidence

Per CR-00072 and the S01 report, `create_app().openapi()` pre-fix raised:
```
pydantic.errors.PydanticUserError: `TypeAdapter[typing.Annotated[ForwardRef('Response'), …]]`
is not fully defined; you should define … then call `.rebuild()` on the instance.
```
`test_i_00111_app_openapi_callable_returns_dict` calls `app.openapi()` directly
as its first action after `create_app()`. Against pre-fix code, this would raise
before the first assertion, satisfying RED-first semantics retroactively. The test
was not run against reverted code (S01 report provides the canonical RED evidence).

## Notes

- The `_json_api_openapi` workaround and its `monkeypatch.setattr` are
  completely gone from `contract_app`. The fixture body is now simpler and
  clearly documents its intent.
- `Any` is still imported at module level in `test_schemathesis_contract.py`
  (line 51) because it is used in the `contract_schema` fixture return annotation
  and the `schema = schemathesis.pytest.from_fixture(...)` variable assignment.
  No `from typing import TYPE_CHECKING` change is needed since `Any` is a
  runtime-available type — it is only needed in `TYPE_CHECKING` when you want
  to avoid circular import side-effects at type-checking time.
- No changes were made to `JSON_API_PATHS`, `KNOWN_CONTRACT_5XX`, or
  `JSON_API_FUZZ_PATHS` — these are intentionally narrow and unchanged by
  this incident.
- Both new tests are under `tests/dashboard/` (required for the `client`
  fixture) and use PT018-compliant split assertions.