# CR-00090_S03_Tests_prompt

**Work Item**: CR-00090 — Fix E2E Polling Suppression — Replace UA Sniffing with IW_CORE_E2E_MODE Env Var
**Step**: S03
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

No migration is required for this CR.

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00090 --json`
- `ai-dev/active/CR-00090/CR-00090_CR_Design.md` — Design document (authoritative spec — TDD Approach section)
- `ai-dev/active/CR-00090/reports/CR-00090_S01_Backend_report.md` — S01 implementation
- `ai-dev/active/CR-00090/reports/CR-00090_S02_Frontend_report.md` — S02 implementation
- `orch/config.py` — For `get_e2e_mode()` signature
- `dashboard/app.py` — To understand how `_e2e_mode` is injected as a global
- `dashboard/templates/base.html` — To understand `_headless` detection for test assertions
- `tests/unit/test_config.py` — Existing unit tests (S01 added parametrized cases here; check for gaps)
- `tests/conftest.py` — Root fixtures and test patterns
- `tests/CLAUDE.md` — Test conventions (MUST read)
- `skills/iw-ai-core-testing/SKILL.md` — Testing rules (MUST read)

## Output Files

- `tests/dashboard/test_e2e_mode.py` — New dashboard test file
- `ai-dev/active/CR-00090/reports/CR-00090_S03_Tests_report.md` — Step report

## Context

You are writing additional test coverage for CR-00090. S01 already added parametrized
unit tests for `get_e2e_mode()` in `tests/unit/test_config.py`. This step adds
dashboard-level tests that verify:
1. `_e2e_mode` appears in the template context when the app is started
2. Polling attributes are absent when `IW_CORE_E2E_MODE=true`
3. Polling attributes are present when `IW_CORE_E2E_MODE` is unset

Read the design document's TDD Approach section carefully — it names these files
explicitly and describes what each test must assert.

## Requirements

### 1. Check and extend `tests/unit/test_config.py` if needed

S01 should have added parametrized `get_e2e_mode()` tests. Read that file and verify
the following cases are all covered:

| `IW_CORE_E2E_MODE` value | Expected result |
|--------------------------|-----------------|
| `"true"` | `True` |
| `"1"` | `True` |
| `"TRUE"` | `True` |
| `""` | `False` |
| `"false"` | `False` |
| absent (env var not set) | `False` |

If any cases are missing, add them. Use `monkeypatch.setenv` / `monkeypatch.delenv`.
NEVER call `importlib.reload(orch.config)` — use `monkeypatch` only.

### 2. Create `tests/dashboard/test_e2e_mode.py`

Use FastAPI's `TestClient` to test the dashboard at the HTTP level.

**Test patterns to follow** (read existing dashboard tests for exact patterns):
- Use `tests/dashboard/` conftest fixtures for the `db_session` / test app setup
- Override `get_db` dependency if needed (see other dashboard test files)
- Use `monkeypatch.setenv("IW_CORE_E2E_MODE", "true")` to set the env var

**IMPORTANT — reading `_e2e_mode` from the Jinja2 global context at test time**:
The `_e2e_mode` global is set once at app startup via `templates.env.globals["_e2e_mode"]`.
Because `TestClient` creates the app once per test session (or module), and the env var
is set via `monkeypatch` which is function-scoped, you may need to patch `get_e2e_mode`
directly using `monkeypatch.setattr` on the function in `orch.config`, OR you can reload
the global in the app startup fixture. Check how other globals (`static_v`, `is_db_stale`)
are handled in existing tests to pick the right approach.

**Write these tests:**

**Test A — `_e2e_mode` global is present in template context (AC5)**

Verify that when a page is rendered, the Jinja2 template context includes `_e2e_mode`
as a boolean. One approach: render a page response and assert the HTML does not include
an `UndefinedError` for `_e2e_mode`. A more direct approach: assert the presence or
absence of `hx-trigger="never"` in the rendered HTML (see tests B and C below).

**Test B — Polling suppressed when `IW_CORE_E2E_MODE=true` (AC1)**

1. Set `IW_CORE_E2E_MODE=true` (via `monkeypatch.setenv` or patch `get_e2e_mode`)
2. GET a page containing the worktree-badge element (e.g., `/system/nav/worktree-badge`
   or the project dashboard page)
3. Assert: the response HTML contains `hx-trigger="never"` for the polling element
4. Assert: the response HTML does NOT contain `hx-get` on that same element
   (confirming polling is fully disabled, not just triggered differently)

**Test C — Polling present when `IW_CORE_E2E_MODE` is unset (AC2)**

1. Ensure `IW_CORE_E2E_MODE` is NOT set (use `monkeypatch.delenv("IW_CORE_E2E_MODE", raising=False)`)
2. GET the same page
3. Assert: the response HTML does NOT contain `hx-trigger="never"`
4. Assert: the response HTML contains a `hx-get` attribute on the polling element
   (confirming polling is enabled)

Read `dashboard/templates/base.html` and the fragment files to determine the exact
HTML element selectors and attribute patterns you need to assert on.

## Project Conventions

- NEVER connect tests to live DB (port 5433) — use testcontainers or `TestClient`
- NEVER call `importlib.reload(orch.config)` — use `monkeypatch.setenv()` or `monkeypatch.setattr()`
- NEVER mock the database in integration tests
- Use `monkeypatch.delenv("IW_CORE_E2E_MODE", raising=False)` to cleanly unset the var
- Read `tests/CLAUDE.md` and `skills/iw-ai-core-testing/SKILL.md` before writing tests

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `completion_status: complete`:

1. `make format` — auto-fixes formatting drift
2. `make typecheck` — must report zero errors in files you touched
3. `make lint` — must report zero errors

Do NOT run `make test-unit`, `make test-integration`, `make allure-integration`, or any full-suite gate. Full-suite execution is the downstream qv-gate's job — running it here blows the timeout budget (see I-00073/S03 post-mortem).

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed.
But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert "permissions" in data` (shape only)
- GOOD: `assert "brands:manage" in permissions` (semantic — verifies specific expected value)
- GOOD: `assert "*" not in permissions` (semantic — verifies unwanted value is absent)

Apply this rigorously: every assertion must be one that would fail if the production code regressed.

## Test Verification (NON-NEGOTIABLE)

Run ONLY the test files you wrote or modified:

```bash
uv run pytest tests/unit/test_config.py -v -k "e2e" --no-cov
uv run pytest tests/dashboard/test_e2e_mode.py -v --no-cov
```

Do NOT run the full suite — that is the QV gate's job.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "tests-impl",
  "work_item": "CR-00090",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/unit/test_config.py",
    "tests/dashboard/test_e2e_mode.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "n/a — tests-impl step adds coverage after implementation",
  "blockers": [],
  "notes": ""
}
```
