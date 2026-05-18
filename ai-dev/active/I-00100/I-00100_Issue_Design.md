# I-00100: Cascade thrashing detector is dead code in the production daemon path

**Type**: Issue
**Severity**: High
**Created**: 2026-05-18
**Reported By**: Operator (Sergio), discovered while unblocking CR-00057
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt. This incident only touches `orch/daemon/fix_cycle.py` and a new integration test.

## ⛔ Migrations: agents generate, daemon applies

This incident does **NOT** add or modify any Alembic migration. No schema change.

## Description

The cascade thrashing detector exists in code and unit-tests pass, but it never runs in the live daemon: `check_active_fix_cycles` accepts `project_config: ProjectConfig` and marks it `# noqa: ARG001`, so the config never reaches `_complete_fix_cycle`, where the guard `if potential_reset_ids and project_config is not None:` short-circuits. As a result, any cascade-prone fix-cycle (e.g. a browser-verification step the fix agent can't satisfy) replays the full upstream QV-gate set on every attempt — burning ~20 minutes of compute per cycle until the per-step retry cap finally trips.

## Project Context

Read `CLAUDE.md` for architecture, conventions, and hard rules. Per-package guides:
- `orch/CLAUDE.md` — daemon module map, ProjectConfig surface, fix-cycle responsibilities.
- `tests/CLAUDE.md` — testcontainer rules, integration test patterns, live-DB guard, randomly-seed isolation.

The thrashing detector lives in `orch.daemon.fix_cycle._detect_thrashing` and was wired in CR-00040 (the "B.2 thrashing detector" comment at line 1132 names it directly). `ProjectConfig.cascade_thrashing_threshold` (default 3) and `cascade_thrashing_jaccard_min` (default 0.5) are loaded from `projects.toml` by `orch.daemon.project_registry._build_project_config`.

## Steps to Reproduce

1. Approve any work item whose pipeline ends in a `browser_verification` step that the fix agent cannot satisfy with a code patch (e.g. CR-00057 — the seed/registry-sync gap is environmental, but the fix agent classifies it as a code defect per the cycle-prompt warning and patches the wrong layer).
2. Let the daemon run the standard fix-cycle loop. Each failed S15 cycle calls `_complete_fix_cycle`, which calls `_cascade_reset_upstream_qv_gates` to flip every prior QV gate back to `pending`.
3. Inspect `daemon_events` after ≥3 cascades from the same trigger step:
   ```sql
   SELECT event_type, metadata FROM daemon_events
   WHERE entity_id = '<ITEM_ID>'
     AND event_type IN ('cascaded_replay_after_fix', 'cascade_thrashing_detected')
   ORDER BY created_at;
   ```

**Expected**: After the 3rd cascade from the same trigger step with overlapping reset-sets (Jaccard ≥ 0.5), `_detect_thrashing` returns `True`, the cascade reset is suppressed, and a `cascade_thrashing_detected` daemon event is emitted with `cascade_count` and `reset_set`.

**Actual**: Zero `cascade_thrashing_detected` events ever fire. Every consecutive S15 failure triggers a fresh cascade reset of the full upstream gate set. Observed on CR-00057 today: 11 `cascaded_replay_after_fix` rows (4 from S15, 7 from S14), all with reset-set Jaccard 1.0 between consecutive cascades, zero detector events. Item burned ~5 hours of compute before manual operator intervention raised `fix_cycle_max` and reset S14 to pending.

## Root Cause Analysis

The call chain that runs in production is:

1. `orch/daemon/batch_manager.py:109` — `BatchManager` calls `fix_cycle.check_active_fix_cycles(db, self.project_id, self.project_config, self.config)` and **does** pass `project_config`.
2. `orch/daemon/fix_cycle.py:805` — signature: `check_active_fix_cycles(db, project_id, project_config: ProjectConfig, config: DaemonConfig)`. **Both** `project_config` and `config` are marked `# noqa: ARG001` (unused argument), and the body never references them.
3. `orch/daemon/fix_cycle.py:823` — the loop calls `_check_fix_cycle_health(db, cycle, project_id)` — no config passed.
4. `orch/daemon/fix_cycle.py:866` — when the fix-agent PID has exited, `_check_fix_cycle_health` calls `_complete_fix_cycle(db, cycle, project_id, now)` — no `project_config` argument.
5. `orch/daemon/fix_cycle.py:1014` — `_complete_fix_cycle` signature: `_complete_fix_cycle(db, cycle, project_id, now, project_config: ProjectConfig | None = None)`. Default is `None`.
6. `orch/daemon/fix_cycle.py:1139` — guard: `if potential_reset_ids and project_config is not None:` — short-circuits because `project_config` is always `None` on this path.
7. `_detect_thrashing` at line 956 — never called from production. The `_emit_event(..., "cascade_thrashing_detected", ...)` block at line 1160 is unreachable.

The function `_detect_thrashing` itself works (`tests/integration/daemon/test_fix_cycle_thrashing.py` exercises it directly with handcrafted inputs and the unit-level tests pass). The bug is exclusively a *plumbing* defect — the production call chain bypasses the seam the unit tests cover.

Why tests didn't catch this:
- The existing thrashing-detector tests call `_detect_thrashing` directly, never through `check_active_fix_cycles`.
- No integration test simulates the full PID-dead → `_check_fix_cycle_health` → `_complete_fix_cycle` → `_detect_thrashing` chain.
- The `# noqa: ARG001` annotation on `check_active_fix_cycles` is a static-analysis lie — the parameter *is* required for correctness, the linter just can't see the contract.

## Affected Components

| Component | Impact |
|-----------|--------|
| `orch/daemon/fix_cycle.py::check_active_fix_cycles` | Accepts `project_config` but discards it; `# noqa: ARG001` masks the dead argument |
| `orch/daemon/fix_cycle.py::_check_fix_cycle_health` | Receives `(db, cycle, project_id)` only; can never propagate config to `_complete_fix_cycle` |
| `orch/daemon/fix_cycle.py::_complete_fix_cycle` | Default `project_config=None` makes the line-1139 guard always short-circuit in production |
| `orch/daemon/fix_cycle.py::_detect_thrashing` | Implemented and unit-tested, but unreachable from any production call site |
| Operator cost | Cascade-prone items waste ~20 minutes per cycle on full QV-gate replays. CR-00057 lost ~5 hours to this single defect before manual intervention |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | Thread `project_config` from `check_active_fix_cycles` → `_check_fix_cycle_health` → `_complete_fix_cycle`. Drop the `# noqa: ARG001`. No behaviour change beyond enabling the guard at line 1139. | — |
| S02 | code-review-impl | Per-agent review of S01 — verify parameter wiring is correct, no dropped configs elsewhere on this path, no signature break for any test seam | — |
| S03 | tests-impl | New `tests/integration/daemon/test_cascade_thrashing_detector_wiring.py` — drives the full PID-dead path, asserts `cascade_thrashing_detected` event fires on the 3rd same-trigger cascade with overlapping reset-set, and asserts the upstream gates are NOT reset that time | — |
| S04 | code-review-impl | Per-agent review of S03 — verify the test exercises the real production seam (not `_complete_fix_cycle` directly) and uses semantic assertions (specific event_type, specific reset_step_ids) | — |
| S05 | code-review-final-impl | Cross-agent review — final correctness, scope discipline, regression net soundness | — |
| S06 | qv-gate | `make lint` | — |
| S07 | qv-gate | `make format` | — |
| S08 | qv-gate | `make typecheck` | — |
| S09 | qv-gate | `make arch-check` | — |
| S10 | qv-gate | `make security-sast` | — |
| S11 | qv-gate | `make test-unit` | — |
| S12 | qv-gate | `make allure-integration` (timeout 1800s) | — |
| S13 | self-assess-impl | iw-item-analyze on the completed item | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: No Alembic revision. Existing `daemon_events.metadata` JSONB column already carries `cascade_count` / `reset_set` for the `cascade_thrashing_detected` event_type — the column shape stays unchanged.

### Code Changes

- **Files to modify**: `orch/daemon/fix_cycle.py`
- **Files to add**: `tests/integration/daemon/test_cascade_thrashing_detector_wiring.py`
- **Nature of change**: pure plumbing — thread an existing parameter through three function calls, remove a now-incorrect `# noqa: ARG001` annotation.

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `I-00100_Issue_Design.md` | Design | This document |
| `I-00100_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for the orchestrator |
| `prompts/I-00100_S01_Backend_prompt.md` | Prompt | Thread project_config through the call chain |
| `prompts/I-00100_S02_CodeReview_prompt.md` | Prompt | Review S01 |
| `prompts/I-00100_S03_Tests_prompt.md` | Prompt | Integration regression test for the full production seam |
| `prompts/I-00100_S04_CodeReview_prompt.md` | Prompt | Review S03 |
| `prompts/I-00100_S05_CodeReview_Final_prompt.md` | Prompt | Cross-agent global review |
| `prompts/I-00100_S13_SelfAssess_prompt.md` | Prompt | iw-item-analyze self-assessment |

Reports are created during execution under `ai-dev/active/I-00100/reports/`.

## Test to Reproduce

A failing integration test that drives the real production seam (`check_active_fix_cycles`, NOT `_complete_fix_cycle` directly) — proving the detector is unreachable today.

**Test-file location**: `tests/integration/daemon/test_cascade_thrashing_detector_wiring.py` — requires the testcontainer-backed `db_session` because it inspects `daemon_events` and mutates `WorkflowStep` / `FixCycle` rows.

```python
def test_thrashing_detector_fires_when_driven_through_check_active_fix_cycles(
    db_session, project_factory, work_item_with_qv_pipeline_factory
) -> None:
    """RED before I-00100 fix; GREEN after.

    Drives the full production seam:
        check_active_fix_cycles -> _check_fix_cycle_health -> _complete_fix_cycle

    Pre-fix: project_config is dropped at check_active_fix_cycles' boundary
    (# noqa: ARG001), so the line-1139 guard in _complete_fix_cycle short-circuits
    on project_config is None and the detector never runs. This test fails because
    no 'cascade_thrashing_detected' event is emitted even after 3 same-trigger
    cascades with overlapping reset-sets.

    Post-fix: the detector fires on the 3rd cascade and the upstream gates are
    NOT reset that time.
    """
    project = project_factory(
        id="thrashing-probe",
        config={
            "cascade_thrashing_threshold": 3,
            "cascade_thrashing_jaccard_min": 0.5,
            "fix_cycle_max": 10,
        },
    )
    item = work_item_with_qv_pipeline_factory(project, qv_step_ids=["S01", "S02"])

    # Simulate two prior cascades (historical DaemonEvents) so the third — the
    # one we drive synchronously below — is the one that should trip the detector.
    for n in (1, 2):
        _emit_cascade_event(db_session, item, trigger_step_id="S02", reset_set=["S01"])

    # Arrange the third cascade: a fresh in-progress FixCycle on S02 whose PID
    # is already dead (simulating the fix agent having exited).
    s02 = _get_step(db_session, item, "S02")
    cycle = _create_in_progress_fix_cycle(db_session, s02, pid=-1)  # dead PID

    # Act: run the same code path the daemon runs.
    from orch.daemon import fix_cycle
    fix_cycle.check_active_fix_cycles(
        db_session,
        project_id=project.id,
        project_config=_project_config_for(project),
        config=_daemon_config(),
    )

    # Assert (semantic, not shape): the detector event was emitted.
    events = (
        db_session.query(DaemonEvent)
        .filter(DaemonEvent.entity_id == item.id)
        .filter(DaemonEvent.event_type == "cascade_thrashing_detected")
        .all()
    )
    assert len(events) == 1, f"expected detector to fire on 3rd cascade, got {events}"
    meta = events[0].event_metadata
    assert meta["trigger_step_id"] == "S02"
    assert meta["cascade_count"] == 3
    assert set(meta["reset_set"]) == {"S01"}

    # Assert: upstream gate was NOT reset (thrashing suppression worked).
    s01 = _get_step(db_session, item, "S01")
    assert s01.status == StepStatus.completed, (
        "thrashing detector should have suppressed the 3rd cascade reset"
    )
```

## Acceptance Criteria

### AC1: Bug is fixed

```
Given a work item that has fired ≥2 cascaded_replay_after_fix events
  from the same trigger step with overlapping reset-sets (Jaccard ≥ 0.5)
When a third fix-cycle for the same trigger step completes via the
  daemon's check_active_fix_cycles → _check_fix_cycle_health → _complete_fix_cycle path
Then _detect_thrashing returns True, no upstream QV gates are reset,
  and a cascade_thrashing_detected daemon event is emitted with
  cascade_count >= 3 and the overlapping reset_set in metadata
```

### AC2: Regression test exists

```
Given the fix is applied
When tests/integration/daemon/test_cascade_thrashing_detector_wiring.py runs
Then test_thrashing_detector_fires_when_driven_through_check_active_fix_cycles
  passes against the production seam (not the bare _detect_thrashing function)
```

### AC3: No behaviour change for non-thrashing cases

```
Given a fix-cycle completes with project_config provided but the cascade
  pattern does NOT meet the thrashing threshold or jaccard floor
When _complete_fix_cycle runs
Then upstream QV gates ARE reset (unchanged from pre-fix behaviour) and
  no cascade_thrashing_detected event is emitted
```

## Regression Prevention

- **Production seam coverage** — the new integration test drives `check_active_fix_cycles` end-to-end, not `_complete_fix_cycle` in isolation. Future refactors that drop `project_config` again will fail the test instead of silently disabling the safety circuit.
- **`# noqa: ARG001` removal** — keep the annotation off the parameter so any future drop is caught by ruff `ARG001`. Mypy already treats `ProjectConfig | None` as load-bearing here.
- **Assertion strength** — the test asserts on specific event metadata keys (`trigger_step_id`, `cascade_count`, `reset_set`) AND on step status, not just `len(events) > 0`. A weakened detector that emits the event but still resets the gates would still fail AC1.

## Dependencies

- **Depends on**: None
- **Blocks**: Future browser-verification work items that hit unsatisfiable V suites — currently they cascade indefinitely; with I-00100 they halt cleanly after the threshold and emit a `cascade_thrashing_detected` event the operator can act on.

## Impacted Paths

- `orch/daemon/fix_cycle.py`
- `tests/integration/daemon/test_cascade_thrashing_detector_wiring.py`

## TDD Approach

- **Reproducing test**: `test_thrashing_detector_fires_when_driven_through_check_active_fix_cycles` (above). RED before the plumbing fix because `project_config` is dropped at the seam; GREEN after.
- **Unit tests**: existing `_detect_thrashing` unit tests stay green — no signature change to that function.
- **Integration tests**: the new test is the only addition; it lives under `tests/integration/daemon/` and uses the standard testcontainer + `db_session` fixtures (see `tests/CLAUDE.md` for the FTS-DDL bootstrap and the live-DB guard rules).

## Notes

- The fix is a 3-line plumbing change plus one `# noqa` removal. The risk surface is the test, not the fix.
- The operator-applied workaround on CR-00057 (raise `fix_cycle_max` from 5 → 10 and reset S14 to `pending`) is independent of I-00100 — that was about exhausting per-step caps, not about the thrashing detector. Once I-00100 ships, that workaround becomes unnecessary: the detector halts before the per-step cap is even relevant.
- The `_emit_event(..., "cascade_thrashing_detected", ...)` block at `fix_cycle.py:1160` already writes the metadata structure the integration test asserts on. No event-shape changes needed.
