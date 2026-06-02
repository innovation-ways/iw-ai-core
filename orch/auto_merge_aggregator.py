"""Auto-merge aggregator — status, events, verdicts, and token-cost rollups.

Provides read-only aggregation helpers consumed by the auto-merge dashboard
page and API: resolved project config, status snapshots, recent event listing,
verdict rollups, refuse-list breakdowns, health summaries, and token-cost
rollups from DaemonEvent llm_calls metadata.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, Literal, cast

from sqlalchemy import func, or_, select

from orch.db.models import AgentRuntimeOption, AutoMergeProjectConfig, DaemonEvent, MergeAutoVerdict

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from sqlalchemy.sql.elements import ColumnElement

    from orch.daemon.auto_merge import AutoMergeConfig

logger = logging.getLogger(__name__)

AUTO_MERGE_EVENT_PREFIXES: tuple[str, ...] = ("auto_merge_", "merge_auto_")

EVENT_AUTO_MERGE_CONFIG_INVALID = "auto_merge_config_invalid"
EVENT_AUTO_MERGE_HEALTH_PROBE = "auto_merge_health_probe"

SORTABLE_COLUMNS: dict[str, ColumnElement[Any]] = {
    "created_at": cast("ColumnElement[Any]", DaemonEvent.created_at),
    "event_type": cast("ColumnElement[Any]", DaemonEvent.event_type),
    "entity_id": cast("ColumnElement[Any]", DaemonEvent.entity_id),
    "verdict": cast("ColumnElement[Any]", MergeAutoVerdict.verdict),
}


@dataclass(frozen=True)
class ResolvedConfig:
    """Resolved auto-merge configuration for a project, with per-axis provenance.

    Attributes:
        phase: Auto-merge phase (0 or 1).
        runtime_option_id: PK of the resolved AgentRuntimeOption, or None when
            falling back to the hardcoded default.
        cli_tool: CLI tool name (e.g. "opencode" or "claude").
        model: LLM model identifier.
        phase_source: Where the phase value was resolved from.
        runtime_source: Where the runtime was resolved from.
    """

    phase: int
    runtime_option_id: int | None
    cli_tool: str
    model: str
    phase_source: Literal["per_project_db", "toml", "hardcoded"]
    runtime_source: Literal["per_project_db", "toml", "hardcoded"]

    @property
    def source(self) -> Literal["per_project_db", "toml", "hardcoded"]:
        """Derived single-axis source for backwards compatibility.

        Returns ``per_project_db`` if either axis resolved from the DB;
        otherwise falls back to the runtime axis's source. This preserves
        existing chip rendering until the frontend step (S03) migrates the
        chip template to use the per-axis fields independently.
        """
        if self.phase_source == "per_project_db" or self.runtime_source == "per_project_db":
            return "per_project_db"
        return self.runtime_source


@dataclass(frozen=True)
class StatusSnapshot:
    """Point-in-time auto-merge status snapshot for one project.

    Attributes:
        project_id: The project identifier.
        config: Resolved runtime configuration at the time of the snapshot.
        deployed_since: Earliest migration_applied or config_updated event timestamp.
        counts_by_event_type: Event counts grouped by event_type.
        health_state: Overall health classification.
        latest_health_probe_at: Timestamp of the most recent health-probe event.
    """

    project_id: str
    config: ResolvedConfig
    deployed_since: datetime
    counts_by_event_type: dict[str, int]
    health_state: Literal["healthy", "degraded", "down", "unknown"]
    latest_health_probe_at: datetime | None


@dataclass(frozen=True)
class EventRow:
    """Flattened view of a DaemonEvent with its optional MergeAutoVerdict.

    Attributes:
        id: DaemonEvent PK.
        event_type: Event type string.
        entity_id: Entity identifier (work item, batch, etc.), or None.
        message: Human-readable event message, or None.
        metadata: Parsed event_metadata JSON dict.
        created_at: Event creation timestamp.
        verdict: Verdict classification, or None.
        verdict_notes: Free-text verdict notes, or None.
        verdicted_by: Who submitted the verdict, or None.
        verdicted_at: When the verdict was submitted, or None.
    """

    id: int
    event_type: str
    entity_id: str | None
    message: str | None
    metadata: dict[str, object]
    created_at: datetime
    verdict: str | None
    verdict_notes: str | None
    verdicted_by: str | None
    verdicted_at: datetime | None


@dataclass(frozen=True)
class VerdictRollup:
    """Verdict outcome counts for a sliding time window.

    Attributes:
        window: Time window identifier ("7d" or "30d").
        pending: Count of pending verdicts.
        correct: Count of correct verdicts.
        wrong: Count of wrong verdicts.
        partial: Count of partial verdicts.
    """

    window: Literal["7d", "30d"]
    pending: int
    correct: int
    wrong: int
    partial: int


@dataclass(frozen=True)
class RefuseListEntry:
    """Single reason entry from the auto-merge refuse-list breakdown.

    Attributes:
        reason: The reason code for refusal (e.g. "no_design_doc").
        count: Number of skips with this reason in the window.
    """

    reason: str
    count: int


@dataclass(frozen=True)
class HealthSummary:
    """Auto-merge runtime health summary.

    Attributes:
        state: Overall health classification.
        latest_probe_at: Timestamp of the most recent probe, or None.
        latest_probe_runtime_reachable: Whether the runtime was reachable in
            the most recent probe, or None when no probe has been recorded.
        failures_last_24h: Number of failed probes in the last 24 hours.
        threshold_per_day: Configured failure threshold per day (from toml).
    """

    state: Literal["healthy", "degraded", "down", "unknown"]
    latest_probe_at: datetime | None
    latest_probe_runtime_reachable: bool | None
    failures_last_24h: int
    threshold_per_day: int


@dataclass(frozen=True)
class TokenCostRollup:
    """LLM token-cost rollup for a sliding time window.

    Attributes:
        window: Time window identifier ("7d" or "30d").
        total_input_tokens: Total input tokens consumed.
        total_output_tokens: Total output tokens consumed.
        total_cost_usd: Estimated total cost in USD.
        breakdown_by_model: Per-model dict with keys "input", "output", "cost".
        has_unknown_models: True when at least one model had no known pricing.
    """

    window: Literal["7d", "30d"]
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: float
    breakdown_by_model: dict[str, dict[str, int | float]]
    has_unknown_models: bool


MODEL_PRICING: dict[str, dict[str, float]] = {
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "claude-opus-4-7": {"input": 15.00, "output": 75.00},
    "openai/gpt-5.3-codex": {"input": 5.00, "output": 20.00},
    "minimax/MiniMax-M2.7": {"input": 0.20, "output": 1.00},
}


def _window_days(window: Literal["7d", "30d"]) -> int:
    """Return the integer number of days for a window identifier."""
    return 7 if window == "7d" else 30


def _default_runtime(db: Session) -> AgentRuntimeOption | None:
    """Return the default enabled AgentRuntimeOption row, or None if none is set."""
    return db.execute(
        select(AgentRuntimeOption)
        .where(AgentRuntimeOption.is_default.is_(True))
        .where(AgentRuntimeOption.enabled.is_(True))
        .limit(1)
    ).scalar_one_or_none()


def _runtime_by_id(db: Session, runtime_id: int | None) -> AgentRuntimeOption | None:
    """Return the AgentRuntimeOption for the given PK, or None when id is None."""
    if runtime_id is None:
        return None
    return db.get(AgentRuntimeOption, runtime_id)


def _maybe_emit_disabled_runtime_event(
    db: Session, project_id: str, runtime_option_id: int
) -> None:
    """Emit a config-invalid event when the configured runtime is disabled, deduplicating."""
    latest = db.execute(
        select(DaemonEvent)
        .where(DaemonEvent.project_id == project_id)
        .where(DaemonEvent.event_type == EVENT_AUTO_MERGE_CONFIG_INVALID)
        .order_by(DaemonEvent.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if (
        latest is not None
        and isinstance(latest.event_metadata, dict)
        and latest.event_metadata.get("reason") == "runtime_option_disabled"
        and latest.event_metadata.get("configured_id") == runtime_option_id
    ):
        return

    db.add(
        DaemonEvent(
            project_id=project_id,
            event_type=EVENT_AUTO_MERGE_CONFIG_INVALID,
            entity_id=None,
            entity_type=None,
            message="runtime disabled — falling back",
            event_metadata={
                "project_id": project_id,
                "configured_id": runtime_option_id,
                "reason": "runtime_option_disabled",
            },
        )
    )
    db.commit()


def resolve_project_config(
    db: Session, project_id: str, toml_config: AutoMergeConfig
) -> ResolvedConfig:
    """Resolve the effective auto-merge config for a project with per-axis provenance.

    Priority layers for phase: per_project_db > toml > hardcoded (0).
    Priority layers for runtime: per_project_db > toml > default DB row > hardcoded fallback.
    Disabled runtimes are skipped and a config-invalid event is emitted once per unique case.

    Args:
        db: SQLAlchemy session.
        project_id: Project identifier.
        toml_config: Parsed toml-level auto-merge config for this project.

    Returns:
        ResolvedConfig with both the effective values and their provenance.
    """
    db_row = db.get(AutoMergeProjectConfig, project_id)

    # Determine phase source before any fallback
    if db_row is not None and db_row.phase is not None:
        phase_source: Literal["per_project_db", "toml", "hardcoded"] = "per_project_db"
    else:
        phase_source = "toml"

    phase = db_row.phase if db_row is not None and db_row.phase is not None else toml_config.phase
    if phase not in (0, 1):
        # phase_source is preserved so a CR/test can verify this warning fires
        # when phase_source=='per_project_db' and the value fell back to 0.
        logger.warning(
            "[auto_merge_config] project=%s invalid phase=%s from %s — falling back to 0",
            project_id,
            phase,
            phase_source,
        )
        phase = 0

    runtime_layers: list[tuple[Literal["per_project_db", "toml", "hardcoded"], int | None]] = []
    if db_row is not None and db_row.runtime_option_id is not None:
        runtime_layers.append(("per_project_db", db_row.runtime_option_id))
    runtime_layers.append(("toml", toml_config.runtime_option_id))
    runtime_layers.append(("hardcoded", None))

    for runtime_source, runtime_id in runtime_layers:
        runtime = _runtime_by_id(db, runtime_id) if runtime_id is not None else None
        if runtime_id is not None and (runtime is None or not runtime.enabled):
            if runtime_source == "per_project_db":
                logger.warning(
                    "[auto_merge_config] project=%s runtime_option_id=%s disabled — falling back",
                    project_id,
                    runtime_id,
                )
                _maybe_emit_disabled_runtime_event(db, project_id, runtime_id)
            continue
        if runtime is None:
            runtime = _default_runtime(db)
        if runtime is None:
            return ResolvedConfig(
                phase=phase,
                runtime_option_id=None,
                cli_tool="opencode",
                model="openai/gpt-5.3-codex",
                phase_source=phase_source,
                runtime_source=runtime_source,
            )
        return ResolvedConfig(
            phase=phase,
            runtime_option_id=runtime.id,
            cli_tool=runtime.cli_tool,
            model=runtime.model,
            phase_source=phase_source,
            runtime_source=runtime_source,
        )

    fallback = _default_runtime(db)
    return ResolvedConfig(
        phase=0,
        runtime_option_id=fallback.id if fallback else None,
        cli_tool=fallback.cli_tool if fallback else "opencode",
        model=fallback.model if fallback else "openai/gpt-5.3-codex",
        phase_source="hardcoded",
        runtime_source="hardcoded",
    )


def get_status_snapshot(
    db: Session, project_id: str, toml_config: AutoMergeConfig
) -> StatusSnapshot:
    """Build a StatusSnapshot for the given project.

    Args:
        db: SQLAlchemy session.
        project_id: Project identifier.
        toml_config: Parsed toml-level auto-merge config for this project.

    Returns:
        StatusSnapshot with resolved config, event counts, and health state.
    """
    config = resolve_project_config(db, project_id, toml_config)
    deployed_since = db.execute(
        select(func.min(DaemonEvent.created_at))
        .where(DaemonEvent.project_id == project_id)
        .where(DaemonEvent.event_type.in_(["migration_applied", "auto_merge_config_updated"]))
    ).scalar_one_or_none() or datetime.now(UTC)
    count_rows = db.execute(
        select(DaemonEvent.event_type, func.count())
        .where(DaemonEvent.project_id == project_id)
        .where(DaemonEvent.created_at >= deployed_since)
        .group_by(DaemonEvent.event_type)
    ).all()
    counts: dict[str, int] = {str(row[0]): int(row[1]) for row in count_rows}
    health = get_health_summary(db, project_id, toml_config)
    return StatusSnapshot(
        project_id=project_id,
        config=config,
        deployed_since=deployed_since,
        counts_by_event_type=counts,
        health_state=health.state,
        latest_health_probe_at=health.latest_probe_at,
    )


def list_recent_events(
    db: Session,
    project_id: str,
    *,
    page: int = 0,
    page_size: int = 50,
    event_type_filter: str | None = None,
    sort: str = "created_at",
    direction: str = "desc",
    include_non_auto_merge: bool = False,
) -> tuple[list[EventRow], int]:
    """List auto-merge events with optional filtering, sorting, and pagination.

    Args:
        db: SQLAlchemy session.
        project_id: Project identifier.
        page: Zero-based page index.
        page_size: Number of rows per page.
        event_type_filter: When set, filter to exactly this event_type.
        sort: Column to sort by; must be a key in SORTABLE_COLUMNS.
        direction: Sort direction ("asc" or "desc").
        include_non_auto_merge: When True, include all event types; otherwise
            only events whose type starts with an AUTO_MERGE_EVENT_PREFIXES entry.

    Returns:
        Tuple of (list of EventRow, total row count before pagination).

    Raises:
        ValueError: If sort or direction is invalid.
    """
    if sort not in SORTABLE_COLUMNS:
        raise ValueError(f"sort must be one of {sorted(SORTABLE_COLUMNS)}; got {sort!r}")
    if direction not in ("asc", "desc"):
        raise ValueError(f"direction must be 'asc' or 'desc'; got {direction!r}")

    stmt = (
        select(DaemonEvent, MergeAutoVerdict)
        .outerjoin(
            MergeAutoVerdict,
            (MergeAutoVerdict.project_id == DaemonEvent.project_id)
            & (MergeAutoVerdict.daemon_event_id == DaemonEvent.id),
        )
        .where(DaemonEvent.project_id == project_id)
    )
    if event_type_filter:
        stmt = stmt.where(DaemonEvent.event_type == event_type_filter)
    elif not include_non_auto_merge:
        stmt = stmt.where(
            or_(*(DaemonEvent.event_type.like(p + "%") for p in AUTO_MERGE_EVENT_PREFIXES))
        )

    col = SORTABLE_COLUMNS[sort]
    order = col.asc() if direction == "asc" else col.desc()
    if sort == "verdict":
        order = order.nulls_last()

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = db.execute(stmt.order_by(order).offset(page * page_size).limit(page_size)).all()
    return [
        EventRow(
            id=event.id,
            event_type=event.event_type,
            entity_id=event.entity_id,
            message=event.message,
            metadata=event.event_metadata or {},
            created_at=event.created_at,
            verdict=verdict.verdict if verdict else None,
            verdict_notes=verdict.verdict_notes if verdict else None,
            verdicted_by=verdict.verdicted_by if verdict else None,
            verdicted_at=verdict.verdicted_at if verdict else None,
        )
        for event, verdict in rows
    ], total


def get_event_detail(db: Session, project_id: str, event_id: int) -> EventRow | None:
    """Return an EventRow for a single event by id, or None when not found.

    Args:
        db: SQLAlchemy session.
        project_id: Project identifier (scopes the lookup).
        event_id: DaemonEvent primary key.

    Returns:
        EventRow with verdict fields populated if a verdict exists, else None.
    """
    row = db.execute(
        select(DaemonEvent, MergeAutoVerdict)
        .outerjoin(
            MergeAutoVerdict,
            (MergeAutoVerdict.project_id == DaemonEvent.project_id)
            & (MergeAutoVerdict.daemon_event_id == DaemonEvent.id),
        )
        .where(DaemonEvent.project_id == project_id)
        .where(DaemonEvent.id == event_id)
        .limit(1)
    ).first()
    if row is None:
        return None
    event, verdict = row
    return EventRow(
        id=event.id,
        event_type=event.event_type,
        entity_id=event.entity_id,
        message=event.message,
        metadata=event.event_metadata or {},
        created_at=event.created_at,
        verdict=verdict.verdict if verdict else None,
        verdict_notes=verdict.verdict_notes if verdict else None,
        verdicted_by=verdict.verdicted_by if verdict else None,
        verdicted_at=verdict.verdicted_at if verdict else None,
    )


def get_verdict_rollup(db: Session, project_id: str, window: Literal["7d", "30d"]) -> VerdictRollup:
    """Count verdicts by outcome for the given project and time window.

    Args:
        db: SQLAlchemy session.
        project_id: Project identifier.
        window: Time window ("7d" or "30d").

    Returns:
        VerdictRollup with pending, correct, wrong, and partial counts.
    """
    since_expr = func.now() - timedelta(days=_window_days(window))
    rows = db.execute(
        select(MergeAutoVerdict.verdict, func.count())
        .join(DaemonEvent, DaemonEvent.id == MergeAutoVerdict.daemon_event_id)
        .where(MergeAutoVerdict.project_id == project_id)
        .where(DaemonEvent.created_at >= since_expr)
        .group_by(MergeAutoVerdict.verdict)
    ).all()
    counts: dict[str, int] = {str(row[0]): int(row[1]) for row in rows}
    return VerdictRollup(
        window=window,
        pending=int(counts.get("pending", 0)),
        correct=int(counts.get("correct", 0)),
        wrong=int(counts.get("wrong", 0)),
        partial=int(counts.get("partial", 0)),
    )


def get_refuse_list_breakdown(
    db: Session, project_id: str, window: Literal["7d", "30d"]
) -> list[RefuseListEntry]:
    """Return per-reason counts of auto-merge skips for the given window.

    Args:
        db: SQLAlchemy session.
        project_id: Project identifier.
        window: Time window ("7d" or "30d").

    Returns:
        List of RefuseListEntry sorted by count descending.
    """
    since_expr = func.now() - timedelta(days=_window_days(window))
    rows = db.execute(
        select(DaemonEvent.event_metadata["reason"].astext, func.count())
        .where(DaemonEvent.project_id == project_id)
        .where(DaemonEvent.event_type == "merge_auto_resolution_skipped")
        .where(DaemonEvent.created_at >= since_expr)
        .group_by(DaemonEvent.event_metadata["reason"].astext)
    ).all()
    return [RefuseListEntry(reason=reason or "unknown", count=count) for reason, count in rows]


def get_health_summary(db: Session, project_id: str, toml_config: AutoMergeConfig) -> HealthSummary:
    """Compute the auto-merge runtime health summary for a project.

    Args:
        db: SQLAlchemy session.
        project_id: Project identifier.
        toml_config: Parsed toml-level auto-merge config (provides the threshold).

    Returns:
        HealthSummary with state, latest probe info, and 24h failure count.
    """
    latest = db.execute(
        select(DaemonEvent)
        .where(DaemonEvent.project_id == project_id)
        .where(DaemonEvent.event_type == EVENT_AUTO_MERGE_HEALTH_PROBE)
        .order_by(DaemonEvent.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    since_expr = func.now() - timedelta(days=1)
    failures = db.execute(
        select(func.count())
        .where(DaemonEvent.project_id == project_id)
        .where(DaemonEvent.event_type == EVENT_AUTO_MERGE_HEALTH_PROBE)
        .where(DaemonEvent.created_at >= since_expr)
        .where(DaemonEvent.event_metadata["runtime_reachable"].astext == "false")
    ).scalar_one()
    if latest is None:
        state: Literal["healthy", "degraded", "down", "unknown"] = "unknown"
        reachable = None
    else:
        reachable = bool((latest.event_metadata or {}).get("runtime_reachable"))
        threshold = int(toml_config.health_failure_rate_threshold_per_day)
        if reachable and failures == 0:
            state = "healthy"
        elif failures > threshold:
            state = "down"
        else:
            state = "degraded"
    return HealthSummary(
        state=state,
        latest_probe_at=latest.created_at if latest else None,
        latest_probe_runtime_reachable=reachable,
        failures_last_24h=int(failures),
        threshold_per_day=toml_config.health_failure_rate_threshold_per_day,
    )


def get_token_cost_rollup(
    db: Session, project_id: str, window: Literal["7d", "30d"]
) -> TokenCostRollup:
    """Aggregate LLM token usage and estimated cost from event metadata.

    Reads ``llm_calls`` from DaemonEvent.event_metadata for events in the
    window, applies MODEL_PRICING per-model, and returns totals and a
    per-model breakdown.

    Args:
        db: SQLAlchemy session.
        project_id: Project identifier.
        window: Time window ("7d" or "30d").

    Returns:
        TokenCostRollup with totals and per-model breakdown.
    """
    since_expr = func.now() - timedelta(days=_window_days(window))
    events = db.scalars(
        select(DaemonEvent)
        .where(DaemonEvent.project_id == project_id)
        .where(DaemonEvent.created_at >= since_expr)
    ).all()
    total_input = 0
    total_output = 0
    total_cost = 0.0
    by_model: dict[str, dict[str, int | float]] = {}
    unknown = False
    for event in events:
        llm_calls = (event.event_metadata or {}).get("llm_calls", [])
        if not isinstance(llm_calls, list):
            continue
        for call in llm_calls:
            if not isinstance(call, dict):
                continue
            model = str(call.get("model") or "unknown")
            inp = int(call.get("input_tokens") or 0)
            out = int(call.get("output_tokens") or 0)
            pricing = MODEL_PRICING.get(model)
            if pricing is None:
                unknown = True
                cost = 0.0
            else:
                cost = (inp / 1_000_000.0) * pricing["input"] + (out / 1_000_000.0) * pricing[
                    "output"
                ]
            total_input += inp
            total_output += out
            total_cost += cost
            bucket = by_model.setdefault(model, {"input": 0, "output": 0, "cost": 0.0})
            bucket["input"] = int(bucket["input"]) + inp
            bucket["output"] = int(bucket["output"]) + out
            bucket["cost"] = float(bucket["cost"]) + cost
    return TokenCostRollup(
        window=window,
        total_input_tokens=total_input,
        total_output_tokens=total_output,
        total_cost_usd=round(total_cost, 8),
        breakdown_by_model=by_model,
        has_unknown_models=unknown,
    )
