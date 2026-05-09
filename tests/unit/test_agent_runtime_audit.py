"""Unit tests for orch.agent_runtime.audit — DaemonEvent emission helper."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

if TYPE_CHECKING:
    from orch.db.models import DaemonEvent


class TestEmitRuntimeOverrideChanged:
    """Tests for emit_runtime_override_changed."""

    def test_emits_single_event(self) -> None:
        """AC6: exactly one DaemonEvent row is written regardless of step count."""
        from orch.agent_runtime.audit import emit_runtime_override_changed

        mock_session = MagicMock()

        emit_runtime_override_changed(
            session=mock_session,
            project_id="test-project",
            item_id="F-00081",
            scope="bulk",
            step_ids=["S02", "S03", "S04", "S05", "S06"],
            old_option_id=None,
            new_option_id=3,
            actor="test@example.com",
        )

        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

        event: DaemonEvent = mock_session.add.call_args[0][0]
        assert event.event_type == "runtime_override_changed"
        assert event.project_id == "test-project"
        assert event.entity_id == "F-00081"
        assert event.entity_type == "work_item"
        assert event.event_metadata["scope"] == "bulk"
        assert event.event_metadata["step_ids"] == ["S02", "S03", "S04", "S05", "S06"]
        assert event.event_metadata["old_option_id"] is None
        assert event.event_metadata["new_option_id"] == 3
        assert event.event_metadata["actor"] == "test@example.com"

    def test_emits_item_scope_event(self) -> None:
        """Single-step override emits scope='item'."""
        from orch.agent_runtime.audit import emit_runtime_override_changed

        mock_session = MagicMock()

        emit_runtime_override_changed(
            session=mock_session,
            project_id="test-project",
            item_id="F-00081",
            scope="item",
            step_ids=None,
            old_option_id=1,
            new_option_id=4,
            actor="operator@example.com",
        )

        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

        event: DaemonEvent = mock_session.add.call_args[0][0]
        assert event.event_type == "runtime_override_changed"
        assert event.event_metadata["scope"] == "item"
        assert event.event_metadata["step_ids"] is None
        assert event.event_metadata["old_option_id"] == 1
        assert event.event_metadata["new_option_id"] == 4

    def test_emits_step_scope_event(self) -> None:
        """Step-level override emits scope='step' with single step_ids list."""
        from orch.agent_runtime.audit import emit_runtime_override_changed

        mock_session = MagicMock()

        emit_runtime_override_changed(
            session=mock_session,
            project_id="innoforge",
            item_id="F-00081",
            scope="step",
            step_ids=["S02"],
            old_option_id=None,
            new_option_id=2,
            actor="user@example.com",
        )

        mock_session.add.assert_called_once()

        event: DaemonEvent = mock_session.add.call_args[0][0]
        assert event.event_type == "runtime_override_changed"
        assert event.event_metadata["scope"] == "step"
        assert event.event_metadata["step_ids"] == ["S02"]

    def test_emits_with_old_and_new_none(self) -> None:
        """Clearing an override (both old and new are None) still emits an event."""
        from orch.agent_runtime.audit import emit_runtime_override_changed

        mock_session = MagicMock()

        emit_runtime_override_changed(
            session=mock_session,
            project_id="test-project",
            item_id="F-00081",
            scope="item",
            step_ids=None,
            old_option_id=3,
            new_option_id=None,
            actor="user@example.com",
        )

        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

        event: DaemonEvent = mock_session.add.call_args[0][0]
        assert event.event_metadata["old_option_id"] == 3
        assert event.event_metadata["new_option_id"] is None

    def test_bulk_with_zero_steps_still_emits_one_event(self) -> None:
        """Even when bulk targets zero editable steps, one event is emitted with empty step_ids."""
        from orch.agent_runtime.audit import emit_runtime_override_changed

        mock_session = MagicMock()

        emit_runtime_override_changed(
            session=mock_session,
            project_id="test-project",
            item_id="F-00081",
            scope="bulk",
            step_ids=[],  # zero editable steps
            old_option_id=None,
            new_option_id=5,
            actor="operator",
        )

        mock_session.add.assert_called_once()
        event: DaemonEvent = mock_session.add.call_args[0][0]
        assert event.event_metadata["step_ids"] == []
