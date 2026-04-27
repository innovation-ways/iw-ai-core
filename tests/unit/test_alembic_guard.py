"""Unit tests for orch.db.alembic_guard — the alembic-version guard helper.

Tests the public API in isolation, mocking the DB layer
(safe_migrate.list_pending_revisions, current_revision).
No real DB connection.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from orch.db.alembic_guard import (
    DBBehindHeadError,
    GuardStatus,
    MultipleHeadsError,
    assert_db_at_head,
    check_db_at_head,
    remediation_message,
)


class TestCheckDbAtHead:
    def test_returns_ok_when_aligned(self) -> None:
        """current_rev == head_rev and zero pending → ok is True."""
        with (
            patch("orch.db.alembic_guard.current_revision", return_value="abc123"),
            patch("orch.db.alembic_guard._get_head_revisions", return_value=("abc123", [])),
            patch(
                "orch.db.alembic_guard.list_pending_revisions",
                return_value=[],
            ),
        ):
            result = check_db_at_head("postgresql://dummy")
            assert result.ok is True
            assert result.current_rev == "abc123"
            assert result.head_rev == "abc123"
            assert result.pending == []
            assert result.multiple_heads == []

    def test_returns_not_ok_when_behind(self) -> None:
        """Given pending revisions, ok is False and pending list is head-first."""
        with (
            patch("orch.db.alembic_guard.current_revision", return_value="old_rev"),
            patch("orch.db.alembic_guard._get_head_revisions", return_value=("head_rev", [])),
        ):

            class FakeRevision:
                id: str

                def __init__(self, id_: str) -> None:
                    self.id = id_

            with patch(
                "orch.db.alembic_guard.list_pending_revisions",
                return_value=[FakeRevision("rev_c"), FakeRevision("rev_b")],
            ):
                result = check_db_at_head("postgresql://dummy")
                assert result.ok is False
                assert result.current_rev == "old_rev"
                assert result.head_rev == "head_rev"
                assert result.pending == ["rev_c", "rev_b"]

    def test_handles_multiple_heads(self) -> None:
        """MultipleHeadsError from list_pending_revisions → multiple_heads reported."""
        with (
            patch("orch.db.alembic_guard.current_revision", return_value="abc123"),
            patch(
                "orch.db.alembic_guard._get_head_revisions",
                return_value=(None, ["head_a", "head_b"]),
            ),
            patch(
                "orch.db.alembic_guard.list_pending_revisions",
                side_effect=MultipleHeadsError("multiple heads"),
            ),
        ):
            result = check_db_at_head("postgresql://dummy")
            assert result.ok is False
            assert result.multiple_heads == ["head_a", "head_b"]
            assert result.pending == []

    def test_handles_empty_alembic_version(self) -> None:
        """current_rev is None → current_rev=None, pending contains all script revisions."""
        with (
            patch("orch.db.alembic_guard.current_revision", return_value=None),
            patch("orch.db.alembic_guard._get_head_revisions", return_value=("head_rev", [])),
        ):

            class FakeRevision:
                id: str

                def __init__(self, id_: str) -> None:
                    self.id = id_

            with patch(
                "orch.db.alembic_guard.list_pending_revisions",
                return_value=[FakeRevision("rev_x"), FakeRevision("rev_y")],
            ):
                result = check_db_at_head("postgresql://dummy")
                assert result.current_rev is None
                assert result.head_rev == "head_rev"
                assert result.pending == ["rev_x", "rev_y"]


class TestAssertDbAtHead:
    def test_raises_db_behind_head_error_with_revs_in_msg(self) -> None:
        """Raised exception message contains current_rev, head_rev, and 'make db-migrate'."""
        status = GuardStatus(
            current_rev="old_rev",
            head_rev="new_rev",
            pending=["c", "b"],
            multiple_heads=[],
            ok=False,
        )
        with patch("orch.db.alembic_guard.check_db_at_head", return_value=status):
            with pytest.raises(DBBehindHeadError) as exc_info:
                assert_db_at_head("postgresql://dummy")

            msg = str(exc_info.value)
            assert "old_rev" in msg
            assert "new_rev" in msg
            assert "make db-migrate" in msg

    def test_raises_db_behind_head_error_with_empty_for_none_current_rev(self) -> None:
        """current_rev=None is displayed as 'EMPTY' in the error message."""
        status = GuardStatus(
            current_rev=None,
            head_rev="head_abc",
            pending=["p1"],
            multiple_heads=[],
            ok=False,
        )
        with patch("orch.db.alembic_guard.check_db_at_head", return_value=status):
            with pytest.raises(DBBehindHeadError) as exc_info:
                assert_db_at_head("postgresql://dummy")

            msg = str(exc_info.value)
            assert "EMPTY" in msg
            assert "head_abc" in msg
            assert "make db-migrate" in msg

    def test_silent_on_match(self) -> None:
        """No exception raised when status.ok is True."""
        status = GuardStatus(
            current_rev="abc123",
            head_rev="abc123",
            pending=[],
            multiple_heads=[],
            ok=True,
        )
        with patch("orch.db.alembic_guard.check_db_at_head", return_value=status):
            assert_db_at_head("postgresql://dummy")  # must not raise

    def test_raises_multiple_heads_error_when_multiple_heads(self) -> None:
        """Multiple heads detected raises MultipleHeadsError."""
        status = GuardStatus(
            current_rev="abc123",
            head_rev=None,
            pending=[],
            multiple_heads=["head_a", "head_b"],
            ok=False,
        )
        with patch("orch.db.alembic_guard.check_db_at_head", return_value=status):
            with pytest.raises(MultipleHeadsError) as exc_info:
                assert_db_at_head("postgresql://dummy")

            msg = str(exc_info.value)
            assert "head_a" in msg
            assert "head_b" in msg


class TestRemediationMessage:
    def test_remediation_message_format(self) -> None:
        """Single line contains current_rev=…, head_rev=…, and 'make db-migrate'."""
        status = GuardStatus(
            current_rev="current_xyz",
            head_rev="head_xyz",
            pending=["p1", "p2"],
            multiple_heads=[],
            ok=False,
        )
        msg = remediation_message(status)
        assert "current_rev=current_xyz" in msg
        assert "head_rev=head_xyz" in msg
        assert "make db-migrate" in msg
        assert "\n" not in msg

    def test_remediation_message_empty_current_rev(self) -> None:
        """current_rev=None renders as EMPTY in the remediation message."""
        status = GuardStatus(
            current_rev=None,
            head_rev="head_abc",
            pending=["p1"],
            multiple_heads=[],
            ok=False,
        )
        msg = remediation_message(status)
        assert "current_rev=EMPTY" in msg
        assert "head_rev=head_abc" in msg


class TestAssertDbAtHeadSkipsGuard:
    def test_assert_db_at_head_skips_when_skip_guard_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """IW_CORE_SKIP_ALEMBIC_GUARD=true causes silent return without calling DB."""
        monkeypatch.setenv("IW_CORE_SKIP_ALEMBIC_GUARD", "true")
        from importlib import reload

        import orch.db.alembic_guard as ag

        reload(ag)
        try:
            ag.assert_db_at_head("postgresql://dummy")
        finally:
            reload(ag)

    def test_assert_db_at_head_skips_when_agent_context(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """IW_CORE_AGENT_CONTEXT=true causes silent return without calling DB."""
        monkeypatch.setenv("IW_CORE_AGENT_CONTEXT", "true")
        from importlib import reload

        import orch.db.alembic_guard as ag

        reload(ag)
        try:
            ag.assert_db_at_head("postgresql://dummy")
        finally:
            reload(ag)
