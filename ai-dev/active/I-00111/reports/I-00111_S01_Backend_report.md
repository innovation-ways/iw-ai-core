# I-00111 S01 Backend — Step Report

## Summary

**Fix applied**: `dashboard/app.py` — moved `starlette.responses.Response` from the `TYPE_CHECKING:` block into a runtime import, placing it alongside the already-runtime `starlette.requests.Request`.

**Root cause**: `dashboard/app.py` had `from __future__ import annotations`, which converts all annotations to string ForwardRefs at parse time. `Response` was imported only inside `if TYPE_CHECKING:`. When FastAPI called `get_typed_return_annotation()` on the `favicon_ico()` handler (whose return annotation is `-> Response`), it resolved the ForwardRef against the module's `__globals__` — but `Response` was absent from the runtime namespace, causing Pydantic schema generation to fail with `ForwardRef('Response') is not fully defined`.

`Request` was already at runtime (correct for middleware callables), so routes that returned `Response` AND imported `Response` at runtime from elsewhere (like `keep_alive.py:50`) worked fine. Only the `favicon_ico()` route in `app.py` — where `Response` was only in `TYPE_CHECKING` — triggered the bug.

## Fault Pattern

**Pattern 3 from the design doc**: `from __future__ import annotations` + `TYPE_CHECKING` import.

Offending location: `dashboard/app.py:479` — the `favicon_ico()` handler with `-> Response` return annotation, but `Response` was only imported under `TYPE_CHECKING`.

## Reproduction (pre-fix)

```
$ IW_CORE_OPERATOR_APPLY=true uv run python -c 'from dashboard.app import create_app; create_app().openapi()'
Traceback (most recent call last):
  File "<string>", line 1, in <module>
  File "...fastapi/applications.py", line 1087, in openapi
    self.openapi_schema = get_openapi(...)
  File "...fastapi/openapi/utils.py", line 552, in get_definitions
    field_mapping, definitions = schema_generator.generate_definitions(inputs=inputs)
  File "...pydantic/json_schema.py", line 379, in generate_definitions
    self.generate_inner(schema)
  File "...pydantic/json_schema.py", line 459, in generate_inner
    if 'ref' in schema:
  File "...pydantic/_internal/_mock_val_ser.py", line 41, in __getitem__
    return self._get_built().__getitem__(key)
  File "...pydantic/_internal/_mock_val_ser.py", line 58, in _get_built
    raise PydanticUserError(
        "`TypeAdapter[typing.Annotated[ForwardRef('Response'), FieldInfo(annotation=NoneType, required=True)]]` "
        "is not fully defined; you should define ... then call `.rebuild()` on the instance."
    )
pydantic.errors.PydanticUserError: `TypeAdapter[typing.Annotated[ForwardRef('Response'), FieldInfo(annotation=NoneType, required=True)]]` is not fully defined ...
```

**In-process trace bisect confirmed** the offending route: `/favicon.ico {'GET'}` with `return_annotation: ForwardRef('Response')` and `response_model: ForwardRef('Response')`.

## Fix

**File**: `dashboard/app.py`  
**Lines changed**: 1 (moved `from starlette.responses import Response` from `TYPE_CHECKING:` block to a runtime import below `from fastapi import FastAPI`)

```diff
 if TYPE_CHECKING:
     from collections.abc import AsyncIterator, Awaitable, Callable
     from sqlalchemy.orm import Session
     from starlette.requests import Request  # noqa: TC002
-    from starlette.responses import Response  # noqa: TC002

 from fastapi import FastAPI
+from starlette.requests import Request  # noqa: TC002
+from starlette.responses import Response  # noqa: TC002
```

`Request` was already at runtime (correct for middleware `call_next` signatures); `Response` now joins it, resolving the ForwardRef at `get_typed_return_annotation()` call time.

## Post-fix Verification

```
$ IW_CORE_OPERATOR_APPLY=true uv run python -c 'from dashboard.app import create_app; app = create_app(); s = app.openapi(); assert "paths" in s and len(s["paths"]) > 0; print("OK:", len(s["paths"]), "paths")'
OK: 232 paths

$ IW_CORE_OPERATOR_APPLY=true uv run python -c 'from fastapi.testclient import TestClient; from dashboard.app import create_app; r = TestClient(create_app()).get("/openapi.json"); print("status:", r.status_code, "paths:", len(r.json().get("paths", {}))); assert r.status_code == 200'
status: 200 paths: 232
```

Both probes return HTTP 200 with 232 OpenAPI paths.

## Preflight Quality Gates

| Gate | Result |
|------|--------|
| `make format` | ok — 890 files already formatted |
| `make typecheck` | ok — Success: no issues found in 276 source files |
| `make lint` | ok — All checks passed |

## Files Changed

| File | Change |
|------|--------|
| `dashboard/app.py` | Moved `from starlette.responses import Response` from `TYPE_CHECKING:` to runtime import (1 line moved) |

## Notes

- The `favicon_ico()` route was the only handler in `app.py` using `-> Response`; all other routes return actual content types (HTMLResponse, JSONResponse, etc.) or are plain. Moving `Response` to runtime is the minimal fix — it matches the pre-existing pattern for `Request` and has zero behavioral impact on the route.
- S03 (Tests agent) owns the regression test file `tests/dashboard/test_openapi_schema.py` and the removal of the schemathesis workaround. This step does not touch test files.
