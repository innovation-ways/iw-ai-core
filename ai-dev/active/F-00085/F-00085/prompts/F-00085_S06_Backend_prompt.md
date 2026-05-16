# F-00085_S06_Backend_prompt

**Work Item**: F-00085
**Step**: S06
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. NO migrations in this step.

## Input Files

- `ai-dev/active/F-00085/F-00085_Feature_Design.md` — Acceptance Criteria, Boundary Behavior, Invariants
- Canonical reference: `ai-dev/active/AUTO_MERGE_RESOLUTION.md` §5b
- S01 deliverables (already merged): `merge_auto_verdicts` + `auto_merge_project_config` tables + ORM models
- S04 deliverables (already merged): `[health]` TOML section + loader extension + `EVENT_AUTO_MERGE_HEALTH_PROBE` / `EVENT_AUTO_MERGE_CONFIG_UPDATED` constants
- Existing patterns to study:
  - `orch/jobs/aggregator.py` — read-only aggregator pattern; query factoring; how it joins across tables
  - `orch/daemon/auto_merge.py` — F-00084's structure for AutoMergeConfig, classify_conflicts, attempt_resolution
  - `orch/daemon/merge_queue.py` — the merge-flow integration point at line ~482
  - `orch/daemon/main.py` — daemon poll loop; how background tasks are wired
  - `orch/daemon/migration_rebase.py` — pattern for subprocess + DB-state daemon tasks

## Output Files

- `ai-dev/active/F-00085/reports/F-00085_S06_Backend_report.md`

## Context

You are implementing the backend logic. THREE deliverables:

1. New module `orch/auto_merge_aggregator.py` — read-only queries + config resolution + per-model pricing
2. New module `orch/daemon/auto_merge_health.py` — daemon-scheduled health probe task
3. Update `orch/daemon/auto_merge.py` AND `orch/daemon/merge_queue.py` to use `resolve_project_config()`

You do NOT touch the dashboard layer in this step (S08/S10).

## Requirements

### 1. `orch/auto_merge_aggregator.py` — public surface

```python
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal
from sqlalchemy.orm import Session

# Resolved configuration for a project
@dataclass(frozen=True)
class ResolvedConfig:
    phase: int                          # 0 or 1
    runtime_option_id: int | None       # explicit DB or TOML; None → project default
    cli_tool: str                       # resolved via agent_runtime_options lookup
    model: str                          # resolved via agent_runtime_options lookup
    source: Literal["per_project_db", "toml", "hardcoded"]   # which layer won

@dataclass(frozen=True)
class StatusSnapshot:
    project_id: str
    config: ResolvedConfig
    deployed_since: datetime           # first non-null timestamp from auto_merge_project_config or migration apply
    counts_by_event_type: dict[str, int]   # since deployed_since
    health_state: Literal["healthy", "degraded", "down", "unknown"]
    latest_health_probe_at: datetime | None

@dataclass(frozen=True)
class EventRow:
    id: int
    event_type: str
    entity_id: str | None
    message: str | None
    metadata: dict
    created_at: datetime
    verdict: str | None                 # joined from merge_auto_verdicts (None → no verdict yet)
    verdict_notes: str | None
    verdicted_by: str | None
    verdicted_at: datetime | None

@dataclass(frozen=True)
class VerdictRollup:
    window: Literal["7d", "30d"]
    pending: int
    correct: int
    wrong: int
    partial: int

@dataclass(frozen=True)
class RefuseListEntry:
    reason: str                         # event_metadata.reason value
    count: int

@dataclass(frozen=True)
class HealthSummary:
    state: Literal["healthy", "degraded", "down", "unknown"]
    latest_probe_at: datetime | None
    latest_probe_runtime_reachable: bool | None
    failures_last_24h: int
    threshold_per_day: int

@dataclass(frozen=True)
class TokenCostRollup:
    window: Literal["7d", "30d"]
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: float
    breakdown_by_model: dict[str, dict[str, int | float]]   # model -> {input, output, cost}
    has_unknown_models: bool

# Per-model pricing (USD per 1M tokens). Update when provider pricing changes.
MODEL_PRICING: dict[str, dict[str, float]] = {
    "claude-sonnet-4-6":   {"input": 3.00,  "output": 15.00},
    "claude-opus-4-7":     {"input": 15.00, "output": 75.00},
    "openai/gpt-5.3-codex":{"input": 5.00,  "output": 20.00},
    "minimax/MiniMax-M2.7":{"input": 0.20,  "output": 1.00},
}

def resolve_project_config(db: Session, project_id: str, toml_config) -> ResolvedConfig:
    """Resolution order: per-project DB row > TOML > hardcoded defaults.

    Resolves runtime_option_id → (cli_tool, model) via agent_runtime_options.
    If the resolved runtime is disabled, falls through to the next layer with
    a 'runtime disabled — falling back' annotation (caller logs it).
    """

def get_status_snapshot(db: Session, project_id: str, toml_config) -> StatusSnapshot: ...
def list_recent_events(
    db: Session, project_id: str, *, page: int = 0, page_size: int = 50,
    event_type_filter: str | None = None,
) -> tuple[list[EventRow], int]:  # (rows, total)
    ...
def get_event_detail(db: Session, project_id: str, event_id: int) -> EventRow | None: ...
def get_verdict_rollup(db: Session, project_id: str, window: Literal["7d", "30d"]) -> VerdictRollup: ...
def get_refuse_list_breakdown(db: Session, project_id: str, window: Literal["7d", "30d"]) -> list[RefuseListEntry]: ...
def get_health_summary(db: Session, project_id: str, toml_config) -> HealthSummary: ...
def get_token_cost_rollup(db: Session, project_id: str, window: Literal["7d", "30d"]) -> TokenCostRollup: ...
```

**Implementation notes**:

- All queries scope by `project_id` (multi-project isolation per `orch/CLAUDE.md`).
- Window strings translate to `timedelta(days=7)` / `timedelta(days=30)` and filter on `created_at >= now() - window`.
- `event_metadata` queries use PostgreSQL JSONB operators (`->>`, `->`). Sample: `DaemonEvent.event_metadata['reason'].astext`.
- `list_recent_events` LEFT JOINs `merge_auto_verdicts` so each row carries its verdict (or NULL).
- `get_token_cost_rollup` walks `event_metadata.llm_calls` (a JSON array); use `func.jsonb_array_elements` + `jsonb_to_recordset` style — or pull metadata into Python and aggregate there (acceptable for the expected volume).
- `MODEL_PRICING` lookup MUST be a strict dict — unknown model returns `0.0` cost and the rollup's `has_unknown_models = True`.
- `resolve_project_config` MUST be deterministic (Invariant 2) — no `datetime.now()`, no random, no I/O beyond the passed DB session.
- When `resolve_project_config` finds a per-project row with `runtime_option_id` pointing at a disabled row in `agent_runtime_options`, fall through to TOML layer; log a WARNING; emit an `auto_merge_config_invalid` event so the dashboard can surface "runtime disabled — falling back".

### 2. `orch/daemon/auto_merge_health.py` — probe task

```python
from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess
import logging

from sqlalchemy.orm import Session
from orch.db.models import DaemonEvent
from orch.daemon.auto_merge import AutoMergeConfig, EVENT_AUTO_MERGE_HEALTH_PROBE
from orch.auto_merge_aggregator import resolve_project_config

logger = logging.getLogger(__name__)

PROBE_PROMPT = "Reply with the single word OK."

def maybe_run_probe(db: Session, project_id: str, toml_config: AutoMergeConfig) -> None:
    """If the last auto_merge_health_probe event for this project is older than
    toml_config.health_probe_interval_seconds, fire a probe and record the event.

    Idempotent: if a recent probe exists, no-op.
    Non-blocking: subprocess timeout = max(15s, probe_interval_seconds // 4).
    """
    resolved = resolve_project_config(db, project_id, toml_config)
    if resolved.phase == 0:
        return  # No probe when phase=0; chip won't render anyway.

    # Find latest probe
    latest = db.execute(
        select(DaemonEvent)
        .where(DaemonEvent.project_id == project_id)
        .where(DaemonEvent.event_type == EVENT_AUTO_MERGE_HEALTH_PROBE)
        .order_by(DaemonEvent.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    interval = timedelta(seconds=toml_config.health_probe_interval_seconds)
    now = datetime.now(timezone.utc)
    if latest is not None and (now - latest.created_at) < interval:
        return

    start = time.monotonic()
    error: str | None = None
    reachable = False
    try:
        # Invoke step_executor.sh in one-shot mode (F-00084's auto_merge_resolve path).
        # The prompt is "Reply with the single word OK." — minimal token spend.
        result = subprocess.run(
            ["bash", str(EXECUTOR_PATH / "step_executor.sh"),
             "--step-type", "auto_merge_resolve",
             "--agent", resolved.cli_tool,
             "--model", resolved.model],
            input=PROBE_PROMPT,
            text=True,
            capture_output=True,
            timeout=max(15, toml_config.health_probe_interval_seconds // 4),
        )
        if result.returncode == 0 and "OK" in result.stdout:
            reachable = True
        else:
            error = (result.stderr or result.stdout)[:1024]
    except subprocess.TimeoutExpired:
        error = "timeout"
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"

    duration_ms = int((time.monotonic() - start) * 1000)

    db.add(DaemonEvent(
        project_id=project_id,
        event_type=EVENT_AUTO_MERGE_HEALTH_PROBE,
        entity_id=None,
        entity_type=None,
        message=None,
        event_metadata={
            "runtime_reachable": reachable,
            "cli_tool": resolved.cli_tool,
            "model": resolved.model,
            "probe_duration_ms": duration_ms,
            "error": error,
        },
    ))
    db.commit()
    logger.info(
        "[auto_merge_health] project=%s reachable=%s duration_ms=%d error=%s",
        project_id, reachable, duration_ms, error,
    )
```

### 3. Update `orch/daemon/main.py` poll loop

After each poll iteration, for each ENABLED project, call `maybe_run_probe(db, project.id, toml_config)`. This is fire-and-forget per Invariant 7 (non-blocking on merge queue).

Place the call AFTER the merge-queue processing AND batch processing, so probes never delay actual work. Wrap in try/except → log + continue.

### 4. Update `orch/daemon/auto_merge.py` to use `resolve_project_config`

Where F-00084 currently reads `config.phase` and `config.runtime_option_id` directly from the TOML, route through `resolve_project_config(db, project_id, toml_config)` to get the resolved view.

Specifically:
- `attempt_resolution()`: change the Phase-0 short-circuit check to read `resolved.phase == 0` (not `toml_config.phase == 0`).
- `_resolve_runtime_option()`: change to prefer `resolved.runtime_option_id` if set; only fall back to project default when resolved is None.

### 5. Update `orch/daemon/merge_queue.py`

Where F-00084's code reads `executor/auto_merge.toml` directly (line ~485), keep that, but route the loaded config through `resolve_project_config(db, project_id, toml_config)` before calling `auto_merge.attempt_resolution`.

### 6. Emit `auto_merge_config_invalid` when the per-project runtime is disabled

In `resolve_project_config`, when the per-project DB row's `runtime_option_id` points at a disabled `agent_runtime_options` row, emit a `auto_merge_config_invalid` DaemonEvent with metadata `{project_id, configured_id, reason: "runtime_option_disabled"}`. The aggregator's status snapshot surfaces this via the chip annotation.

Be careful: don't emit duplicate events for the same project on every merge — only emit when transitioning from "valid" to "invalid". Track via a module-level cache or by checking the latest existing event.

### 7. NO daemon poll loop in `auto_merge_health.py`

The probe task is a **function** that the daemon `main.py` poll loop calls. It is NOT a separate thread or asyncio task. F-00084's pattern: keep daemon single-threaded.

## Project Conventions

- Read `orch/CLAUDE.md` and `orch/jobs/aggregator.py` for the aggregator pattern.
- Sync SQLAlchemy — no `async def`.
- `DaemonEvent.metadata` is accessed as `.event_metadata` in Python.
- Subprocess invocations use `# noqa: S603, S607` consistent with existing code.
- `logger = logging.getLogger(__name__)` — no custom config.

## TDD Requirement

Write RED tests in `tests/unit/test_auto_merge_aggregator.py`, `tests/unit/test_auto_merge_config_resolution.py`, `tests/unit/test_auto_merge_health.py`, `tests/unit/test_auto_merge_pricing.py` BEFORE implementing. Each new public function gets at least one RED test asserting its contract. Run them to confirm RED (most will fail with `ImportError` or `AttributeError`). Then GREEN them.

S13 will expand these into comprehensive coverage; your job here is enough to drive your own implementation.

`tdd_red_evidence` must record at least one captured RED failure line.

## Pre-flight Quality Gates

1. `make format`.
2. `make typecheck`.
3. `make lint`.
4. Targeted unit tests: `uv run pytest tests/unit/test_auto_merge_*.py -v`.

## Test Verification

- Run only `tests/unit/test_auto_merge_*.py` and any `tests/unit/test_merge_queue.py` you affected.
- Do NOT run `make test-integration` (S21's job).

## Subagent Result Contract

```json
{
  "step": "S06",
  "agent": "backend-impl",
  "work_item": "F-00085",
  "completion_status": "complete",
  "files_changed": [
    "orch/auto_merge_aggregator.py",
    "orch/daemon/auto_merge_health.py",
    "orch/daemon/auto_merge.py",
    "orch/daemon/merge_queue.py",
    "orch/daemon/main.py",
    "tests/unit/test_auto_merge_aggregator.py",
    "tests/unit/test_auto_merge_config_resolution.py",
    "tests/unit/test_auto_merge_health.py",
    "tests/unit/test_auto_merge_pricing.py"
  ],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed (targeted unit tests for aggregator + health + config resolution + pricing)",
  "tdd_red_evidence": "tests/unit/test_auto_merge_config_resolution.py::test_per_project_db_row_overrides_toml — ImportError: cannot import name 'resolve_project_config' from 'orch.auto_merge_aggregator'",
  "blockers": [],
  "notes": "Aggregator + health task + config resolution complete. Per-project DB override now drives both attempt_resolution() and merge_queue.py. Phase-0 short-circuit moves from TOML-only to resolved-config (still safe-by-default). MODEL_PRICING covers all currently-enabled agent_runtime_options rows; unknown models contribute $0 and set has_unknown_models=True."
}
```
