# F-00085_S04_Pipeline_prompt

**Work Item**: F-00085
**Step**: S04
**Agent**: pipeline-impl

---

## ⛔ Docker is off-limits

Standard policy.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. No migrations in this step.

## Input Files

- `ai-dev/active/F-00085/F-00085_Feature_Design.md`
- F-00084's `executor/auto_merge.toml` (already on main)
- F-00084's `orch/daemon/auto_merge.py` — `AutoMergeConfig` class (~line 130) and `AutoMergeConfig.load()` (~line 159)

## Output Files

- `ai-dev/active/F-00085/reports/F-00085_S04_Pipeline_report.md`

## Context

Add a `[health]` section to `executor/auto_merge.toml` and extend the TOML loader in `orch/daemon/auto_merge.py` to parse it. The aggregator (S06) will use these values to drive the daemon's health probe.

## Requirements

### 1. Append `[health]` section to `executor/auto_merge.toml`

```toml
[health]
# F-00085: daemon-scheduled health-probe knobs.
# The probe is a no-op LLM call ("Reply with the single word OK") issued
# via the configured runtime, once per probe_interval_seconds per enabled
# project. The result is recorded as an auto_merge_health_probe DaemonEvent.
# Cost ≈ 50 tokens / probe × 288 probes/day at default interval.

# Seconds between probe attempts per project. Increase to reduce idle cost.
probe_interval_seconds = 300

# If more than this many auto_merge_resolution_failed events fire in a
# rolling 24h window, the status chip turns yellow ⚠. Default 3.
failure_rate_threshold_per_day = 3
```

### 2. Extend `AutoMergeConfig` in `orch/daemon/auto_merge.py`

Add two new fields with defaults matching the TOML above:

```python
@dataclass(frozen=True)
class AutoMergeConfig:
    # ...existing fields...
    health_probe_interval_seconds: int = 300
    health_failure_rate_threshold_per_day: int = 3
```

Extend `AutoMergeConfig.load()` to parse the new section:

```python
health = data.get("health", {})
health_probe_interval_seconds = int(health.get("probe_interval_seconds", 300))
health_failure_rate_threshold_per_day = int(health.get("failure_rate_threshold_per_day", 3))
```

Update `AutoMergeConfig.defaults()` to include the new fields with the same defaults.

### 3. Define new event-type string constants

Add two module-level constants near the existing `EVENT_*` constants in `orch/daemon/auto_merge.py`:

```python
EVENT_AUTO_MERGE_HEALTH_PROBE = "auto_merge_health_probe"
EVENT_AUTO_MERGE_CONFIG_UPDATED = "auto_merge_config_updated"
```

These are the event_type strings the daemon health task (S06) and the config-POST endpoint (S08) will use.

### 4. Back-compat

When the `[health]` section is absent (e.g., on existing deployments that haven't picked up the new TOML), the loader MUST default to `probe_interval_seconds = 300` and `failure_rate_threshold_per_day = 3`. The Phase 0/1 plumbing from F-00084 MUST continue to work unchanged.

### 5. NO daemon wiring in this step

The actual probe-task wiring lives in S06 (`orch/daemon/auto_merge_health.py`). S04's responsibility ends at the config surface + parsing.

## Project Conventions

- Match F-00084's existing TOML comment style (descriptive, operator-facing).
- Match F-00084's loader patterns (`int(data.get(...))` with explicit defaults).
- Use `EVENT_` prefix for event-type constants (precedent in `orch/daemon/auto_merge.py`).
- `executor/auto_merge.toml` must remain strict-TOML-valid (no `null` values — see I-00xx commit `1856cf8b` for the TOML `null` bug fix).

## TDD Requirement

- **RED**: Write a failing unit test in `tests/unit/test_auto_merge_config.py` (or extend F-00084's existing file) asserting `AutoMergeConfig.load()` returns `health_probe_interval_seconds == 300` for an empty `[health]` section. Run it; should fail with `AttributeError: 'AutoMergeConfig' object has no attribute 'health_probe_interval_seconds'`.
- **GREEN**: Implement the loader extension. Re-run; should pass.

Capture the RED failure line in your report.

## Pre-flight Quality Gates

1. `make format`.
2. `make typecheck` — zero errors on `orch/daemon/auto_merge.py`.
3. `make lint`.
4. Targeted unit test: `uv run pytest tests/unit/test_auto_merge_config.py -v`.

## Test Verification

- Run only the targeted unit test for `AutoMergeConfig`.
- Do NOT run the full suite.

## Subagent Result Contract

```json
{
  "step": "S04",
  "agent": "pipeline-impl",
  "work_item": "F-00085",
  "completion_status": "complete",
  "files_changed": [
    "executor/auto_merge.toml",
    "orch/daemon/auto_merge.py",
    "tests/unit/test_auto_merge_config.py"
  ],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed (targeted AutoMergeConfig tests including [health] section parsing)",
  "tdd_red_evidence": "tests/unit/test_auto_merge_config.py::test_load_health_section_defaults — AttributeError: 'AutoMergeConfig' object has no attribute 'health_probe_interval_seconds'",
  "blockers": [],
  "notes": "Config-only step. Daemon probe wiring is S06. New event constants defined but not yet emitted in this step."
}
```
