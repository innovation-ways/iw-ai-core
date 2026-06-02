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
    """In-memory progress record for a single Level 2 module documentation generation task.

    Attributes:
        project_id: Project the module belongs to.
        module_path: Filesystem path of the module being documented.
        module_name: Human-readable display name.
        model: LLM model name used for generation.
        total_steps: Total number of generation steps (default 5).
        step: Current step index (0 = not started).
        step_label: Human-readable description of the current step.
        started_at: UTC timestamp when generation started.
        updated_at: UTC timestamp of the last progress update.
        error: Error message if the task failed, otherwise None.
        done: True once generation completed (successfully or with error).
    """

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
        """Seconds elapsed since generation started."""
        return int((datetime.now(UTC) - self.started_at).total_seconds())

    @property
    def percent(self) -> int:
        """Completion percentage clamped to [0, 100]."""
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
    """Create and register a new ModuleGenProgress entry for the given module.

    Args:
        project_id: Project the module belongs to.
        module_path: Filesystem path of the module being documented.
        module_name: Human-readable display name.
        model: LLM model name being used for generation.

    Returns:
        The newly created ModuleGenProgress registered in the in-memory store.
    """
    p = ModuleGenProgress(
        project_id=project_id,
        module_path=module_path,
        module_name=module_name,
        model=model,
    )
    _PROGRESS[_key(project_id, module_path)] = p
    return p


def update_progress(project_id: str, module_path: str, **fields: object) -> None:
    """Update arbitrary fields on an existing ModuleGenProgress entry.

    Args:
        project_id: Project the module belongs to.
        module_path: Filesystem path used to look up the progress entry.
        **fields: Keyword arguments corresponding to ModuleGenProgress attributes.
    """
    p = _PROGRESS.get(_key(project_id, module_path))
    if p is None:
        return
    for k, v in fields.items():
        setattr(p, k, v)
    p.updated_at = datetime.now(UTC)


def get_progress(project_id: str, module_path: str) -> ModuleGenProgress | None:
    """Return the current progress entry for the module, or None if not registered.

    Args:
        project_id: Project the module belongs to.
        module_path: Filesystem path of the module.

    Returns:
        The ModuleGenProgress entry if present, otherwise None.
    """
    return _PROGRESS.get(_key(project_id, module_path))


def clear_progress(project_id: str, module_path: str) -> None:
    """Remove the progress entry and task reference for the given module.

    Args:
        project_id: Project the module belongs to.
        module_path: Filesystem path of the module to clear.
    """
    _PROGRESS.pop(_key(project_id, module_path), None)
    _TASKS.pop(_key(project_id, module_path), None)


def get_or_start_task(
    project_id: str,
    module_path: str,
    coro_factory: Callable[[], Awaitable[object]],
) -> asyncio.Task[object]:
    """Return the existing asyncio task for the module, or start a new one.

    If an existing task is still running (not done), it is returned unchanged.
    A new task is created by calling coro_factory() when no live task exists.
    The task's done callback automatically updates the progress entry with any
    cancellation or exception.

    Args:
        project_id: Project the module belongs to.
        module_path: Filesystem path used as the deduplication key.
        coro_factory: Callable that returns the coroutine to schedule.

    Returns:
        The running or newly created asyncio Task.
    """
    key = _key(project_id, module_path)
    existing = _TASKS.get(key)
    if existing is not None and not existing.done():
        return existing

    task: asyncio.Task[object] = asyncio.ensure_future(coro_factory())
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
