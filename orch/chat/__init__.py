"""Dashboard AI Assistant chat package.

Hosts:

* The runtime-agnostic :class:`ChatRuntime` ABC (F-00086, F-B).
* The OpenCode runtime adapter — subprocess lifecycle, HTTP/SSE client,
  multi-tab relay.
* The Pi runtime adapter — per-tab ``pi --mode rpc`` subprocess pool
  with LRU eviction and idle reaper (F-00087).
* The ``chat_tabs`` CRUD layer (``tab_service``) and the one-time
  default-tab bootstrap (``migration_helpers.bootstrap_default_tab``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from orch.chat import tab_service
from orch.chat.migration_helpers import bootstrap_default_tab
from orch.chat.opencode import OpencodeClient, OpencodeRuntime, RelayManager, SessionRelay
from orch.chat.pi.pi_runtime import PiRuntime
from orch.chat.runtime_base import ChatRuntime

if TYPE_CHECKING:
    from orch.db.models import ChatTab


def get_runtime_for_tab(tab: ChatTab, app_state: Any) -> ChatRuntime:
    """Resolve the per-runtime instance from ``app.state`` by ``tab.runtime``.

    Raises ``ValueError`` for unknown runtime strings.
    """
    if tab.runtime == "opencode":
        return app_state.opencode_runtime  # type: ignore[no-any-return]
    if tab.runtime == "pi":
        return app_state.pi_runtime  # type: ignore[no-any-return]
    raise ValueError(f"unknown runtime {tab.runtime!r}")


__all__ = (
    "ChatRuntime",
    "OpencodeClient",
    "OpencodeRuntime",
    "PiRuntime",
    "RelayManager",
    "SessionRelay",
    "bootstrap_default_tab",
    "get_runtime_for_tab",
    "tab_service",
)
