"""Regression tests for I-00110.

The dashboard's keep-alive slot endpoints previously returned HTTP 500
(psycopg.errors.NumericValueOutOfRange) when handed a slot_id above
2**63 - 1 (the PostgreSQL BIGINT max). FastAPI now bounds the path param
at the route boundary, so out-of-range values surface as HTTP 422.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

BIGINT_MAX = 2**63 - 1
OVERFLOW = BIGINT_MAX + 1  # 9223372036854775808


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """Create a TestClient that overrides get_db to use the test db_session."""
    import os

    # Ensure keep_alive_config row exists before any tests run
    from orch.keep_alive_service import get_config

    get_config(db_session)
    db_session.commit()

    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    try:

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


def test_delete_slot_overflow_returns_422_not_500(client: TestClient) -> None:
    """An out-of-BIGINT slot_id on DELETE must surface as 422, not 500."""
    resp = client.delete(f"/api/keep-alive/slots/{OVERFLOW}")
    assert resp.status_code == 422, resp.text
    # Semantic: response must mention the slot_id parameter and the bound.
    body = resp.json()
    assert "detail" in body
    # FastAPI's standard validation envelope. We assert the parameter
    # name appears so the caller can locate the failing field.
    assert any("slot_id" in str(err.get("loc", ())) for err in body["detail"]), body


def test_toggle_slot_overflow_returns_422_not_500(client: TestClient) -> None:
    """An out-of-BIGINT slot_id on PATCH toggle must surface as 422, not 500."""
    resp = client.patch(f"/api/keep-alive/slots/{OVERFLOW}/toggle")
    assert resp.status_code == 422, resp.text
    body = resp.json()
    assert "detail" in body
    assert any("slot_id" in str(err.get("loc", ())) for err in body["detail"]), body


def test_delete_slot_at_bigint_max_does_not_500(client: TestClient) -> None:
    """The boundary value 2**63 - 1 must NOT be rejected — it's a valid
    BIGINT, just non-existent. Expect 404 (not found) not 422 (validation)."""
    resp = client.delete(f"/api/keep-alive/slots/{BIGINT_MAX}")
    # Either 404 (slot not found) or 200 (if a slot at MAX existed in seed).
    # Critically: NOT 422 and NOT 500.
    assert resp.status_code in (200, 404), resp.text


def test_toggle_slot_at_bigint_max_does_not_500(client: TestClient) -> None:
    """The boundary value 2**63 - 1 must NOT be rejected on toggle either."""
    resp = client.patch(f"/api/keep-alive/slots/{BIGINT_MAX}/toggle")
    assert resp.status_code in (200, 404), resp.text


def test_delete_slot_zero_returns_422(client: TestClient) -> None:
    """slot_id=0 violates the ge=1 lower bound — must be 422."""
    resp = client.delete("/api/keep-alive/slots/0")
    assert resp.status_code == 422, resp.text


def test_toggle_slot_negative_returns_422(client: TestClient) -> None:
    """A negative slot_id violates ge=1 — must be 422."""
    resp = client.patch("/api/keep-alive/slots/-1/toggle")
    assert resp.status_code == 422, resp.text
