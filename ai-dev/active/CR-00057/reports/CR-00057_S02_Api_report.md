# CR-00057 — S02 API Report

## What was done

- Updated `GET /api/chat/config` in `dashboard/routers/chat.py` to accept optional `project_id` and DB session dependency.
- Implemented fail-open behavior for:
  - missing/empty `project_id`
  - unknown project
  - project without `config["ai_assistant"]`
- Implemented allowlist intersection when `project_id` resolves to a project with `config["ai_assistant"]`:
  - preserves allowlist order
  - drops unreachable models
  - logs dropped entries at WARNING
  - falls back to full provider list when intersection is empty (with WARNING)
- Implemented default model selection rules for allowlist-filtered responses.
- Reworked `_config_cache` to be keyed by project slot (`project_id` or `"__none__"`) while preserving 30s TTL and stale-on-unhealthy semantics.
- Verified `POST /api/chat/sessions` already forwards `directory=body.directory` to `client.create_session(...)`; no code change needed there.

## Files changed

- `dashboard/routers/chat.py`
- `tests/dashboard/test_chat_router.py`

## Tests added/extended

Extended `tests/dashboard/test_chat_router.py` with:

- `test_get_config_no_project_id_returns_full_list`
- `test_get_config_with_project_id_filters_to_allowlist`
- `test_get_config_project_without_allowlist_falls_back`
- `test_get_config_unknown_project_id_falls_back`
- `test_get_config_filter_drops_unreachable_with_warning`
- `test_get_config_default_model_preserved_when_in_filter`
- `test_get_config_default_model_dropped_falls_to_first_filtered`
- `test_get_config_empty_filter_falls_open_with_warning`
- `test_get_config_cache_keyed_per_project`

## TDD (RED → GREEN)

- RED evidence:
  - `uv run pytest tests/dashboard/test_chat_router.py -k "with_project_id_filters_to_allowlist" -v`
  - Failed as expected before implementation because the response returned the full provider list instead of allowlist-filtered models.
- GREEN verification:
  - `uv run pytest tests/dashboard/test_chat_router.py -v --no-cov`
  - Result: **44 passed, 0 failed**

## Preflight quality gates

- `make format` ✅
- `make typecheck` ✅
- `make lint` ✅

## Issues / observations

- Running the required command exactly as written (`uv run pytest tests/dashboard/test_chat_router.py -v`) passes all tests but fails repository-level coverage threshold (`fail_under=50`) in this environment; behavior verification was completed with `--no-cov` for step-local validation.
