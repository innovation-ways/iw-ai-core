# CR-00075_S01_Backend_prompt

**Work Item**: CR-00075 — Security Test Module
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

This CR adds **no migration** and **no schema change**. You MUST NOT
create, modify, or apply any alembic migration. If your work appears to
need one, STOP and raise a blocker — that means the scope is wrong.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — prefer `uv run iw item-status CR-00075 --json` for the current step list, gate commands, and prompt paths. `workflow-manifest.json` is a design-time snapshot and may be out of date (CR-00023).
- `ai-dev/work/CR-00075/CR-00075_CR_Design.md` — the design document. **Read it in full before writing any code.**
- `ai-dev/work/CR-00075/CR-00075_Functional.md` — human-facing summary.
- Reference patterns: `tests/dashboard/test_chat_security.py` (the canonical authz test pattern), `tests/integration/test_agent_migrate_guard.py` (agent-context guard pattern), `tests/integration/test_live_db_guard_log_level.py` (live-DB guard pattern), `tests/integration/conftest.py` and `tests/conftest.py` (shared fixtures).

## Output Files

- `ai-dev/work/CR-00075/reports/CR-00075_S01_Backend_report.md` — step report.

## Context

You are implementing **all of CR-00075** — it is a single-step test-infrastructure
change. Read `CLAUDE.md` and `tests/CLAUDE.md` for project conventions before
starting. Read `skills/iw-ai-core-testing/SKILL.md` — it is MUST-read for any
test work here.

This CR adds a security test module. **It is strictly test-only: you MUST NOT
edit any production code** (`orch/`, `dashboard/`, `executor/`, `scripts/` —
except where explicitly listed below). The merge-time scope gate enforces this
against `scope.allowed_paths`.

**CRITICAL — genuine vulnerability handling.** If any test you write surfaces a
genuine vulnerability (a real SSRF, a real path-traversal, a guard that does not
fire on current `main`), you MUST:
1. Write the test as the failing reproduction (it fails on `main`).
2. Mark it `@pytest.mark.xfail(strict=False, reason="<one-liner>")`.
3. Add a `# NOTE: genuine vulnerability — TODO(file-incident: SECURITY) <one-line rationale>` comment.
4. List the finding prominently under an **"Operator follow-up — SECURITY"** heading
   in your step report (test name + rationale + a short repro snippet) so the
   operator can file a high-priority security Incident on `main` post-merge. Do NOT
   run `/iw-new-incident` from inside the worktree — it would create an
   `ai-dev/active/I-NNNNN/` package outside `scope.allowed_paths` and fail the
   merge-time scope gate.
5. Do NOT edit any production code to fix the vulnerability — the CR stays strictly
   test-only. A genuine vulnerability is not a blocker for this CR; list it under
   "Operator follow-up — SECURITY" and keep going.

## Requirements

### 1. Package skeleton — `tests/integration/security/__init__.py`

Create the package marker so pytest discovers the new modules. No content needed
beyond the docstring:

```python
"""Security regression tests for IW AI Core."""
```

### 2. Live-DB write-guard — `tests/integration/security/test_live_db_write_guard.py`

Create a regression net for the I-00041 class of outage.

- Read `orch/db/session.py` to understand `safe_create_engine`, `is_live_db_url`,
  and `LiveDbConnectionRefusedError` (or the equivalent exception).
- Read `tests/integration/test_live_db_guard_log_level.py` for the existing pattern.
- **NEVER connect to port 5433.** Use `monkeypatch` / env-var injection to simulate
  what a live-DB URL looks like (`IW_CORE_DB_HOST`, `IW_CORE_DB_PORT`). Assert that
  `is_live_db_url()` returns `True` for the constructed URL and that `safe_create_engine()`
  raises `LiveDbConnectionRefusedError` (or equivalent) when given that URL.
- Cover at least two contexts:
  1. **Test-collection context**: assert the guard fires when env vars point at the
     live host:port, simulating what would happen if a test accidentally loaded
     `orch.db.session` with live-DB env vars active.
  2. **Agent-worktree context**: assert the guard fires when `IW_CORE_AGENT_CONTEXT=true`
     is set alongside a live-DB URL — the guard must remain active in worktrees.
- Every assertion must be behavioural: the guard raises, not merely logs. If the
  current implementation only logs on a live-DB URL (and does not raise), write the
  test as the failing reproduction (xfail + `TODO(file-incident)` placeholder —
  see the genuine vulnerability handling section above), do NOT weaken the assertion.
- Tests must be order-independent under `pytest-randomly`. Use `monkeypatch` for
  env-var injection so teardown is automatic.

### 3. Authorization negative paths — `tests/integration/security/test_authz_negative_paths.py`

Create systematic authorization negative-path tests.

- Read `tests/dashboard/test_chat_security.py` for the current authz test pattern
  and the `TestClient` + `app.dependency_overrides[get_db]` setup.
- Build the `TestClient` using `create_app()` from `dashboard.app`, overriding
  `get_db` to use the testcontainer `db_session` fixture (pop `IW_CORE_EXPECTED_INSTANCE_ID`
  so the identity check does not interfere). Follow the pattern in
  `tests/dashboard/test_jobs_filter_ui.py` for the override setup.
- For each protected route or action you test, send at least one request:
  - With no credentials (unauthenticated, if the route has auth).
  - With wrong-scope or cross-project credentials (if the route is scoped).
- Assert the response is a 4xx — never data, never a 5xx. The assertion must check
  both the status code and, where possible, that the response body does not contain
  data the caller should not see.
- Cover the chat endpoints (as in `test_chat_security.py`) and any other explicitly
  authz-bearing routes. Read the router list in `dashboard/routers/` to identify
  candidates — document your coverage decision in a module-level comment.
- If a route is found to incorrectly return data or a 5xx for an unauthorized request,
  that is a genuine vulnerability — apply the genuine vulnerability handling protocol
  above (xfail + `TODO(file-incident)` placeholder + Operator follow-up section).

### 4. Doc-render SSRF and path-traversal — `tests/integration/security/test_doc_render_ssrf_path_traversal.py`

Create SSRF and path-traversal tests for the doc-render pipeline.

- Read `orch/doc_service.py` and `orch/doc_sections.py` to understand the entry
  points that accept user-supplied paths or URLs. Read the `doc-system/` editorial
  config structure.
- Identify the function(s) that process external paths or URLs (e.g. a function
  that fetches a URL to render content, a function that reads a file by path from
  editorial config, etc.).
- Test with the following input classes:
  1. `file://` URLs (e.g. `file:///etc/passwd`) — assert the function raises or
     returns a safe sentinel, never returns the file contents.
  2. Path traversal strings (e.g. `../../etc/passwd`, `../../../etc/hostname`) —
     assert the function raises or returns a safe sentinel.
  3. Internal-URL SSRF attempts (e.g. `http://127.0.0.1:5433/`, `http://localhost:9900/admin`) —
     assert the function raises or returns a safe sentinel, never makes the request.
- If no entry point currently accepts user-supplied paths or URLs, document this
  finding in your step report as a "No SSRF/path-traversal surface found" note and
  write a single test that asserts a safe-render helper is present or that an attempt
  to supply a `file://` URL to the render path raises `TypeError` or `ValueError`.
  This is acceptable; do not invent a surface that does not exist.
- If a genuine SSRF or path-traversal is found, apply the genuine vulnerability
  handling protocol above (xfail + `TODO(file-incident)` placeholder + Operator
  follow-up section).
- Tests must not make real network requests. Use `monkeypatch` or `unittest.mock` to
  prevent any outbound HTTP call from reaching a real address — assert the mock was
  never called with an internal URL.

### 5. Agent-context env-var handling — `tests/integration/security/test_agent_context_env_handling.py`

Create env-var handling tests for the agent-context flag.

- Read `tests/integration/test_agent_migrate_guard.py` for the existing pattern.
  Your module extends and organises those patterns; it does not replace the file.
- Assert that with `IW_CORE_AGENT_CONTEXT=true` set via `monkeypatch`:
  1. Operator-only commands (at minimum: migration apply, any command guarded by
     the agent-context check) raise or return a refusal.
  2. The refusal is explicit (raises an exception or returns a non-zero exit code or
     a clear error message) — not merely a silent no-op.
- Assert at least one bypass attempt is also blocked:
  - Provide `IW_CORE_AGENT_CONTEXT=True` (capital `T`) — should still block.
  - Provide `IW_CORE_AGENT_CONTEXT=1` — should still block (or document clearly
     if only the exact string `"true"` is accepted).
  - Temporarily unset the env var then re-set it within the same test invocation —
    the guard should re-read the live env var, not cache a stale value.
- Use `monkeypatch` for all env-var injection. Tests must be order-independent.

### 6. Makefile target — `test-security-module`

Add a convenience target to `Makefile`:

```
test-security-module:  ## Run asserted security regression tests (distinct from make security-secrets / make security-sast scanners)
	uv run pytest tests/integration/security/ -v --no-cov
```

Add `test-security-module` to the `.PHONY` line.

Include a comment in the Makefile block that explicitly distinguishes this target
from the scanner targets:

```
# NOTE: test-security-module runs pytest-asserted security regression tests.
# It is NOT a replacement for make security-secrets (gitleaks) or make security-sast
# (Semgrep/bandit), which run scanner tools that produce advisory output.
```

### 7. Docs, skill, and plan updates

- `docs/IW_AI_Core_Testing_Strategy.md`: document the new security test layer —
  add it to the layers section (§3), add a gate-table row noting it runs under
  `integration-tests` (§5), and flip the relevant "known gap" rows (§9) that
  describe missing security regression coverage.
- `skills/iw-ai-core-testing/SKILL.md`: add a short sub-section describing the
  security test module — what it covers, how to extend it (a new security risk class
  gets a new module under `tests/integration/security/`; a genuine vulnerability
  discovered during implementation gets an xfail + `TODO(file-incident)` placeholder
  and operator follow-up, not a production fix within the CR). Then run
  `uv run iw sync-skills --force iw-ai-core-testing`
  and verify `.claude/skills/iw-ai-core-testing/SKILL.md` is byte-identical to
  the master.
- `ai-dev/work/TESTS_ENHANCEMENT.md`: set item 3.5's status to
  `DONE 2026-05-21 (CR-00075)` with the link; add a `## 11. Changelog` entry
  dated 2026-05-21 summarising what shipped (the four security modules, any
  xfailed vulnerabilities with their `TODO(file-incident)` placeholders and
  one-line rationales, the Makefile target added).

## "Every test must be able to fail" — required demonstration

This is a test-infrastructure CR, so there is no production code to RED-GREEN.
Instead, **prove each new test module can fail** — and do it **entirely within
the new test files**, never by editing production `orch/`, `dashboard/`,
`executor/`, or `scripts/` code (those are out of scope; a botched revert would
disable a real safety guard and trip the merge-time scope gate):

1. **Live-DB write-guard**: temporarily invert one assertion inside
   `test_live_db_write_guard.py` — e.g. assert the guard *allows* the live-DB
   connection rather than refusing it. Run `make test-security-module`, confirm
   the case fails RED, then **revert the test-file edit**.
2. **Doc-render SSRF/path-traversal**: temporarily weaken one assertion inside
   `test_doc_render_ssrf_path_traversal.py` — e.g. assert the `file://` input is
   *accepted* rather than refused. Run the module, confirm it fails RED, then
   **revert the test-file edit**.
3. **Authz negative paths**: temporarily invert one assertion inside
   `test_authz_negative_paths.py` — e.g. assert a 2xx is returned rather than a
   4xx. Run the module, confirm it fails RED, then **revert the test-file edit**.
4. **Agent-context env-var**: temporarily invert one assertion inside
   `test_agent_context_env_handling.py` — e.g. assert the operator-only command
   is *allowed* rather than blocked. Run the module, confirm it fails RED, then
   **revert the test-file edit**.

Record all demonstrations (failing output snippets) as your `tdd_red_evidence`.
Before reporting completion, confirm via
`git diff origin/main -- orch/ dashboard/ executor/ scripts/` that it is
**empty** (no production code touched) and that **no inverted assertion remains**
in the committed test files.

## Project Conventions

Read `CLAUDE.md` and `tests/CLAUDE.md` for: the live-DB guard (never touch port
5433), the testcontainer rules, the `dashboard.routers.*` collection-time import
gotcha, `pytest-randomly` being on by default (your new tests must be
order-independent), and the assertion-strength rules in
`skills/iw-ai-core-testing/SKILL.md`. Match existing code in
`tests/integration/`.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `completion_status: complete`, run in order and fix anything
they report:

1. `make format` — auto-fixes formatting drift; inspect the diff and re-stage.
2. `make typecheck` — zero errors involving files you touched.
3. `make lint` — zero errors.

Also run `make test-assertions` — your new test files must not trip the
assertion scanner (no no-assert / tautology / mock-only / bare
`pytest.raises`). Every test body must have a meaningful behavioural assert.

## Test Verification (NON-NEGOTIABLE)

Run **only your own new test files** — do NOT run the full suite (that is the
QV gates' job, S08/S09/S10):

```bash
uv run pytest tests/integration/security/ -v --no-cov
```

Also confirm the modules are collected by the default integration-test run:

```bash
uv run pytest tests/integration/security/ --collect-only -q
# expect: all four modules collected, no markers excluding them
```

Do not report `tests_passed: true` unless all four modules are green (genuine
vulnerabilities xfailed with Incident IDs).

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "CR-00075",
  "completion_status": "complete|partial|blocked",
  "files_changed": [],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, Y xfailed, 0 failed (security modules)",
  "tdd_red_evidence": "deliberate-break demonstrations — entirely within test files, no production code touched: (1) live-DB guard: inverted assertion in test_live_db_write_guard.py (asserted guard allows connection), case failed RED, edit reverted; (2) doc-render: weakened assertion in test_doc_render_ssrf_path_traversal.py (asserted file:// input accepted), case failed RED, edit reverted; (3) authz: inverted assertion in test_authz_negative_paths.py (asserted 2xx rather than 4xx), case failed RED, edit reverted; (4) agent-context: inverted assertion in test_agent_context_env_handling.py (asserted command allowed), case failed RED, edit reverted. git diff origin/main -- orch/ dashboard/ executor/ scripts/ is empty.",
  "blockers": [],
  "notes": "Operator follow-up — SECURITY (genuine vulnerabilities with TODO(file-incident) placeholders): <list or 'none'>. xfailed tests: <N>. Total security tests: <T>."
}
```

- In `notes`, report: total security tests, how many are xfailed with
  `TODO(file-incident)` placeholders (and the one-line rationale for each), and
  whether any "Operator follow-up — SECURITY" items were raised.
- A genuine vulnerability is NOT a blocker for this CR — it is allowlisted via xfail
  and listed for the operator. Set `completion_status: partial` only if the security
  modules cannot be made green for some other reason (e.g. a harness artefact you
  could not resolve).
