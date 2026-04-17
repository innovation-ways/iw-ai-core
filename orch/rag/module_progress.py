"""In-memory progress + task registry for Level 2 module doc generation.

Module doc generation runs outside of any HTTP request lifecycle (takes 2-4 min
for a local LLM). This registry:

- Deduplicates concurrent generation attempts for the same (project, module).
- Exposes per-step progress to the spinner fragment that polls the HTTP endpoint.
- Captures the exception if the background task raises, so the next poll can
  render an error card instead of spinning forever.

Process-local only — does not persist across dashboard restarts.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


@dataclass
class ModuleGenProgress:
    project_id: str
    module_path: str
    module_name: str
    model: str = ""
    total_steps: int = 5
    step: int = 0
    step_label: str = "queued"
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    error: str | None = None
    done: bool = False

    @property
    def elapsed_seconds(self) -> int:
        return int((datetime.now(UTC) - self.started_at).total_seconds())

    @property
    def percent(self) -> int:
        total = max(self.total_steps, 1)
        return min(int(self.step / total * 100), 100)


_TASKS: dict[str, asyncio.Task[object]] = {}
_PROGRESS: dict[str, ModuleGenProgress] = {}


def _key(project_id: str, module_path: str) -> str:
    return f"{project_id}::{module_path}"


def start_progress(
    project_id: str,
    module_path: str,
    module_name: str,
    model: str,
) -> ModuleGenProgress:
    p = ModuleGenProgress(
        project_id=project_id,
        module_path=module_path,
        module_name=module_name,
        model=model,
    )
    _PROGRESS[_key(project_id, module_path)] = p
    return p


def update_progress(project_id: str, module_path: str, **fields: object) -> None:
    p = _PROGRESS.get(_key(project_id, module_path))
    if p is None:
        return
    for k, v in fields.items():
        setattr(p, k, v)
    p.updated_at = datetime.now(UTC)


def get_progress(project_id: str, module_path: str) -> ModuleGenProgress | None:
    return _PROGRESS.get(_key(project_id, module_path))


def clear_progress(project_id: str, module_path: str) -> None:
    _PROGRESS.pop(_key(project_id, module_path), None)
    _TASKS.pop(_key(project_id, module_path), None)


def get_or_start_task(
    project_id: str,
    module_path: str,
    coro_factory: Callable[[], Awaitable[object]],
) -> asyncio.Task[object]:
    key = _key(project_id, module_path)
    existing = _TASKS.get(key)
    if existing is not None and not existing.done():
        return existing

    task = asyncio.create_task(coro_factory())
    _TASKS[key] = task

    def _on_done(t: asyncio.Task[object]) -> None:
        if t.cancelled():
            update_progress(project_id, module_path, error="cancelled", done=True)
            return
        exc = t.exception()
        if exc is not None:
            update_progress(
                project_id, module_path, error=f"{type(exc).__name__}: {exc}", done=True
            )

    task.add_done_callback(_on_done)
    return task
