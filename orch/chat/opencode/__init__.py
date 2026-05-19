"""OpenCode runtime adapter (F-00086 subpackage).

Re-exports the canonical names so downstream code reads as
``from orch.chat.opencode import OpencodeRuntime, OpencodeClient, RelayManager``.
"""

from __future__ import annotations

from orch.chat.opencode.client import OpencodeClient
from orch.chat.opencode.relay_manager import RelayManager, SessionRelay
from orch.chat.opencode.runtime import OpencodeRuntime

__all__ = (
    "OpencodeClient",
    "OpencodeRuntime",
    "RelayManager",
    "SessionRelay",
)
