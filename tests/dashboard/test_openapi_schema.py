"""I-00111 regression — ``GET /openapi.json`` must return a valid OpenAPI schema.

Pre-fix, ``create_app().openapi()`` raised a Pydantic ``ForwardRef('Response')``
resolution error (a route handler in ``dashboard/app.py`` returned ``-> Response``
but the import was only inside ``if TYPE_CHECKING:``). The result was HTTP 500
app-wide on ``GET /openapi.json`` and a broken Swagger UI (``GET /docs``).

This test is the regression net: it verifies the fix is in place and will catch
any future re-introduction of the same class of bug (ForwardRef resolution failure
in a route return annotation or response model).

AC2 contract (I-00111): two tests must pass:
  1. ``test_i_00111_openapi_endpoint_returns_valid_schema``  — HTTP-level
  2. ``test_i_00111_app_openapi_callable_returns_dict``     — in-process
"""

from __future__ import annotations

import os
from collections.abc import Generator
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from dashboard.dependencies import get_db

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """Create a TestClient wired to the testcontainer DB.

    Mirrors the pattern used by every other test under tests/dashboard/ that
    exercises FastAPI routes: pops ``IW_CORE_EXPECTED_INSTANCE_ID`` so the DB
    identity check does not fire, overrides ``get_db`` with the seeded test
    session, then yields a ``TestClient``.
    """
    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    try:
        # Lazy import keeps the live-DB guard (test-mode plumbing in
        # tests/dashboard/conftest.py) in effect when create_app() runs.
        from dashboard.app import create_app  # noqa: PLC0415

        def override_get_db() -> Session:
            return db_session

        app = create_app()
        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c
    finally:
        if original is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original
        app.dependency_overrides.clear()


def test_i_00111_openapi_endpoint_returns_valid_schema(client: TestClient) -> None:
    """GET /openapi.json must return HTTP 200 with a valid OpenAPI envelope.

    Pre-I-00111 this returned HTTP 500 from a Pydantic ForwardRef('Response')
    error. Post-fix the route returns 200 with a real OpenAPI 3.x document.
    """
    response = client.get("/openapi.json")
    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}. "
        f"Pre-I-00111 this was 500 from a Pydantic ForwardRef('Response') error. "
        f"Body: {response.text[:500]}"
    )
    schema = response.json()
    # Semantic asserts — not just shape. Each check verifies the schema has
    # real, non-empty content (shape-only checks pass vacuously against a
    # partial/stub schema).
    assert "openapi" in schema, f'Key "openapi" absent from schema: {list(schema.keys())}'
    assert schema["openapi"].startswith("3."), schema["openapi"]
    assert "info" in schema, f'Key "info" absent from schema: {list(schema.keys())}'
    assert schema["info"].get("title"), f"OpenAPI info block has no title: {schema.get('info')}"
    assert "paths" in schema, f'Key "paths" absent from schema: {list(schema.keys())}'
    assert len(schema["paths"]) > 0, (
        "OpenAPI 'paths' is empty — the schema generator silently produced a "
        "stub; the fix must restore real route coverage."
    )


def test_i_00111_app_openapi_callable_returns_dict() -> None:
    """In-process: ``create_app().openapi()`` must return a dict, not raise.

    This is the lowest-level reproduction of the bug — calling .openapi()
    on a freshly-built app, without going through HTTP. Pre-fix this raised
    ``pydantic.errors.PydanticUndefinedAnnotation`` from inside FastAPI's
    schema generation.  Post-fix it returns a populated dict.
    """
    # Lazy import inside the function body keeps the live-DB guard in effect
    # when create_app() runs (tests/dashboard/conftest.py test-mode plumbing).
    from dashboard.app import create_app

    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    try:
        app = create_app()
        schema = app.openapi()
    finally:
        if original is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original

    assert isinstance(schema, dict), type(schema)
    assert "paths" in schema, f'Key "paths" absent from schema: {list(schema.keys())}'
    assert len(schema["paths"]) > 0, (
        f"OpenAPI schema returned a dict but 'paths' is empty. Schema keys: {list(schema.keys())}"
    )
    # Semantic asserts: openapi version and info.title (shape-only checks
    # pass vacuously against a partial/stub schema).
    assert "openapi" in schema, f'Key "openapi" absent from schema: {list(schema.keys())}'
    assert schema["openapi"].startswith("3."), schema["openapi"]
    assert "info" in schema, f'Key "info" absent from schema: {list(schema.keys())}'
    assert schema["info"].get("title"), f"OpenAPI info block has no title: {schema.get('info')}"
