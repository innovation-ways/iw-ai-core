# I-00091_S01_Backend_prompt

**Work Item**: I-00091 — Auto-merge settings form stays "Use global default" after partial-axis override
**Step**: S01
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY docker container/volume/network management
commands. Testcontainers spun up by pytest fixtures are the only
exception. Read-only `docker ps` / `docker logs` / `docker inspect` are
fine. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This step does NOT touch alembic migrations. The DB schema for
`auto_merge_project_config` already has independently-nullable `phase`
and `runtime_option_id` columns. Do not generate a migration in this
step. If `alembic check` reports drift unrelated to this work, leave it
alone and note it in `notes`. Full policy:
`docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00091 --json`
  over the manifest snapshot.
- `ai-dev/active/I-00091/I-00091_Issue_Design.md` — design document
- `ai-dev/active/I-00091/I-00091_Functional.md` — functional design
- `orch/auto_merge_aggregator.py` — current implementation
- `orch/db/models.py` — `AutoMergeProjectConfig` model (read-only context)
- `orch/CLAUDE.md` — orch-layer conventions
- `CLAUDE.md` — project rules

## Output Files

- `ai-dev/active/I-00091/reports/I-00091_S01_Backend_report.md` — Step report

## Context

You are implementing the **backend half** of the fix for I-00091. The
template renders `Use global default` for both dropdowns when the user
overrides only one axis because the single `ResolvedConfig.source` field
is computed from the runtime-resolution loop only — it does not record
where `phase` came from. Your job is to extend the dataclass so each
axis carries its own resolution source.

Read `ai-dev/active/I-00091/I-00091_Issue_Design.md` first, especially
the **Root Cause Analysis → Defect A** section and the **TDD Approach**
list of unit-test names — those are the tests S05 will write that must
pass against your code.

## Requirements

### 1. Extend `ResolvedConfig` with per-axis sources

In `orch/auto_merge_aggregator.py`, add two new fields to the
`ResolvedConfig` dataclass:

```python
phase_source: Literal["per_project_db", "toml", "hardcoded"]
runtime_source: Literal["per_project_db", "toml", "hardcoded"]
```

Both must be `frozen=True`-compatible (positional or keyword args with
defaults — your call, but be consistent with the existing style).

**Back-compat decision**: keep the existing `source` field but make it a
**computed property** that returns `"per_project_db"` if either axis is
`per_project_db`, otherwise the runtime axis's source. This preserves
existing chip rendering until the Frontend step (S03) migrates the chip
template. Document the property's semantics in a one-line docstring so
reviewers know it is a derived value, not first-class state.

Alternatively, if you find no callers of `.source` outside the templates
that S03 will update anyway, you may remove `source` entirely — but in
that case grep the codebase first (`grep -rn "config\.source\|\.config\.source" orch dashboard tests`) and update every call site. Pick one
approach and explain the choice in your step report.

### 2. Populate per-axis sources in `resolve_project_config`

Currently the function (lines 152-208) resolves `phase` at line 156 (one
ternary) and `runtime` via a layered loop (lines 166-199). The phase
source is silently lost.

Restructure so:

- `phase_source` is set to `"per_project_db"` iff the `AutoMergeProjectConfig`
  row exists AND its `phase` column is not NULL; otherwise `"toml"`. The
  `"hardcoded"` value is reserved for the truly-degraded path (no DB row,
  no TOML — currently only reachable when phase is invalid and falls
  back to 0; preserve that semantics).
- `runtime_source` records which of the three runtime layers
  (per_project_db / toml / hardcoded) actually produced the returned
  `runtime_option_id`. The existing loop already iterates through those
  three layers; capture which one wins.

**Edge cases to handle** (the unit tests in S05 will cover all of these
— write your code so they pass):

1. **Phase-only override**: `auto_merge_project_config.phase=1, runtime_option_id=NULL`
   → `phase_source="per_project_db"`, `runtime_source="toml"` (or
   `"hardcoded"` if TOML has no runtime).
2. **Runtime-only override**: `phase=NULL, runtime_option_id=42`
   → `phase_source="toml"`, `runtime_source="per_project_db"`.
3. **Both axes overridden**: both `"per_project_db"`.
4. **No DB row**: both reflect whatever layer the value actually came
   from (typically `"toml"` for both).
5. **Disabled runtime override**: existing fallthrough already emits a
   warning via `_maybe_emit_disabled_runtime_event`. After the
   fallthrough, `runtime_source` must reflect the layer that actually
   won — **not** `"per_project_db"`, because the per_project value was
   rejected.
6. **Invalid phase** (line 158-164): when the configured phase is not in
   `(0, 1)`, the function falls back to `phase=0`. In that case
   `phase_source` should remain whichever layer the invalid value came
   from (preserve observability — a CR or test can then verify the
   warning fires when `phase_source=="per_project_db"` and the value is
   0 due to fallback). Add a short comment explaining.

### 3. Do NOT change the template, route, or status-chip rendering

That is S03's job. Your S01 patch only touches
`orch/auto_merge_aggregator.py`. The chip will still read `.source`
unchanged (via the back-compat property) and the form template will
still render incorrectly — that's expected; S05's failing tests prove
it. S03 then flips both consumers to use the new per-axis fields.

### 4. Update aggregator unit tests for the shape change ONLY

If `tests/unit/test_auto_merge_config_resolution.py` instantiates
`ResolvedConfig` directly anywhere, update those constructor calls so
the new required fields are populated. Do **NOT** add the new behavioural
tests for partial-override matrix cells here — S05 owns those. Your edit
here is mechanical (signature compatibility) only.

### 5. Update any other callers that construct `ResolvedConfig`

```bash
grep -rn "ResolvedConfig(" orch dashboard tests
```

Every construction site needs to provide `phase_source` and
`runtime_source`. The two we already know about are inside
`resolve_project_config` (the live path and the final fallback at lines
201-208). The fallback path should populate both as the source it
actually fell through to (typically `"hardcoded"`).

## Project Conventions

Follow `CLAUDE.md` and `orch/CLAUDE.md`:

- SQLAlchemy 2.0 sync — no async.
- `psycopg` (v3), not `psycopg2`.
- Dataclasses use `@dataclass(frozen=True)` for value objects (existing
  pattern in this file).
- Type hints with `Literal[...]` for enum-like fields (existing pattern).
- No new dependencies.

## TDD Requirement (RED → GREEN → REFACTOR)

This is a **Backend** step, so RED-first applies:

1. **RED**: Before changing `resolve_project_config`, write or extend a
   single targeted unit test in
   `tests/unit/test_auto_merge_config_resolution.py` named
   `test_resolve_project_config_records_per_axis_source_phase_only_override`
   that asserts the returned `ResolvedConfig` has
   `phase_source == "per_project_db"` and `runtime_source == "toml"`
   (or "hardcoded" — match what the existing TOML fixture in that test
   file resolves to). Run it:

   ```bash
   uv run pytest tests/unit/test_auto_merge_config_resolution.py::test_resolve_project_config_records_per_axis_source_phase_only_override -v
   ```

   Confirm the failure is an `AssertionError` or `AttributeError: 'ResolvedConfig' object has no attribute 'phase_source'` — capture that line for `tdd_red_evidence`.
2. **GREEN**: Implement the dataclass + function changes per
   Requirements 1 and 2. Re-run the targeted test until it passes.
3. **REFACTOR**: If `_runtime_by_id` / `_maybe_emit_disabled_runtime_event`
   need adjusting for the new return shape, keep their existing
   behaviour intact and add no new public surface area.

The three remaining matrix tests (runtime-only / both / no-override) are
S05's responsibility — do **not** add them here. Adding only the
phase-only test is sufficient as your RED evidence.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`:

1. `make format` — auto-fixes formatting drift.
2. `make typecheck` — must report zero new errors involving the files
   you touched. (The `Literal` import already exists at the top of
   `orch/auto_merge_aggregator.py`; reuse it.)
3. `make lint` — must report zero new errors.

Populate the `preflight` object in your result contract with the
outcome of each.

## Test Verification (NON-NEGOTIABLE)

Run **only** the targeted test you wrote/touched:

```bash
uv run pytest tests/unit/test_auto_merge_config_resolution.py -v
```

Do **NOT** run `make test-unit` or `make test-integration` — those are
QV gate steps S12 / S13 and have their own budget.

## Migration Verification (Database steps only)

N/A — this step does not touch migrations.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "I-00091",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/auto_merge_aggregator.py",
    "tests/unit/test_auto_merge_config_resolution.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "tests/unit/test_auto_merge_config_resolution.py::test_resolve_project_config_records_per_axis_source_phase_only_override — AttributeError: 'ResolvedConfig' object has no attribute 'phase_source'  // captured RED run",
  "blockers": [],
  "notes": "Decision on back-compat .source property: KEPT|REMOVED with one-line rationale; list of other ResolvedConfig() call sites updated."
}
```
