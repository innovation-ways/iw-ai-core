# CR-00057_S01_Backend_prompt

**Work Item**: CR-00057 — AI Assistant chat model allowlist (per-project, with Ollama provider)
**Step**: S01
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute any docker container/volume/network mutating command. Allowed: `docker ps`, `docker inspect`, `docker logs`, `./ai-core.sh`, `make`. Testcontainer fixtures spun up by pytest are exempt. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This step **does not** add or modify any Alembic migration. The allowlist lives in the existing `Project.config` JSONB column. If you find yourself wanting to add a migration, STOP — review the design doc with the operator. Read-only alembic commands (`history`, `current`, `show`) are fine if you need to verify state.

## Input Files

- `ai-dev/active/CR-00057/CR-00057_CR_Design.md` — design doc (read first; "Current Behavior", "Desired Behavior", AC1–AC6, "Affected Components")
- `orch/daemon/project_registry.py` — file you are extending
- `orch/db/models.py:Project` — `config` JSONB column you are writing to
- `projects.toml` — the file shape you are parsing (the S05 step will add the seed `[projects.iw-ai-core.ai_assistant]` block; you should accept its presence or absence gracefully)
- `CLAUDE.md` and `orch/CLAUDE.md` — project conventions
- Runtime step state via `uv run iw item-status CR-00057 --json`

## Output Files

- `ai-dev/active/CR-00057/reports/CR-00057_S01_Backend_report.md`
- Modified: `orch/daemon/project_registry.py`
- New: `tests/unit/daemon/test_project_registry_ai_assistant.py`

## Context

You are wiring the `[projects.X.ai_assistant]` block from `projects.toml` into the existing `Project.config` JSONB so the dashboard's chat router can read it later. This is the source-of-truth step — every other layer in the CR depends on this key being written correctly.

## Requirements

### 1. Parse the `[projects.<id>.ai_assistant]` block

In `orch/daemon/project_registry.py::_build_project_config`, after the existing keys are merged into `iw_config`, look up `entry.get("ai_assistant")`. The shape, when present, is:

```python
{
    "models": list[str],          # required, non-empty
    "default_model": str | None,   # optional
}
```

Validation:

- `models` must be a non-empty list of strings. If absent, malformed, or empty → log a `WARNING` (`"Project %r ai_assistant block missing or invalid `models` — ignoring"`) and skip the block (do NOT skip the project).
- Each model entry must match the regex `^[a-z0-9._-]+/[A-Za-z0-9._:/-]+$`. Drop entries that don't match with a per-entry warning that names the project and the offending value. Deduplicate while preserving first-seen order. After filtering, if zero valid entries remain, drop the whole block with a `WARNING`.
- `default_model`, when supplied, must appear in the filtered `models` list. Otherwise drop `default_model` only (keep `models`) and log a `WARNING`.

The validated structure is written as `iw_config["ai_assistant"] = {"models": [...], "default_model": "..."}` (omit `default_model` when not set). The existing `sync_project_to_db` already writes `iw_config` into `Project.config` wholesale, so once the key is in `iw_config` the persistence is automatic.

### 2. Helper function

Extract the parsing/validation into a private helper `_parse_ai_assistant_block(project_id: str, raw: object) -> dict[str, Any] | None`. This makes it directly unit-testable without spinning up the full registry. Return `None` when the block is absent or fully invalid. Place it next to `_validate_staleness_config`.

### 3. Unit tests (TDD — RED first)

Create `tests/unit/daemon/test_project_registry_ai_assistant.py` with these cases (write them, run them and confirm they fail, *then* implement):

- `test_parse_valid_block` — full block with `default_model` → returns dict matching input.
- `test_parse_missing_block` — entry has no `ai_assistant` key → returns `None`.
- `test_parse_empty_models_list` → returns `None`, warning logged.
- `test_parse_drops_invalid_entries` — mix of valid + invalid `provider/model` strings → returns dict with only valid entries.
- `test_parse_deduplicates_preserving_order` — duplicate entries → returns first-seen order, no duplicates.
- `test_parse_default_model_not_in_models` — default_model that isn't in models → returns dict with `models` but no `default_model`, warning logged.
- `test_parse_default_model_survives_filter` — default_model that is in `models` → preserved.
- `test_parse_non_string_entries_dropped` — `models = ["valid/x", 42, None]` → only `"valid/x"` survives.

Use `caplog` to assert warnings are emitted at the right levels.

### 4. Do not regress existing tests

The existing `tests/unit/daemon/test_project_registry*.py` files (if any) must still pass. Targeted run only:

```bash
uv run pytest tests/unit/daemon/ -v
```

Do NOT run `make test-unit` or `make test-integration`.

## Project Conventions

Read `CLAUDE.md`, `orch/CLAUDE.md`, and `tests/CLAUDE.md` before writing tests. Key rules:

- SQLAlchemy 2.0 `Mapped[]` declarative style.
- Tests must use testcontainers, never the live DB.
- `DaemonEvent.metadata` is `event_metadata` in Python (not relevant for this step, but a common trap).

## TDD Requirement

Follow RED-GREEN-REFACTOR. Capture the RED run output (the failure line and reason) for the `tdd_red_evidence` field.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting completion, run in order:

1. `make format` (auto-fix)
2. `make typecheck` (zero errors on files you touched)
3. `make lint` (zero errors)

## Test Verification (NON-NEGOTIABLE)

- Run `uv run pytest tests/unit/daemon/test_project_registry_ai_assistant.py -v` after implementing.
- Targeted-only — do NOT run the full unit suite.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "CR-00057",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["orch/daemon/project_registry.py", "tests/unit/daemon/test_project_registry_ai_assistant.py"],
  "preflight": {"format": "ok|fixed", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "tests/unit/daemon/test_project_registry_ai_assistant.py::test_parse_valid_block — AttributeError: module has no attribute '_parse_ai_assistant_block'",
  "blockers": [],
  "notes": ""
}
```
