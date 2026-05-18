# CR-00057 — S04 Tests Report

## What was done

- Added integration coverage for `ai_assistant` config persistence through project registry parsing and DB JSONB round-trip.
- Added integration coverage for `GET /api/chat/config?project_id=...` allowlist intersection behavior against a real testcontainer-backed DB and mocked `app.state.opencode_client`.
- Ensured chat config cache isolation across tests by forcing `_CONFIG_TTL = 0` and clearing `_config_cache` per test.

## Files changed

- `tests/integration/test_project_registry_ai_assistant.py` (new)
- `tests/integration/test_chat_config_allowlist_intersection.py` (new)

## Coverage areas addressed

### `test_project_registry_ai_assistant.py`
- Valid `ai_assistant` block persists to `Project.config["ai_assistant"]` exactly.
- Malformed `default_model` (not in models) is dropped while models persist; warning asserted.
- Absent `ai_assistant` block results in no `ai_assistant` key in persisted config.

### `test_chat_config_allowlist_intersection.py`
- Allowlist intersection preserves allowlist order and returns expected default model.
- Fail-open behavior when project has no `ai_assistant` block.
- Fail-open behavior for unknown `project_id`.
- Unreachable allowlist entries are dropped, fallback default is selected, and WARNING is logged.

## Test results

- Preflight gates:
  - `make format` ✅
  - `make typecheck` ✅
  - `make lint` ✅
- Targeted verification run:
  - `uv run pytest tests/integration/test_project_registry_ai_assistant.py tests/integration/test_chat_config_allowlist_intersection.py -v --no-cov`
  - Result: **7 passed, 0 failed**

## Issues / observations

- Running the prompt-specified pytest command without `--no-cov` executes tests successfully but fails repository-wide coverage threshold (`fail_under=50`) due running only two files; behavior verification is therefore recorded with `--no-cov` for this dedicated coverage step.
