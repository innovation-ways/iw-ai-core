# F-00081_S03_CodeReview_prompt

**Work Item**: F-00081 -- Per-Item / Per-Step Agent + Model Override
**Step Being Reviewed**: S02 (backend-impl)
**Review Step**: S03

---

## ⛔ Docker is off-limits

Standard policy. Read-only `docker ps`/`inspect`/`logs` are allowed. Testcontainers via pytest are exempt.

## ⛔ Migrations: agents generate, daemon applies

Do NOT run alembic mutations. You MAY use `alembic history|current|show` for verification.

## Input Files

- `uv run iw item-status F-00081 --json` for runtime step state.
- `ai-dev/active/F-00081/F-00081_Feature_Design.md`.
- `ai-dev/active/F-00081/reports/F-00081_S02_Backend_report.md`.
- All files in S02's `files_changed`.
- `ai-dev/active/F-00081/reports/F-00081_S01_Database_report.md` for the schema S02 builds on.

## Output Files

- `ai-dev/active/F-00081/reports/F-00081_S03_CodeReview_report.md`.

## Context

You are reviewing the backend-impl work in S02 for **F-00081 — Per-Item / Per-Step Agent + Model Override**. Per-agent reviews focus on this layer's correctness; the cross-layer review is S07.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Run `make lint` and `make format` (or `make format-check`) on S02's `files_changed`. Any new violation that does not appear on `main` is a CRITICAL finding (`category: conventions`). Do not auto-fix; report only.

## Review Checklist

### 1. Cascade resolution correctness

- Does `resolve_runtime` honour the order step → item → projects.toml → catalogue default?
- Are disabled override rows skipped (with a warning log) rather than honoured?
- What happens when `is_default=true` lookup fails? The function should raise — verify it does. (The migration enforces this row exists, so a raise is correct.)
- Are `(cli_tool, model)` lookups done with parameterised queries (no SQL injection risk)?

### 2. Launch-command injection

- Is `--model <model>` injected into both the opencode and claude command paths?
- Is the OpenCode `--model` flag form documented in S02's report (the prompt asked for verification)?
- Does the `step_runs` row record `agent_runtime_option_id` on every launch (Invariant 2)?
- Is `cli_tool` still recorded on `step_runs` for backwards compatibility?
- Are env vars (`OPENCODE_MODEL`, `ANTHROPIC_MODEL`) set in `_build_agent_env` as a fallback?

### 3. Audit helper

- Does `emit_runtime_override_changed` always write **exactly one** `daemon_events` row?
- Is `event_type` exactly `'runtime_override_changed'`?
- Does the metadata payload match the design's AC6 shape (`{item_id, scope, step_ids, old_option_id, new_option_id, actor}`)?
- Note: SQLAlchemy reserves `metadata`; the column is exposed as `event_metadata` in Python — check usage.

### 4. project_registry extension

- Is `cli_tool` read from `projects.toml` first, with `.iw-orch.json` as fallback (backwards compat)?
- Is `model` read from `projects.toml` with sensible default `"minimax"`?
- Is a missing `(cli_tool, model)` pair in the catalogue a warning, not a crash, at registration time?
- Is `ProjectConfig` updated everywhere it is constructed?

### 5. Layer boundaries (orch/CLAUDE.md)

- The new `orch/agent_runtime/` package must not import from `orch/daemon/` (the daemon imports from it). Verify.
- The resolver takes a Session — it must not open one itself.

### 6. Project conventions

- Sync SQLAlchemy 2.0 patterns; psycopg v3 URLs only (no `psycopg2`).
- Type annotations consistent with the rest of `orch/`.
- Logging uses `logger.warning(...)` not `print` for the disabled-override and missing-pair paths.

### 7. Security

- No hardcoded credentials.
- Inputs to launch-command construction (model name) are not interpolated into shell strings without sanitisation. Models come from a controlled catalogue, but verify the SQL fetch is parameterised and the assembled command is safe (e.g., the model field cannot inject a shell metacharacter — the catalogue rows are operator-controlled but a defence-in-depth check is appropriate).

### 8. Testing

- Are the unit tests for the resolver table-driven and covering: no overrides, item only, step only, both, disabled-row fallback, missing-pair fallback?
- Is the audit helper tested for the single-event invariant (Invariant 4)?

## Test Verification (NON-NEGOTIABLE)

Run `make test-unit` and `make test-integration` to confirm no regressions.

## Severity Levels

| Severity | Action |
|---|---|
| CRITICAL / HIGH | Must fix before merge |
| MEDIUM (fixable) | Must fix in fix cycle |
| MEDIUM (suggestion) / LOW | Informational |

## Review Result Contract

```json
{
  "step": "S03",
  "agent": "code-review-impl",
  "work_item": "F-00081",
  "step_reviewed": "S02",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "",
  "notes": ""
}
```
