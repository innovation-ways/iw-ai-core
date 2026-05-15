"""Dashboard AI Assistant chat package.

Hosts the managed `opencode serve` subprocess lifecycle (S01), the
backend↔runtime HTTP+SSE client (S02), and the multi-session relay (S02).
"""

from __future__ import annotations

from orch.chat.opencode_client import OpencodeClient
from orch.chat.opencode_runtime import OpencodeRuntime
from orch.chat.relay_manager import RelayManager, SessionRelay

__all__ = (
    "OpencodeClient",
    "OpencodeRuntime",
    "RelayManager",
    "SessionRelay",
)
