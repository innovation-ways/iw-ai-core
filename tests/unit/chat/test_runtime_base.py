"""Unit tests for the ``ChatRuntime`` ABC (F-00086).

These tests assert the abstract base class contract — that a runtime
*must* implement every abstract method to be instantiable. They are
pure-Python (no DB, no httpx) so they live under ``tests/unit/chat/``
without needing the testcontainer fixture chain that the sibling
``test_tab_service.py`` requires.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest

from orch.chat.runtime_base import ChatRuntime


def test_chat_runtime_cannot_be_instantiated_directly() -> None:
    """ChatRuntime is abstract — bare instantiation must raise TypeError."""
    with pytest.raises(TypeError) as excinfo:
        ChatRuntime()  # type: ignore[abstract]
    # CPython spells the message as
    # "Can't instantiate abstract class ChatRuntime ..." — match loosely so
    # cosmetic wording changes in future versions do not break this test.
    msg = str(excinfo.value).lower()
    assert "abstract" in msg
    assert "chatruntime" in msg

    # Pin the abstract surface so a future edit that drops an @abstractmethod
    # (which would silently make ChatRuntime instantiable and break the
    # subclass contract) fails this test loudly.
    assert set(ChatRuntime.__abstractmethods__) == {
        "health",
        "create_session",
        "get_session",
        "list_sessions",
        "get_messages",
        "prompt",
        "abort",
        "reply_permission",
        "set_model",
        "close_session",
        "subscribe",
        "get_config",
        "get_providers",
    }


def test_subclass_missing_method_cannot_be_instantiated() -> None:
    """A subclass that misses even ONE abstract method is still abstract."""

    class _PartialRuntime(ChatRuntime):
        # Intentionally implements every abstract method EXCEPT ``prompt``.
        async def health(self) -> bool:
            return True

        async def create_session(
            self,
            *,
            model: str | None = None,
            agent: str | None = None,
            directory: str | None = None,
        ) -> str:
            return "sess-1"

        async def get_session(self, session_id: str) -> dict[str, Any]:
            return {}

        async def list_sessions(self) -> list[dict[str, Any]]:
            return []

        async def get_messages(self, session_id: str) -> list[dict[str, Any]]:
            return []

        async def abort(self, session_id: str) -> None:
            return

        async def reply_permission(
            self,
            session_id: str,
            request_id: str,
            response: str,
            *,
            remember: bool = False,
        ) -> None:
            return

        async def set_model(self, session_id: str, model: str) -> None:
            return

        async def close_session(self, session_id: str) -> None:
            return

        async def subscribe(
            self,
            session_id: str,
            *,
            last_event_id: str | None = None,
        ) -> AsyncIterator[dict[str, Any]]:
            if False:  # pragma: no cover — generator marker
                yield {}

        async def get_config(self) -> dict[str, Any]:
            return {}

        async def get_providers(self) -> dict[str, Any]:
            return {}

    # The missing ``prompt`` keeps the class abstract.
    assert _PartialRuntime.__abstractmethods__ == frozenset({"prompt"})
    with pytest.raises(TypeError) as excinfo:
        _PartialRuntime()  # type: ignore[abstract]
    assert "prompt" in str(excinfo.value).lower()


def test_complete_subclass_can_be_instantiated() -> None:
    """A subclass overriding every abstract method instantiates cleanly."""

    class _CompleteRuntime(ChatRuntime):
        async def health(self) -> bool:
            return True

        async def create_session(
            self,
            *,
            model: str | None = None,
            agent: str | None = None,
            directory: str | None = None,
        ) -> str:
            return "sess-x"

        async def get_session(self, session_id: str) -> dict[str, Any]:
            return {"id": session_id}

        async def list_sessions(self) -> list[dict[str, Any]]:
            return []

        async def get_messages(self, session_id: str) -> list[dict[str, Any]]:
            return []

        async def prompt(
            self,
            session_id: str,
            text: str,
            *,
            model: str | None = None,
            system: str | None = None,
        ) -> None:
            return

        async def abort(self, session_id: str) -> None:
            return

        async def reply_permission(
            self,
            session_id: str,
            request_id: str,
            response: str,
            *,
            remember: bool = False,
        ) -> None:
            return

        async def set_model(self, session_id: str, model: str) -> None:
            return

        async def close_session(self, session_id: str) -> None:
            return

        async def subscribe(
            self,
            session_id: str,
            *,
            last_event_id: str | None = None,
        ) -> AsyncIterator[dict[str, Any]]:
            if False:  # pragma: no cover — generator marker
                yield {}

        async def get_config(self) -> dict[str, Any]:
            return {}

        async def get_providers(self) -> dict[str, Any]:
            return {}

    # No abstract methods left → class is concrete.
    assert _CompleteRuntime.__abstractmethods__ == frozenset()
    instance = _CompleteRuntime()
    assert isinstance(instance, ChatRuntime)
