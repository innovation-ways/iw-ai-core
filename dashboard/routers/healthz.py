"""Health check endpoints — CR-00014 identity probe."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Response, status

from dashboard.dependencies import get_db
from orch.db.identity import check_identity

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

router = APIRouter(prefix="/healthz", tags=["health"])


@router.get("/identity")
def identity_check(
    response: Response,
    session: Session = Depends(get_db),
) -> dict[str, str | bool | None]:
    status_info = check_identity(session)

    payload = {
        "expected": str(status_info.expected) if status_info.expected else None,
        "actual": str(status_info.actual) if status_info.actual else None,
        "mode": status_info.mode,
        "match": status_info.mode == "match",
    }

    if status_info.mode in ("mismatch", "missing"):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return payload
