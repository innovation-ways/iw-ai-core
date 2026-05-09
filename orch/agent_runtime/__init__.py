"""Agent runtime option package.

Provides:
- resolver: cascade resolution of (cli_tool, model) from step/item/project/catalogue.
- audit: DaemonEvent emission helper for runtime override changes.
"""

from __future__ import annotations

from orch.agent_runtime.audit import emit_runtime_override_changed
from orch.agent_runtime.resolver import resolve_runtime

__all__ = ["emit_runtime_override_changed", "resolve_runtime"]
