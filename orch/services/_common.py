"""Common helpers shared across all orch service modules.

Provides :class:`ServiceError` (the canonical error type for the service layer)
and small pure utilities used by multiple service modules (e.g. pagination
limit clamping, project existence validation).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

#: Server-side cap on the ``limit`` parameter for list endpoints.
_LIST_MAX_LIMIT: int = 50


class ServiceError(Exception):
    """Structured error raised by service functions.

    CLI wrappers catch ``ServiceError`` and forward ``message`` + ``code``
    to :func:`orch.cli.utils.output_error` so the user sees the same error
    text whether they call the CLI or an MCP tool.

    Attributes:
        message: Human-readable error description.
        code: Numeric exit / error code matching the CLI ``output_error`` codes.
    """

    def __init__(self, message: str, *, code: int = 1) -> None:
        """Initialise a ServiceError with a message and optional exit code.

        Args:
            message: Human-readable error description.
            code: Numeric exit/error code; defaults to 1 (generic error).
        """
        super().__init__(message)
        self.message: str = message
        self.code: int = code


def clamp_limit(limit: int) -> int:
    """Clamp a pagination limit to the server-side maximum of 50.

    Args:
        limit: Requested page size from the caller.

    Returns:
        ``min(limit, 50)`` — the effective limit to use in the query.
    """
    return min(limit, _LIST_MAX_LIMIT)


def resolve_and_validate_project(session: Session, project_id: str) -> None:
    """Verify that a project row exists in the database.

    Args:
        session: Active SQLAlchemy session.
        project_id: Project identifier to look up.

    Raises:
        ServiceError: With code 1 when no ``Project`` row with the given
            ``project_id`` exists.
    """
    from sqlalchemy import select  # noqa: PLC0415

    from orch.db.models import Project  # noqa: PLC0415

    row = session.execute(select(Project).where(Project.id == project_id)).scalar_one_or_none()
    if row is None:
        raise ServiceError(
            f"Project '{project_id}' not found",
            code=1,
        )
