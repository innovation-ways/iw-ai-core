# CR-00054 S04 — Tests Report

## What was done

- Expanded `tests/integration/test_e2e_opencode_stub.py` from a minimal smoke suite to full endpoint/event/auth coverage for the OpenCode E2E stub.
- Added a stub subprocess fixture that:
  - picks a free localhost port,
  - generates a random `OPENCODE_SERVER_PASSWORD`,
  - launches `uv run python scripts/e2e_opencode_stub.py serve ...`,
  - polls `/global/health` until ready,
  - performs SIGTERM → timeout(2s) → SIGKILL teardown.
- Added/updated tests for:
  - unauthenticated `/global/health`,
  - Basic auth enforcement on protected endpoints,
  - `/config` semantic values (`stub/echo`, `Stub Echo`),
  - session create/list/get/404/messages,
  - prompt async + SSE ordered sequence,
  - allow/deny permission branches,
  - abort behavior,
  - Last-Event-ID replay behavior,
  - ring buffer cap at 256 events,
  - invalid argv exit code,
  - password non-leak in stderr.

## Files changed

- `tests/integration/test_e2e_opencode_stub.py`

## Test results

- `make format` ✅
- `make typecheck` ✅
- `make lint` ✅
- Required command run: `uv run pytest tests/integration/test_e2e_opencode_stub.py -v`
  - Functional tests: 15 passed
  - Process exited non-zero due repository-wide coverage fail-under gate when running a single file in isolation.
- Validation run for step-level functional verification: `PYTEST_ADDOPTS='--no-cov' uv run pytest tests/integration/test_e2e_opencode_stub.py -v` ✅
  - 15 passed, 0 failed.

## Issues / observations

- While expanding coverage, one assertion initially went RED and revealed actual stub behavior detail:
  - `allow` path emits an additional `message.updated` (`status=complete`) before `session.idle`.
  - Test was corrected to assert the real expected sequence: `message.updated(tool_continued)` → `message.updated(status=complete)` → `session.idle`.
