"""Runtime-agnostic chat backend contract (F-00086).

``ChatRuntime`` is the abstract base class that every chat runtime (today
``OpencodeRuntime``; tomorrow ``PiRuntime`` from F-B) must implement. The
ABC encodes the wire-shape contract: every coroutine signature is part of
the public API and is consumed by ``tab_service``, the chat router, and
``RelayManager`` without reaching into runtime-specific code paths.

We use ``abc.ABC`` (not ``typing.Protocol``) for two reasons:

* ``@abstractmethod`` fails subclass *instantiation* if a method is
  missing — drift is caught at construction, not in production at the
  first call site.
* ``mypy`` strict mode flags missing implementations even when callers
  go through a base-class type hint.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class ChatRuntime(ABC):
    """Abstract chat runtime: subprocess + HTTP + SSE wire surface.

    Concrete subclasses MUST implement every method. ``health()`` is the
    only synchronously-meaningful gate — the router uses it before
    dispatching any session-bound call.
    """

    @abstractmethod
    async def health(self) -> bool:
        """Return True iff the runtime is up and ready to accept requests."""

    @abstractmethod
    async def create_session(
        self,
        *,
        model: str | None = None,
        agent: str | None = None,
        directory: str | None = None,
    ) -> str:
        """Create a runtime-side session and return its identifier."""

    @abstractmethod
    async def get_session(self, session_id: str) -> dict[str, Any]:
        """Return the runtime's metadata blob for ``session_id``."""

    @abstractmethod
    async def list_sessions(self) -> list[dict[str, Any]]:
        """Return all runtime-side sessions (used by ``bootstrap_default_tab``)."""

    @abstractmethod
    async def get_messages(self, session_id: str) -> list[dict[str, Any]]:
        """Return the full message history for ``session_id``."""

    @abstractmethod
    async def prompt(
        self,
        session_id: str,
        text: str,
        *,
        model: str | None = None,
        system: str | None = None,
    ) -> None:
        """Kick off a streaming completion for ``session_id``."""

    @abstractmethod
    async def abort(self, session_id: str) -> None:
        """Cancel any in-flight completion on ``session_id``."""

    @abstractmethod
    async def reply_permission(
        self,
        session_id: str,
        request_id: str,
        response: str,
        *,
        remember: bool = False,
    ) -> None:
        """Reply to a permission-asked event for ``session_id``."""

    @abstractmethod
    async def set_model(self, session_id: str, model: str) -> None:
        """Pin the session's default model for subsequent prompts.

        Implementations that route the model on a per-prompt basis (OpenCode)
        may treat this as a no-op — the tab-service stores the model on the
        ``chat_tabs`` row and forwards it to ``prompt()`` per call.
        """

    @abstractmethod
    async def close_session(self, session_id: str) -> None:
        """Release runtime-side resources for ``session_id``.

        For OpenCode this is a no-op: closing a tab in the UI is a
        soft-delete in ``chat_tabs`` only; the runtime session is kept so
        ``reopen_tab`` can restore the full history.
        """

    @abstractmethod
    def subscribe(
        self,
        session_id: str,
        *,
        last_event_id: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield normalised event dicts for ``session_id``.

        The yielded shape is ``{event, data, id, ...}``. Production consumers
        go through ``RelayManager`` (fan-out + ring buffer); this method is
        the low-level single-subscriber surface.

        Declared ``def`` (not ``async def``) so concrete implementations are
        free to be async generators — ``async def foo(): yield ...`` makes
        ``foo`` return an ``AsyncGenerator`` (a subtype of ``AsyncIterator``)
        directly, matching this signature, while ``async def foo() ->
        AsyncIterator: ...`` with a yield body is typed as
        ``Coroutine[..., AsyncIterator]`` by mypy and fails the LSP check.
        """

    @abstractmethod
    async def get_config(self) -> dict[str, Any]:
        """Return the runtime's static config blob (models, defaults, ...)."""

    @abstractmethod
    async def get_providers(self) -> dict[str, Any]:
        """Return the runtime's enumerated provider catalogue."""
