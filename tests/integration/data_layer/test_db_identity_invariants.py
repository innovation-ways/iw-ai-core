"""DB-identity invariant assertions — companion to test_db_identity_integration.py.

This module formally asserts the three DB-identity invariants from CR-00014:
  1. Match path:  IW_CORE_EXPECTED_INSTANCE_ID matches the DB fingerprint → proceed.
  2. Mismatch path:  IW_CORE_EXPECTED_INSTANCE_ID differs from fingerprint → raise.
  3. Bootstrap path:  IW_CORE_EXPECTED_INSTANCE_ID unset + row exists → proceed.

Unlike test_db_identity_integration.py (which uses a module-scoped
migrated_engine), these tests run in the per-test template clone provided by
db_session, so each test is fully isolated and order-independent.

Invariant 2 (mismatch) is the primary target: it is the I-00041 regression net
for the live-DB guard.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

from orch.db.identity import (
    InstanceMismatchError,
    InstanceRowMissingError,
    check_identity,
    verify_instance_identity,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Match path
# ---------------------------------------------------------------------------


def test_identity_check_match_path(db_session: Session) -> None:
    """When env matches DB row, check_identity returns mode=match."""
    # Read the actual instance ID from the test DB
    row = db_session.execute(
        text("SELECT instance_id FROM iw_core_instance WHERE id = 1")
    ).fetchone()
    assert row is not None, "iw_core_instance row must exist (template was migrated)"
    actual_fingerprint = row.instance_id

    # monkeypatch: set env to match
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("IW_CORE_EXPECTED_INSTANCE_ID", str(actual_fingerprint))
        status = check_identity(db_session)

    assert status.mode == "match", (
        f"Expected mode='match' when env matches DB. "
        f"mode={status.mode!r}, message={status.message!r}"
    )
    assert status.expected == actual_fingerprint
    assert status.actual == actual_fingerprint


def test_verify_instance_identity_match_path_no_exception(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When env matches DB row, verify_instance_identity does not raise."""
    row = db_session.execute(
        text("SELECT instance_id FROM iw_core_instance WHERE id = 1")
    ).fetchone()
    assert row is not None
    actual_fingerprint = row.instance_id

    monkeypatch.setenv("IW_CORE_EXPECTED_INSTANCE_ID", str(actual_fingerprint))

    # Should not raise
    status = verify_instance_identity(db_session)
    assert status.mode == "match"


# ---------------------------------------------------------------------------
# Mismatch path
# ---------------------------------------------------------------------------


def test_identity_check_mismatch_path(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """When env differs from DB row, check_identity returns mode=mismatch."""
    row = db_session.execute(
        text("SELECT instance_id FROM iw_core_instance WHERE id = 1")
    ).fetchone()
    assert row is not None
    actual_fingerprint = row.instance_id

    # Set env to a DIFFERENT UUID
    wrong_fingerprint = uuid.uuid4()
    while wrong_fingerprint == actual_fingerprint:
        wrong_fingerprint = uuid.uuid4()
    monkeypatch.setenv("IW_CORE_EXPECTED_INSTANCE_ID", str(wrong_fingerprint))

    status = check_identity(db_session)

    assert status.mode == "mismatch", (
        f"Expected mode='mismatch' when env differs from DB. "
        f"mode={status.mode!r}, message={status.message!r}"
    )
    assert status.expected == wrong_fingerprint
    assert status.actual == actual_fingerprint


def test_verify_instance_identity_mismatch_raises(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When env differs from DB row, verify_instance_identity raises InstanceMismatchError."""
    row = db_session.execute(
        text("SELECT instance_id FROM iw_core_instance WHERE id = 1")
    ).fetchone()
    assert row is not None
    actual_fingerprint = row.instance_id

    wrong_fingerprint = uuid.uuid4()
    while wrong_fingerprint == actual_fingerprint:
        wrong_fingerprint = uuid.uuid4()
    monkeypatch.setenv("IW_CORE_EXPECTED_INSTANCE_ID", str(wrong_fingerprint))

    with pytest.raises(InstanceMismatchError) as exc_info:
        verify_instance_identity(db_session)

    # Assert on specific error message content
    exc_message = str(exc_info.value)
    assert "MISMATCH" in exc_message or "mismatch" in exc_message, (
        f"Expected mismatch signal in error message, got: {exc_message!r}"
    )


# ---------------------------------------------------------------------------
# Bootstrap path (env unset)
# ---------------------------------------------------------------------------


def test_identity_check_bootstrap_path(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When env is unset and row exists, check_identity returns mode=bootstrap."""
    monkeypatch.delenv("IW_CORE_EXPECTED_INSTANCE_ID", raising=False)
    status = check_identity(db_session)
    assert status.mode == "bootstrap", (
        f"Expected mode='bootstrap' when env is unset. "
        f"mode={status.mode!r}, message={status.message!r}"
    )


def test_verify_instance_identity_bootstrap_no_exception(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When env is unset and row exists, verify_instance_identity proceeds."""
    monkeypatch.delenv("IW_CORE_EXPECTED_INSTANCE_ID", raising=False)
    status = verify_instance_identity(db_session)
    assert status.mode == "bootstrap"


# ---------------------------------------------------------------------------
# Missing row with env set — InstanceRowMissingError
# ---------------------------------------------------------------------------


def test_verify_instance_identity_missing_row_with_env_raises(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When env is set but the iw_core_instance row is missing, raise InstanceRowMissingError."""
    # Delete the row first (test DB has it from migration; we delete it)
    db_session.execute(text("DELETE FROM iw_core_instance"))
    db_session.commit()

    # Set env to something (anything — the value is irrelevant when the row is missing)
    monkeypatch.setenv("IW_CORE_EXPECTED_INSTANCE_ID", str(uuid.uuid4()))

    with pytest.raises(InstanceRowMissingError):
        verify_instance_identity(db_session)
