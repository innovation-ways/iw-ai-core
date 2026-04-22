"""DB instance-identity verification — CR-00014.

Public API:
    get_live_instance_id(session)    -> uuid.UUID | None
    get_expected_instance_id()         -> uuid.UUID | None
    check_identity(session)             -> IdentityStatus
    verify_instance_identity(session)  -> IdentityStatus  (raises on mismatch/missing)
"""

from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

ENV_VAR = "IW_CORE_EXPECTED_INSTANCE_ID"


class InstanceMismatchError(RuntimeError):
    """Raised when the live DB instance_id does not match the expected value."""


class InstanceRowMissingError(RuntimeError):
    """Raised when the iw_core_instance row is absent and the env var is set."""


@dataclass(frozen=True)
class IdentityStatus:
    expected: uuid.UUID | None
    actual: uuid.UUID | None
    mode: Literal["match", "mismatch", "bootstrap", "missing"]
    message: str


def get_live_instance_id(session: Session) -> uuid.UUID | None:
    """Return the instance_id from iw_core_instance, or None if the row is missing."""
    from orch.db.models import IwCoreInstance

    row = session.get(IwCoreInstance, 1)
    if row is None:
        return None
    return row.instance_id


def get_expected_instance_id() -> uuid.UUID | None:
    """Parse IW_CORE_EXPECTED_INSTANCE_ID env var.

    Returns None if the variable is unset or empty (after whitespace trimming).
    Raises ValueError if the variable is set to a malformed non-empty value.
    """
    raw = os.environ.get(ENV_VAR, "")
    stripped = raw.strip()
    if not stripped:
        return None
    return uuid.UUID(stripped)


def check_identity(session: Session) -> IdentityStatus:
    """Pure function: read both values, classify, return status.

    Does not raise. Always returns an IdentityStatus.
    """
    expected = get_expected_instance_id()
    actual = get_live_instance_id(session)

    if actual is None:
        mode: Literal["match", "mismatch", "bootstrap", "missing"] = "missing"
        if expected is None:
            message = (
                "iw_core_instance row is absent; IW_CORE_EXPECTED_INSTANCE_ID is unset. "
                "Bootstrap mode — proceeding without identity verification."
            )
        else:
            message = (
                f"iw_core_instance row is absent but IW_CORE_EXPECTED_INSTANCE_ID is set.\n"
                f"  Expected: {expected}\n"
                f"Remediation: run alembic upgrade head to re-create the row,"
                f" or remove IW_CORE_EXPECTED_INSTANCE_ID from .env."
            )
    elif expected is None:
        mode = "bootstrap"
        message = (
            f"IW_CORE_EXPECTED_INSTANCE_ID is unset. Live DB identity is {actual}.\n"
            f"  Add this line to .env to enable strict identity verification:\n"
            f"    IW_CORE_EXPECTED_INSTANCE_ID={actual}"
        )
    elif expected == actual:
        mode = "match"
        message = f"Identity verified — instance_id={actual}"
    else:
        mode = "mismatch"
        message = (
            f"DB instance-identity MISMATCH.\n"
            f"  Expected: {expected}   (from IW_CORE_EXPECTED_INSTANCE_ID)\n"
            f"  Actual  : {actual}   (from iw_core_instance.instance_id)\n"
            f"Remediation: restore the correct DB, or update IW_CORE_EXPECTED_INSTANCE_ID"
            f" in .env AFTER verifying the live DB is the one you intend."
        )

    return IdentityStatus(expected=expected, actual=actual, mode=mode, message=message)


def verify_instance_identity(session: Session) -> IdentityStatus:
    """Enforce identity. Raises on mismatch or missing row (when env is set).

    Returns IdentityStatus on match or bootstrap (no env var set).
    """
    status = check_identity(session)

    if status.mode == "mismatch":
        raise InstanceMismatchError(status.message)

    if status.mode == "missing" and status.expected is not None:
        raise InstanceRowMissingError(status.message)

    return status
