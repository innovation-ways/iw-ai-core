# CR-00057 — S01 Backend Report

## What was done

- Added ai-assistant parsing/validation in `orch/daemon/project_registry.py` via new helper:
  - `_parse_ai_assistant_block(project_id: str, raw: object) -> dict[str, Any] | None`
- Wired `_build_project_config(...)` to read `entry.get("ai_assistant")`, validate it, and persist the validated structure into `iw_config["ai_assistant"]`.
- Validation behavior implemented per step requirements:
  - missing/malformed/empty `models` => warning + ignore block
  - per-entry regex validation (`provider/model`) with warnings for invalid values
  - drop invalid entries, deduplicate valid entries preserving first-seen order
  - drop block if zero valid models remain
  - keep `default_model` only when it exists in filtered models; otherwise warn and drop only `default_model`
- Added focused unit tests for parser behavior in new test module.

## Files changed

- Modified: `orch/daemon/project_registry.py`
- Added: `tests/unit/daemon/test_project_registry_ai_assistant.py`

## Test results

- RED evidence run (before implementation):
  - `uv run pytest tests/unit/daemon/test_project_registry_ai_assistant.py -v`
  - Failed as expected with `AttributeError` (`_parse_ai_assistant_block` missing)
- GREEN verification:
  - `uv run pytest tests/unit/daemon/test_project_registry_ai_assistant.py -v --no-cov`
  - Result: **8 passed, 0 failed**
- Regression check (daemon unit scope):
  - `uv run pytest tests/unit/daemon/ -v --no-cov`
  - Result: **171 passed, 0 failed**

## Preflight quality gates

- `make format` ✅
- `make typecheck` ✅
- `make lint` ✅

## Issues / observations

- Running the single test file with default coverage options triggers repository-wide coverage threshold failure; behavior-level verification was completed with `--no-cov` to keep the run targeted and focused for this step.
