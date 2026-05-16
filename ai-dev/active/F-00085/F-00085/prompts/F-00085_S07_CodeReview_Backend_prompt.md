# F-00085_S07_CodeReview_Backend_prompt

**Work Item**: F-00085
**Step**: S07 (Per-agent review of S06)
**Agent**: code-review-impl

---

## Inputs

- F-00085 Feature Design (especially Invariants 1, 2, 3, 5, 7)
- S06 report + diff of `files_changed`

## Output

- `ai-dev/active/F-00085/reports/F-00085_S07_CodeReview_report.md`

## Review Checklist

### Aggregator (`orch/auto_merge_aggregator.py`)

- [ ] All 7 queries scope by `project_id` (multi-project isolation).
- [ ] `list_recent_events` LEFT JOINs `merge_auto_verdicts` (so unrevdicted rows still appear).
- [ ] Window filters use parameterised `now() - interval`; no string interpolation of time values.
- [ ] JSONB queries use `->>` / `->` operators correctly (Python: `Event.event_metadata['key'].astext`).
- [ ] `MODEL_PRICING` covers every currently-enabled `agent_runtime_options` row (id=1, 4, 5, 6 from F-00081 + I-00086).
- [ ] Unknown models → contribute $0 cost AND set `TokenCostRollup.has_unknown_models=True`.
- [ ] `resolve_project_config` is deterministic (Invariant 2): no `datetime.now()`, no random, no I/O beyond the passed DB session.

### Config resolution

- [ ] Resolution order is per-project DB > TOML > hardcoded defaults.
- [ ] Phase=2 / Phase=3 in DB row → rejected (CHECK constraint from S01) or filtered out with clear log.
- [ ] Disabled runtime in per-project row → falls through to next layer + emits `auto_merge_config_invalid` (once per state-change, not on every merge).
- [ ] `ResolvedConfig.source` correctly identifies which layer won.
- [ ] When per-project row's `phase` is NULL but `runtime_option_id` is set, the phase resolves from TOML and runtime from DB (independent override layers).

### Health probe (`orch/daemon/auto_merge_health.py`)

- [ ] Probe respects `probe_interval_seconds` from TOML (no probe if last one is recent).
- [ ] Probe respects per-project phase: phase=0 → no probe.
- [ ] Probe uses the resolved runtime (per-project DB override > TOML).
- [ ] Subprocess timeout = `max(15, probe_interval_seconds // 4)`.
- [ ] On any exception, error is captured in event metadata as string; daemon does NOT crash.
- [ ] Daemon poll loop wraps `maybe_run_probe` in try/except (Invariant 7: never blocks merge queue).
- [ ] Token budget is bounded: prompt is fixed short string, response is single word.

### Daemon main loop integration

- [ ] `maybe_run_probe` called AFTER merge queue processing AND batch processing per poll iteration (Inv 7).
- [ ] Iterates over ENABLED projects only.
- [ ] try/except around the call → log + continue (one project's failure doesn't block others).

### `auto_merge.py` + `merge_queue.py` updates

- [ ] All reads of `config.phase` and `config.runtime_option_id` go through `resolve_project_config`.
- [ ] F-00084's Phase-0 short-circuit still works (now via `resolved.phase == 0`).
- [ ] Backwards-compatible: with NO per-project rows, behaviour matches F-00084's current behaviour exactly.

### Invariants

- [ ] **Inv 1** (`daemon_events` append-only): no `.update(DaemonEvent)` or `.delete(DaemonEvent)` calls in the diff.
- [ ] **Inv 2** (config resolution deterministic): no time-dependent inputs.
- [ ] **Inv 3** (TOML standalone): with `auto_merge_project_config` empty, all behaviour is unchanged.
- [ ] **Inv 5** (Phase >=2 rejected): per-project DB CHECK + TOML loader both refuse.
- [ ] **Inv 7** (health probe non-blocking): wrapped in try/except, called out-of-band on poll loop.

### Project conventions

- [ ] Sync SQLAlchemy.
- [ ] `event_metadata` (not `metadata`) on Python side.
- [ ] Subprocess noqa comments.
- [ ] No new dependencies.

### Out-of-scope guard

- [ ] No router / template / CSS changes (S08/S10).
- [ ] No new alembic migration (S01 was the only one).
- [ ] No changes to F-00081's `agent_runtime_options` schema.

## Severity Mapping

- **CRITICAL** — probe blocks merge queue; per-project override causes phase=0 to call LLM; daemon_events touched with UPDATE/DELETE; resolve_project_config returns non-deterministic results.
- **HIGH** — backward compat broken (empty DB tables change behaviour); MODEL_PRICING missing an enabled row; disabled-runtime fallback skipped.
- **MEDIUM** — log noise (event spam); window-string parsing fragile.
- **LOW** — style.

## Result Contract

Standard code-review JSON.
