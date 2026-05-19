"""Dashboard AI Assistant chat package.

Hosts:

* The runtime-agnostic :class:`ChatRuntime` ABC (F-00086, F-B).
* The OpenCode runtime adapter — subprocess lifecycle, HTTP/SSE client,
  multi-tab relay. Today the only concrete :class:`ChatRuntime`.
* The ``chat_tabs`` CRUD layer (``tab_service``) and the one-time
  default-tab bootstrap (``migration_helpers.bootstrap_default_tab``).
"""

from __future__ import annotations

from orch.chat import tab_service
from orch.chat.migration_helpers import bootstrap_default_tab
from orch.chat.opencode import OpencodeClient, OpencodeRuntime, RelayManager, SessionRelay
from orch.chat.runtime_base import ChatRuntime

__all__ = (
    "ChatRuntime",
    "OpencodeClient",
    "OpencodeRuntime",
    "RelayManager",
    "SessionRelay",
    "bootstrap_default_tab",
    "tab_service",
)
