"""Agent runtime option resolver — cascade resolution of (cli_tool, model).

Cascade order (per F-00081 design):
  1. WorkflowStep.agent_runtime_option_id  (step override — most specific)
  2. WorkItem.agent_runtime_option_id      (item override)
  3. projects.toml (cli_tool, model) lookup in agent_runtime_options catalogue
  4. agent_runtime_options.is_default=true row (catalogue default — guaranteed by migration)

Disabled rows in the chain are skipped with a warning log, falling through to
the next level. This module has NO database-opening logic — the caller passes
an active Session.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy import select

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from orch.db.models import AgentRuntimeOption

logger = logging.getLogger(__name__)


def resolve_runtime(
    session: Session,
    *,
    step: object,
    item: object,
    project: object,
) -> AgentRuntimeOption:
    """Resolve the runtime (cli_tool, model) option for a step.

    Args:
        session: Active SQLAlchemy session (caller manages commit/rollback).
        step: WorkflowStep row (or fake with .agent_runtime_option_id).
        item: WorkItem row (or fake with .agent_runtime_option_id).
        project: ProjectConfig (or fake with .cli_tool and .model).

    Returns:
        The resolved AgentRuntimeOption row.

    Raises:
        RuntimeError: When no option can be resolved (should be impossible
            because the migration enforces exactly one is_default=true row).

    Cascade:
        step override → item override → project.toml lookup → catalogue default
    """
    # Step-level override
    step_opt_id = getattr(step, "agent_runtime_option_id", None)
    if step_opt_id is not None:
        option = _load_option(session, step_opt_id)
        if option is not None:
            if option.enabled:
                logger.debug(
                    "Runtime resolved: step override id=%d (%s, %s)",
                    option.id,
                    option.cli_tool,
                    option.model,
                )
                return option
            logger.warning(
                "Step override id=%d is disabled — skipping and using item/project default",
                step_opt_id,
            )
        # option was None (row deleted) → fall through

    # Item-level override
    item_opt_id = getattr(item, "agent_runtime_option_id", None)
    if item_opt_id is not None:
        option = _load_option(session, item_opt_id)
        if option is not None:
            if option.enabled:
                logger.debug(
                    "Runtime resolved: item override id=%d (%s, %s)",
                    option.id,
                    option.cli_tool,
                    option.model,
                )
                return option
            logger.warning(
                "Item override id=%d is disabled — skipping and using project/catalogue default",
                item_opt_id,
            )
        # None → fall through

    # Project.toml (cli_tool, model) lookup
    cli_tool = getattr(project, "cli_tool", "opencode")
    model = getattr(project, "model", "minimax/MiniMax-M2.7")

    option = _load_option_by_cli_model(session, cli_tool, model)
    if option is not None:
        logger.debug(
            "Runtime resolved: project.toml lookup (%s, %s) → id=%d",
            cli_tool,
            model,
            option.id,
        )
        return option

    # Fallback: catalogue is_default=true row
    option = _load_default(session)
    if option is not None:
        logger.debug(
            "Runtime resolved: catalogue default id=%d (%s, %s)",
            option.id,
            option.cli_tool,
            option.model,
        )
        return option

    # Should be unreachable — migration enforces a default row exists
    raise RuntimeError(
        "resolve_runtime: no option resolved and no is_default=true row found. "
        "Ensure the agent_runtime_options migration has seeded the default row."
    )


def _load_option(session: Session, option_id: int) -> AgentRuntimeOption | None:
    """Load a single AgentRuntimeOption by id, or None if not found."""
    return session.execute(
        select(AgentRuntimeOption).where(AgentRuntimeOption.id == option_id)
    ).scalar_one_or_none()


def _load_option_by_cli_model(
    session: Session, cli_tool: str, model: str
) -> AgentRuntimeOption | None:
    """Load an enabled AgentRuntimeOption by (cli_tool, model) pair.

    Returns None if no enabled row matches.
    """
    return session.execute(
        select(AgentRuntimeOption).where(
            AgentRuntimeOption.cli_tool == cli_tool,
            AgentRuntimeOption.model == model,
            AgentRuntimeOption.enabled.is_(True),
        )
    ).scalar_one_or_none()


def _load_default(session: Session) -> AgentRuntimeOption | None:
    """Load the catalogue default row (is_default=true)."""
    return session.execute(
        select(AgentRuntimeOption).where(AgentRuntimeOption.is_default.is_(True))
    ).scalar_one_or_none()


def resolve_inherited_runtime(
    session: Session,
    *,
    item: object,
    project: object,
) -> AgentRuntimeOption | None:
    """Resolve the runtime option an un-overridden step would inherit.

    This helper answers "what does a step with no explicit step-level override
    actually run?" — identical to what the daemon's ``resolve_runtime()``
    would return for a step carrying no ``agent_runtime_option_id``.

    The cascade is:
        item override → projects.toml (cli_tool, model) lookup → catalogue default

    Args:
        session: Active SQLAlchemy session.
        item: WorkItem row (or fake with .agent_runtime_option_id).
        project: ProjectConfig (or fake with .cli_tool/.model), may be None.

    Returns:
        The resolved ``AgentRuntimeOption`` row, or ``None`` when the catalogue
        has no enabled rows at all (e.g. fresh install before the seed migration
        runs). ``None`` is returned instead of raising so dashboard renders
        degrade gracefully without a 500 on the steps table (AC5).
    """

    # Build a no-step-override sentinel — an object whose
    # agent_runtime_option_id is None so the step-override branch in
    # resolve_runtime() is skipped.
    class _NoStepOverride:
        agent_runtime_option_id: int | None = None

    try:
        return resolve_runtime(
            session,
            step=_NoStepOverride(),
            item=item,
            project=project,
        )
    except RuntimeError:
        # resolve_runtime raises RuntimeError only when the cascade reaches the
        # catalogue default and finds no is_default=true row. This can happen
        # when the seed migration hasn't run yet (empty or partially-seeded
        # catalogue). We degrade gracefully rather than crashing the dashboard.
        return None
