"""Unit tests for orch.db.identity module — CR-00014."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from orch.db.identity import (
    ENV_VAR,
    BoundIdentityStatus,
    IdentityStatus,
    InstanceMismatchError,
    InstanceRowMissingError,
    check_bound_identity,
    check_identity,
    get_expected_instance_id,
    get_live_instance_id,
    verify_instance_identity,
)


class TestGetExpectedInstanceId:
    """Tests for GetExpectedInstanceId scenarios."""

    def test_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifies that unset."""
        monkeypatch.delenv(ENV_VAR, raising=False)
        assert get_expected_instance_id() is None

    def test_empty_string(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifies that empty string."""
        monkeypatch.setenv(ENV_VAR, "")
        assert get_expected_instance_id() is None

    def test_whitespace_only(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifies that whitespace only."""
        monkeypatch.setenv(ENV_VAR, "   ")
        assert get_expected_instance_id() is None

    def test_valid(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifies that valid."""
        expected = uuid.uuid4()
        monkeypatch.setenv(ENV_VAR, str(expected))
        result = get_expected_instance_id()
        assert result == expected

    def test_uppercase(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifies that uppercase."""
        raw = str(uuid.uuid4()).upper()
        monkeypatch.setenv(ENV_VAR, raw)
        result = get_expected_instance_id()
        assert result is not None
        assert str(result).upper() == raw

    def test_malformed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifies that malformed."""
        monkeypatch.setenv(ENV_VAR, "not-a-uuid")
        with pytest.raises(ValueError, match="badly formed hexadecimal UUID string"):
            get_expected_instance_id()


class TestGetLiveInstanceId:
    """Tests for GetLiveInstanceId scenarios."""

    def test_row_missing(self, db_session: MagicMock) -> None:
        """Verifies that row missing."""
        db_session.get.return_value = None
        assert get_live_instance_id(db_session) is None

    def test_row_present(self, db_session: MagicMock) -> None:
        """Verifies that row present."""
        expected = uuid.uuid4()
        mock_row = MagicMock()
        mock_row.instance_id = expected
        db_session.get.return_value = mock_row
        result = get_live_instance_id(db_session)
        assert result == expected


class TestCheckIdentity:
    """Tests for CheckIdentity scenarios."""

    def test_match(self, db_session: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifies that match."""
        expected_uuid = uuid.uuid4()
        mock_row = MagicMock()
        mock_row.instance_id = expected_uuid
        db_session.get.return_value = mock_row
        monkeypatch.setenv(ENV_VAR, str(expected_uuid))

        status = check_identity(db_session)

        assert status.mode == "match"
        assert status.expected == expected_uuid
        assert status.actual == expected_uuid

    def test_mismatch(self, db_session: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifies that mismatch."""
        expected_uuid = uuid.uuid4()
        actual_uuid = uuid.uuid4()
        mock_row = MagicMock()
        mock_row.instance_id = actual_uuid
        db_session.get.return_value = mock_row
        monkeypatch.setenv(ENV_VAR, str(expected_uuid))

        status = check_identity(db_session)

        assert status.mode == "mismatch"
        assert status.expected == expected_uuid
        assert status.actual == actual_uuid

    def test_bootstrap(self, db_session: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifies that bootstrap."""
        actual_uuid = uuid.uuid4()
        mock_row = MagicMock()
        mock_row.instance_id = actual_uuid
        db_session.get.return_value = mock_row
        monkeypatch.delenv(ENV_VAR, raising=False)

        status = check_identity(db_session)

        assert status.mode == "bootstrap"
        assert status.expected is None
        assert status.actual == actual_uuid

    def test_missing_env_set(self, db_session: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifies that missing env set."""
        db_session.get.return_value = None
        monkeypatch.setenv(ENV_VAR, str(uuid.uuid4()))

        status = check_identity(db_session)

        assert status.mode == "missing"
        assert status.expected is not None
        assert status.actual is None

    def test_missing_env_unset(
        self, db_session: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verifies that missing env unset."""
        db_session.get.return_value = None
        monkeypatch.delenv(ENV_VAR, raising=False)

        status = check_identity(db_session)

        assert status.mode == "missing"
        assert status.expected is None
        assert status.actual is None


class TestCheckBoundIdentity:
    """Tests for CheckBoundIdentity scenarios."""

    def test_match(self, db_session: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifies that match."""
        bound = uuid.uuid4()
        mock_row = MagicMock()
        mock_row.instance_id = bound
        db_session.get.return_value = mock_row
        monkeypatch.setenv(ENV_VAR, str(bound))

        status = check_bound_identity(db_session, bound)

        assert isinstance(status, BoundIdentityStatus)
        assert status.mode == "match"
        assert status.actual == bound

    def test_changed(self, db_session: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifies that changed."""
        bound = uuid.uuid4()
        live = uuid.uuid4()
        mock_row = MagicMock()
        mock_row.instance_id = live
        db_session.get.return_value = mock_row
        monkeypatch.setenv(ENV_VAR, str(bound))

        status = check_bound_identity(db_session, bound)

        assert status.mode == "changed"
        assert status.bound == bound
        assert status.actual == live

    def test_missing_while_pinned(
        self, db_session: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verifies that missing while pinned."""
        bound = uuid.uuid4()
        db_session.get.return_value = None
        monkeypatch.setenv(ENV_VAR, str(bound))

        status = check_bound_identity(db_session, bound)

        assert status.mode == "missing_while_pinned"


class TestVerifyInstanceIdentity:
    """Tests for VerifyInstanceIdentity scenarios."""

    def test_match(self, db_session: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifies that match."""
        expected_uuid = uuid.uuid4()
        mock_row = MagicMock()
        mock_row.instance_id = expected_uuid
        db_session.get.return_value = mock_row
        monkeypatch.setenv(ENV_VAR, str(expected_uuid))

        status = verify_instance_identity(db_session)

        assert status.mode == "match"
        assert isinstance(status, IdentityStatus)

    def test_bootstrap(self, db_session: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifies that bootstrap."""
        actual_uuid = uuid.uuid4()
        mock_row = MagicMock()
        mock_row.instance_id = actual_uuid
        db_session.get.return_value = mock_row
        monkeypatch.delenv(ENV_VAR, raising=False)

        status = verify_instance_identity(db_session)

        assert status.mode == "bootstrap"

    def test_mismatch_raises(self, db_session: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifies that mismatch raises."""
        expected_uuid = uuid.uuid4()
        actual_uuid = uuid.uuid4()
        mock_row = MagicMock()
        mock_row.instance_id = actual_uuid
        db_session.get.return_value = mock_row
        monkeypatch.setenv(ENV_VAR, str(expected_uuid))

        with pytest.raises(InstanceMismatchError) as exc_info:
            verify_instance_identity(db_session)

        msg = str(exc_info.value)
        assert str(expected_uuid) in msg
        assert str(actual_uuid) in msg

    def test_missing_row_with_env_set_raises(
        self, db_session: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verifies that missing row with env set raises."""
        db_session.get.return_value = None
        monkeypatch.setenv(ENV_VAR, str(uuid.uuid4()))

        with pytest.raises(InstanceRowMissingError):
            verify_instance_identity(db_session)

    def test_missing_row_env_unset_does_not_raise(
        self, db_session: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verifies that missing row env unset does not raise."""
        db_session.get.return_value = None
        monkeypatch.delenv(ENV_VAR, raising=False)

        status = verify_instance_identity(db_session)

        assert status.mode == "missing"
