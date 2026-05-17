# CR-00057_S04_Tests_prompt

**Work Item**: CR-00057 — AI Assistant chat model allowlist (per-project, with Ollama provider)
**Step**: S04
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures are exempt — and you will use them.

## ⛔ Migrations: agents generate, daemon applies

No migration is involved. Existing migration fixtures run inside testcontainers — no host-DB writes.

## Input Files

- `ai-dev/active/CR-00057/CR-00057_CR_Design.md` — design + AC1..AC6
- `ai-dev/active/CR-00057/reports/CR-00057_S01_Backend_report.md`
- `ai-dev/active/CR-00057/reports/CR-00057_S02_API_report.md`
- `ai-dev/active/CR-00057/reports/CR-00057_S03_Frontend_report.md`
- `tests/conftest.py` — testcontainer fixture wiring
- `tests/CLAUDE.md` — test patterns and rules
- `skills/iw-ai-core-testing/SKILL.md` — IW AI Core testing standards

## Output Files

- `ai-dev/active/CR-00057/reports/CR-00057_S04_Tests_report.md`
- New: `tests/integration/test_project_registry_ai_assistant.py`
- New: `tests/integration/test_chat_config_allowlist_intersection.py`

## Context

S01 covered unit tests for the parser. S02 covered dashboard router unit tests with a mocked opencode client. This step adds **integration** coverage that exercises the full path:

1. `projects.toml` → `project_registry.sync_projects_from_toml` → `Project.config` JSONB round-trip against a real testcontainer DB.
2. `GET /api/chat/config?project_id=…` against a real DB with the seeded allowlist and a mocked `OpencodeClient` (we don't want a live opencode subprocess in CI).

## Requirements

### 1. `tests/integration/test_project_registry_ai_assistant.py`

- Use the project's standard testcontainer fixture from `tests/conftest.py` (do not invent a new one).
- Write a fixture `projects.toml` to a `tmp_path` with one project that has a valid `[ai_assistant]` block.
- Monkeypatch the registry's `PROJECTS_TOML_PATH` (or whichever module variable it uses; check S01's report) to point at the temp file.
- Invoke `sync_projects_from_toml(db)` (or whatever the public sync function is named — read `orch/daemon/project_registry.py` to confirm).
- Assert the resulting `Project.config["ai_assistant"]` matches the input.
- Add a second test where the toml block is malformed (default_model not in models) — assert the resulting `config["ai_assistant"]` has `models` but no `default_model`, and a warning was logged.
- Add a third test where the block is absent — assert the resulting `config` has no `ai_assistant` key.

Apply the testing standards in `skills/iw-ai-core-testing/SKILL.md`: strong assertions (no bare `assert result`), real DB writes go through the testcontainer, no live-DB connection (the guard fixture will refuse it).

### 2. `tests/integration/test_chat_config_allowlist_intersection.py`

- Use `TestClient` against the FastAPI app (same pattern as the existing `tests/dashboard/` files — but this one is `integration/` because it uses a real DB).
- Seed a `Project` row with `config["ai_assistant"] = {"models": [...], "default_model": "..."}` directly via the testcontainer session.
- Mock `OpencodeClient.get_providers` and `OpencodeClient.get_config` on `app.state.opencode_client` to return a deterministic provider list.
- Hit `GET /api/chat/config?project_id=…`.
- Assert response.models == filtered allowlist (intersection in allowlist order), response.default_model matches the expected pick.
- Add the fail-open variant (no `ai_assistant` in config), the unknown-project variant (project_id not in DB), the unreachable-entries variant (with caplog WARNING assertion).
- Use `_CONFIG_TTL = 0` (or monkeypatch the cache dict between tests) so cache pollution doesn't bleed across cases.

### 3. Do not duplicate S01/S02 coverage

S01 already tests the parser as a unit. S02 already tests the router with a fully mocked client. These integration tests exist to catch wiring problems that the unit-level mocks would hide (e.g. ORM round-trip stripping a key, JSONB serialization quirks, cache key collision across test functions).

### 4. Run only your new files for verification

```bash
uv run pytest tests/integration/test_project_registry_ai_assistant.py \
              tests/integration/test_chat_config_allowlist_intersection.py -v
```

Do NOT run `make test-integration` here — the QV gate (S14) does that.

## TDD Requirement

For `tests-impl` steps the prompt explicitly says: "Dedicated coverage steps (`tests-impl`) are exempt — they add tests after the code exists and are not RED-first by nature." Use `"n/a — dedicated coverage step, code already exists from S01/S02"` for `tdd_red_evidence`.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

`make format` → `make typecheck` → `make lint`. Zero errors.

## Subagent Result Contract

```json
{
  "step": "S04",
  "agent": "tests-impl",
  "work_item": "CR-00057",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/integration/test_project_registry_ai_assistant.py",
    "tests/integration/test_chat_config_allowlist_intersection.py"
  ],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "n/a — dedicated coverage step, code already exists from S01/S02",
  "blockers": [],
  "notes": ""
}
```
