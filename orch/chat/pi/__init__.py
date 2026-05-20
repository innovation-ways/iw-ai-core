"""Pi runtime subpackage — ``orch.chat.pi`` (F-00087).

Re-exports the public surface for consumers that do ``from orch.chat.pi import ...``.
"""

from __future__ import annotations

from orch.chat.pi.event_normalizer import normalize_pi_event
from orch.chat.pi.pi_jsonl_reader import aiter_jsonl_lines
from orch.chat.pi.pi_rpc_client import PiRpcClient
from orch.chat.pi.pi_runtime import IDLE_TIMEOUT_SECONDS, MAX_PI_TABS, PiRuntime

__all__ = (
    "IDLE_TIMEOUT_SECONDS",
    "MAX_PI_TABS",
    "PiRpcClient",
    "PiRuntime",
    "aiter_jsonl_lines",
    "normalize_pi_event",
)
