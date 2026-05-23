# F-00088_S01_Backend_prompt

**Work Item**: F-00088 — Structured Dashboard E2E Test Layer
**Step**: S01
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (see the 2026-04-22 incident in
docs/IW_AI_Core_DB_Setup.md).

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This Feature adds **no migration** and **no schema change**. You MUST NOT
create, modify, or apply any alembic migration. If your work appears to
need one, STOP and raise a blocker — that means the scope is wrong.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — prefer `uv run iw item-status F-00088 --json` for the current step list, gate commands, and prompt paths. `workflow-manifest.json` is a design-time snapshot and may be out of date (CR-00023).
- `ai-dev/active/F-00088/F-00088_Feature_Design.md` — the design document. **Read it in full before writing any code.**
- `ai-dev/active/F-00088/F-00088_Functional.md` — human-facing summary.
- Reference patterns: `tests/dashboard/browser/conftest.py` (existing playwright-cli session fixture pattern), `scripts/e2e_up.sh` (the isolated E2E stack mechanism), `scripts/e2e_seed.py` (seed data pattern), `.claude/agents/qv-browser.md` (playwright-cli usage rules).

## Output Files

- `ai-dev/work/F-00088/reports/F-00088_S01_Backend_report.md` — step report.

## Context

You are implementing the **E2E harness foundation** for F-00088. This step
creates the `tests/e2e/` directory, the playwright-cli wrapper, the `e2e`
and `e2e_smoke` markers, the Makefile targets, and the first journey
(`test_journey_home_navigation.py`) as proof-of-harness.

This Feature is **strictly test-infrastructure**: you MUST NOT edit any
production code (`orch/`, `dashboard/`, `executor/`, `scripts/` — except
`scripts/e2e_seed.py` if a journey needs more seed rows). The merge-time
scope gate enforces this against `scope.allowed_paths`.

Read `CLAUDE.md` and `tests/CLAUDE.md` for project conventions before
starting. Read `skills/iw-ai-core-testing/SKILL.md` — it is MUST-read
for any test work here.

## Requirements

### 1. `tests/e2e/` directory structure

Create:
- `tests/e2e/__init__.py` (empty package marker)
- `tests/e2e/playwright_wrapper.py` — the thin subprocess wrapper
- `tests/e2e/conftest.py` — E2E fixtures
- `tests/e2e/test_journey_home_navigation.py` — journey 1
- `tests/e2e/test_harness_selfcheck.py` — unmarked harness self-check unit tests (see §7)
- `tests/e2e/.gitignore` — ignores the `_artifacts/` journey-screenshot dir (see §3)

### 2. playwright-cli wrapper — `tests/e2e/playwright_wrapper.py`

**CRITICAL**: ALL browser interactions MUST be implemented as subprocess calls
to the `playwright-cli` binary. NEVER:
- Call `chromium.launch()` or any direct Playwright Python/Node API
- Use `agent-browser`
- Run `npx playwright install` or `playwright install`

The binary is at `~/.local/bin/playwright-cli`. The wrapper should:
- Accept the base URL from `$IW_BROWSER_BASE_URL` (read via the conftest fixture).
- Raise a clear `RuntimeError` at import/init time if the binary is absent.
- Expose at minimum these helpers (all implemented via subprocess):
  - `open_url(url)` — opens the URL in the browser (use only once per session)
  - `goto(url)` — navigate without relaunching the browser
  - `snapshot()` — returns the accessible element tree
  - `click(ref)` — click an element by its accessible ref
  - `fill(ref, value)` — fill a form field
  - `screenshot(dest_path)` — take a screenshot and copy it to `dest_path`
    (remember: `playwright-cli screenshot` takes no path argument — saves to
    `.playwright-cli/page-<ts>.png`; copy the latest file to `dest_path`)
  - `read_console_errors()` — reads the latest `.playwright-cli/console-*.log`
    and returns any error-level lines
  - `accessibility_check(url)` — runs an accessibility snapshot and returns
    any violations found (adapt the snapshot output to flag missing labels,
    missing roles, or obvious a11y issues; at minimum assert that the page
    has at least one landmark region)

Always call `playwright-cli kill-all` before `open_url`. After `open_url`,
use `goto` for all subsequent navigations. Never call `open_url` more than
once per session — it wipes browser state (localStorage / cookies).

### 3. `tests/e2e/conftest.py` — E2E fixtures

- Define a `base_url` fixture (session scope) that reads `$IW_BROWSER_BASE_URL`.
  If the env var is not set, the fixture itself calls
  `pytest.skip("E2E_STACK_MISSING: IW_BROWSER_BASE_URL is not set")`. The skip
  MUST be **fixture-scoped** — only tests that request `base_url` / `pw` skip.
  Do NOT use a directory-wide collection hook (`collect_ignore`, a
  `pytest_collection_modifyitems` blanket skip): the harness self-check unit
  tests (§7) use neither fixture and MUST still run without the E2E stack.
- Define a `pw` fixture (function scope) that creates a fresh
  `PlaywrightWrapper(base_url)` and runs `kill-all` at setup. Yield the wrapper.
  In teardown, run `playwright-cli kill-all` again.
- Define an `evidence_dir` fixture that returns the directory for journey
  screenshots. It reads the `IW_E2E_EVIDENCE_DIR` env var; if unset it defaults
  to `tests/e2e/_artifacts/`. This is a **neutral, gitignored** location — do
  NOT hardcode `ai-dev/active/F-00088/...`: `tests/e2e/` is permanent
  infrastructure and must not bake in the F-00088 work-item ID (once the item
  is archived that path would be a phantom dir created on every later run).
  Create the directory if absent. The S14 qv-browser step sets
  `IW_E2E_EVIDENCE_DIR` to its own `evidences/post/` dir so verification
  evidence still lands with the item.
- Wipe stale `.playwright-cli/page-*.png` and `.playwright-cli/console-*.log`
  files before each journey to prevent reuse of stale screenshots.

### 4. `e2e` and `e2e_smoke` markers — `pyproject.toml`

- Register both markers in `[tool.pytest.ini_options].markers` with prose
  descriptions (model on existing `browser` / `quarantine` / `contract_fuzz`
  entries). Suggested text:
  - `e2e: Full browser journey tests — require the isolated E2E stack (IW_BROWSER_BASE_URL). Run via make test-e2e; excluded from the default pytest selection and make test-integration.`
  - `e2e_smoke: Curated smoke subset of the e2e journey suite — blocking on pull_request and push; run via make test-e2e-smoke.`
- Extend the `addopts` `-m` filter to also exclude `e2e`. **Do NOT assume the
  current expression** — open `pyproject.toml`, locate the existing `-m '...'`
  segment inside `addopts`, and append ` and not e2e` immediately before its
  closing quote, preserving every term already present.
  On current `main` the expression is `-m 'not browser and not quarantine'`,
  so it becomes `-m 'not browser and not quarantine and not e2e'`. If a Phase 3
  CR has merged first (e.g. CR-00072 adds `not contract_fuzz`), that term is
  already there — keep it and still only add `and not e2e`. A literal
  find-replace on a hardcoded "from" string is a bug; read the file first.
  Note: excluding `e2e` covers `e2e_smoke` automatically (a test can carry
  both markers; the `-m` expression matches either).
- Keep `--strict-markers` and every other existing flag intact.

### 5. Makefile targets

- `test-e2e` — runs the full six-journey matrix:
  `uv run pytest tests/e2e/ -m e2e -v --no-cov`
- `test-e2e-smoke` — runs the smoke subset:
  `uv run pytest tests/e2e/ -m e2e_smoke -v --no-cov`
- Add both target names to the `.PHONY` line.

### 6. Journey 1 — `tests/e2e/test_journey_home_navigation.py`

Implement the dashboard home → project → cross-tab navigation journey. Mark it
with both `@pytest.mark.e2e` and `@pytest.mark.e2e_smoke`.

The IW AI Core dashboard has **no authentication** — there is no login page,
no credentials, and no logout. Do NOT add a login step and do NOT read
`IW_BROWSER_E2E_USER` / `IW_BROWSER_E2E_PASSWORD`; they are not set for this
project. This journey verifies the core navigation path a real user takes.

The journey should:
1. Open the base URL — the global dashboard home.
2. Assert the home page renders (HTTP 200) and lists at least one project.
3. Run an accessibility check on the home page; assert it passes.
4. Assert zero console errors observed on the home page.
5. Navigate into a project by clicking its link/row in the home list — never a
   hardcoded URL; read the link the page actually renders.
6. Assert the project landing page renders (HTTP 200) with the project name
   visible.
7. Navigate across the project's main tabs (at minimum Queue, Code, Docs, Jobs)
   by clicking each nav link. After each, assert the page renders (HTTP 200)
   with zero console errors.
8. Capture a screenshot of a representative project page via the wrapper's
   `screenshot()` into the `evidence_dir` fixture; use a neutral filename
   (e.g. `home_navigation_project.png`) — never bake the F-00088 ID into a
   permanent test file.
9. Navigate back to the global home; assert it still renders and the project
   list is intact (navigation did not lose state).
10. Run an accessibility check on at least one project page; assert it passes.
11. Assert zero console errors for the full journey.

Navigate via the UI exactly as a user would — open a list/index page and click
the link for the entity under test. Do not hardcode route paths; routes drift.

### 7. "Every test must be able to fail" — required demonstration (S01 scope)

This is test-infrastructure. Prove the harness can detect failures **without
touching any production code** — the entire demonstration stays inside
`tests/e2e/**`.

Create `tests/e2e/test_harness_selfcheck.py` — **unmarked** unit tests (no
`@pytest.mark.e2e`) that exercise the wrapper's pure failure-detection
functions with synthetic in-memory input. No browser and no E2E stack are
needed, so these run here in S01:

1. **Console-error detection**: call `read_console_errors()` /
   `assert_no_console_errors()` with a synthetic console log string/file that
   contains an `error`-level line; assert the helper flags it (returns the
   error / raises `AssertionError`). Also assert the clean-input case passes.
2. **Accessibility check**: call `accessibility_check()` with a synthetic
   snapshot that has no landmark region; assert it reports a violation. Assert
   a snapshot with a landmark passes.

Write each self-check test RED-first (it fails before the corresponding helper
is implemented). Run them with `uv run pytest tests/e2e/test_harness_selfcheck.py -v`
and record the RED run (the failing snippet — `AssertionError`, not a
collection/import error) and the subsequent GREEN run as your
`tdd_red_evidence`.

Additionally, in `test_journey_home_navigation.py`, add a one-line comment naming
the single behavioural assertion that, if inverted, proves the journey can
fail (the actual inverted-assertion RED run happens at S14, where the live
stack exists).

You MUST NOT edit `dashboard/`, `orch/`, or `executor/` for any reason —
including a "temporary" break that you revert. The merge-time scope gate
enforces `scope.allowed_paths`; a residual edit fails the merge and a
reverted-but-thrashy edit wastes the step budget. `git status` / `git diff`
must show changes only under the paths in `scope.allowed_paths`.

## Project Conventions

Read `CLAUDE.md` and `tests/CLAUDE.md` for:
- The live-DB guard (never touch port 5433)
- `pytest-randomly` being on by default (your new tests must be order-independent
  — each journey must set up and tear down its own browser state)
- The assertion-strength rules in `skills/iw-ai-core-testing/SKILL.md`
- The playwright-cli rules: `kill-all` before open; `goto` after the first
  `open_url`; `snapshot` before every `click`/`fill`; never hardcode ports
- The screenshot idiom: `playwright-cli screenshot` saves to
  `.playwright-cli/page-<ts>.png`; copy the latest file to the dest with
  `ls -t .playwright-cli/page-*.png | head -1`

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `completion_status: complete`, run in order and fix anything
they report:

1. `make format` — auto-fixes formatting drift; inspect the diff and re-stage.
2. `make typecheck` — zero errors involving files you touched.
3. `make lint` — zero errors.

Also run `make test-assertions` — your new test files must not trip the
assertion scanner (no no-assert / tautology / mock-only / bare
`pytest.raises`). Every journey must have a meaningful `assert` that would
fail if the production code regressed.

## Test Verification (NON-NEGOTIABLE)

Verify the marker exclusion works — `e2e`-marked **journey** tests must NOT be
collected by the default selection:

```bash
uv run pytest tests/e2e/ --collect-only -q
# expect: only test_harness_selfcheck.py tests collected;
#         ZERO e2e-marked journey tests (deselected by the addopts -m filter)
```

Verify the smoke target selects the right tests:

```bash
uv run pytest tests/e2e/ -m e2e_smoke --collect-only -q
# expect: test_journey_home_navigation collected
```

Run the harness self-check unit tests (these need no browser or E2E stack):

```bash
uv run pytest tests/e2e/test_harness_selfcheck.py -v
# expect: all self-check tests pass (after the RED-first demonstration)
```

Do not run the full `make test-e2e` suite here — that requires the live E2E
stack and is the S14 qv-browser step's job. Do not report `tests_passed: true`
based on collection-only checks — report what you actually ran and what passed.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "F-00088",
  "completion_status": "complete|partial|blocked",
  "files_changed": [],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "collection verified: test_journey_home_navigation under -m e2e_smoke; 0 e2e-marked journey tests under default addopts; test_harness_selfcheck.py self-check tests pass",
  "tdd_red_evidence": "harness self-check (tests/e2e/test_harness_selfcheck.py, in scope, no production code touched) — console-error detector: RED before assert_no_console_errors() implemented, GREEN after, flags a synthetic error log; accessibility check: RED then GREEN, flags a synthetic landmark-less snapshot. No dashboard/orch/executor file edited (git diff confined to scope.allowed_paths).",
  "blockers": [],
  "notes": "playwright-cli binary found at ~/.local/bin/playwright-cli. e2e and e2e_smoke markers registered. addopts updated. Makefile targets added. Journey 1 implemented."
}
```
