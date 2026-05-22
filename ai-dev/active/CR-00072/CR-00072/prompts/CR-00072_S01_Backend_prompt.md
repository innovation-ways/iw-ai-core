# CR-00072_S01_Backend_prompt

**Work Item**: CR-00072 — Contract / No-5xx Route Sweep + schemathesis Fuzzing
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

- **Runtime step state** — prefer `uv run iw item-status CR-00072 --json` for the current step list, gate commands, and prompt paths. `workflow-manifest.json` is a design-time snapshot and may be out of date (CR-00023).
- `ai-dev/work/CR-00072/CR-00072_CR_Design.md` — the design document. **Read it in full before writing any code.**
- `ai-dev/work/CR-00072/CR-00072_Functional.md` — human-facing summary.
- Reference patterns: `tests/dashboard/test_jobs_filter_ui.py` (the canonical `TestClient` + `app.dependency_overrides[get_db]` pattern), `tests/dashboard/conftest.py`, `tests/integration/conftest.py`, `tests/integration/test_jobs_api.py` (`_seed_all_sources`).

## Output Files

- `ai-dev/work/CR-00072/reports/CR-00072_S01_Backend_report.md` — step report.

## Context

You are implementing **all of CR-00072** — it is a single-step test-infrastructure
change. Read `CLAUDE.md` and `tests/CLAUDE.md` for project conventions before
starting. Read `skills/iw-ai-core-testing/SKILL.md` — it is MUST-read for any
test work here.

This CR adds a contract test layer. **It is strictly test-only: you MUST NOT
edit any production code** (`orch/`, `dashboard/`, `executor/`, `scripts/` —
except where explicitly listed below). The merge-time scope gate enforces this
against `scope.allowed_paths`.

## Requirements

### 1. Route-contract sweep — `tests/dashboard/test_route_contract_sweep.py`

Create a new test module that enumerates every dashboard route and asserts none
return a 5xx.

- Build the app with `create_app()` from `dashboard.app`. Override `get_db`
  (from `dashboard.dependencies`) to return the testcontainer `db_session`
  fixture — follow the fixture pattern in `tests/dashboard/test_jobs_filter_ui.py`
  (including popping `IW_CORE_EXPECTED_INSTANCE_ID` so the identity check does
  not interfere).
- **The `TestClient` for the sweep MUST be constructed with
  `raise_server_exceptions=False`** — otherwise a 500 raises an exception
  instead of returning a response you can assert on.
- **Seed a representative dataset** into `db_session` before the sweep: at least
  one `Project`, one or two `WorkItem`s, one `Batch`, one doc, and one job-like
  row. Reuse existing seed helpers where they exist (`_seed_all_sources` in
  `tests/integration/test_jobs_api.py`, the `test_project` fixture, helpers under
  `scripts/e2e_seed.py` if importable without side effects). If you need a shared
  helper, add it under `tests/fixtures/` or `tests/dashboard/conftest.py` — both
  are in scope.
- Enumerate `app.routes`. For each route that includes `"GET"` (or `"HEAD"`) in
  its `methods`:
  - **Skip set (documented):** streaming/SSE routes (anything served by
    `dashboard/routers/sse.py`, and any other endpoint that streams), the static
    files mount, and FastAPI's own `/openapi.json` / swagger UI if present.
    Put the skip list in a module-level constant with a one-line rationale per
    entry.
  - **Path parameters:** build a substitution map from the seeded data
    (`project_id`, `item_id`, `batch_id`, doc id, job id, …) and format the
    route path with real values. A route whose parameters cannot all be resolved
    goes into a module-level `UNRESOLVED` list; the test asserts `UNRESOLVED`
    equals an explicitly-reviewed expected set, so a newly-added unresolvable
    route fails the test rather than being silently dropped.
  - Issue the request and assert `response.status_code < 500`.
- **Parametrize one case per route** (`@pytest.mark.parametrize`) so a failure
  names the exact route (use the route path as the param id).
- **`EXPECTED_5XX` allowlist:** a module-level dict keyed by route path. If the
  sweep finds a *genuine* 5xx on current `main` (a real handler bug, not a
  test-harness artefact like a missing seed row or an unresolved parameter),
  add the route to `EXPECTED_5XX` with a `TODO(file-incident)` placeholder and a
  one-line rationale, and `xfail` that parametrized case. **Investigate every
  5xx before allowlisting it** — most will be harness artefacts you should fix
  in the test (better seed data, a resolvable parameter). Only genuine handler
  bugs get allowlisted. **Do NOT file the Incident yourself** — running
  `/iw-new-incident` from inside the worktree would create an incident package
  under `ai-dev/active/I-NNNNN/`, which is outside `scope.allowed_paths` and
  would fail the merge-time scope gate. Instead, for each genuine bug, record a
  `TODO(file-incident)` placeholder in `EXPECTED_5XX` and list it prominently in
  your step report under an **"Operator follow-up"** heading (route, one-line
  rationale, a short failing-response snippet) so the operator files the
  Incident on `main` post-merge. A genuine pre-existing 5xx is **not** a
  blocker — allowlist it, `xfail` it, report it, and keep going.
- The sweep MUST exit 0 on current `main` once harness artefacts are fixed and
  genuine bugs are allowlisted.

### 2. schemathesis fuzz module — `tests/dashboard/test_schemathesis_contract.py`

Create a new module that property-fuzzes the JSON API endpoints.

- Add `schemathesis` to the `[dependency-groups] dev` group in `pyproject.toml`.
  Pin to the **current major version** — consult the schemathesis docs (use the
  context7 MCP server or the project's research tooling) for the current release
  and the correct API; the library's API has changed across majors, so verify
  the loader (`schemathesis.openapi.from_asgi` / `from_asgi`) and the
  `not_a_server_error` check against the version you pin. Regenerate `uv.lock`.
- The module loads the app's OpenAPI schema from `create_app()` and restricts
  generated operations to the app's **JSON API operations** — defined precisely
  as operations whose OpenAPI response declares an `application/json` media type
  (handlers returning `JSONResponse` or a pydantic model, not `HTMLResponse`).
  In today's dashboard that is the keep-alive API (`/api/keep-alive/*`), the
  runtime-overrides endpoint, and the JSON job endpoints. Use schemathesis's
  operation filtering (filter by response content type, or by an explicit path
  allowlist you derive from that rule) — do NOT fuzz the HTML/htmx routes; those
  are covered by the route sweep. If the resulting operation set is small, that
  is expected — the dashboard is predominantly HTML/htmx.
- Every generated case asserts schemathesis's `not_a_server_error` check (the
  response is never a 5xx). Wire the testcontainer `db_session` via the same
  `get_db` override so the fuzzed requests hit a real seeded DB.
- **Mark the entire module `contract_fuzz`** (module-level `pytestmark` or a
  per-test marker) so it is excluded from the default suite.
- **Assertion-scanner interaction.** A schemathesis test whose body is just
  `case.call_and_validate()` has no literal `assert`, so the `assertions` QV
  gate (S05, `make test-assertions`) will flag it `no-assert` — a NEW violation
  that fails the gate with no fix cycle. Either capture the response and assert
  explicitly (`assert response.status_code < 500`), **or** add
  `# noqa: assertion-scanner` to the test's `def` line — the scanner honours
  that suppression and `tests/dashboard/test_schemathesis_contract.py` is in
  scope. Do NOT edit `tests/assertion_free_baseline.txt` (out of scope).

### 3. `contract_fuzz` marker + `addopts` exclusion — `pyproject.toml`

- Register the `contract_fuzz` marker in `[tool.pytest.ini_options].markers`
  with a prose description (model on the existing `browser` / `quarantine`
  entries): contract fuzzing is slow and runs nightly, not in the blocking suite.
- Extend the `addopts` `-m` filter from
  `-m 'not browser and not quarantine'` to
  `-m 'not browser and not quarantine and not contract_fuzz'`.
  Keep `--strict-markers` and every other existing flag intact.

### 4. Makefile targets

- `test-route-sweep` — `uv run pytest tests/dashboard/test_route_contract_sweep.py -v --no-cov` (convenience; the `integration-tests` gate already runs it via `make test-integration`).
- `test-contract-fuzz` — `uv run pytest tests/dashboard/test_schemathesis_contract.py -m contract_fuzz -v --no-cov`.
- Add both target names to the `.PHONY` line.

### 5. Nightly workflow — `.github/workflows/contract-fuzz.yml`

- Triggers: a nightly `schedule:` cron **and** `workflow_dispatch:`. It MUST NOT
  trigger on `push` or `pull_request`.
- One job that checks out the repo, sets up the environment, and runs
  `make test-contract-fuzz`. Mirror the environment setup of `test-quality.yml`'s
  `integration` job (Python/uv setup, any postgres/Docker provisioning the
  testcontainer fixtures need). Read `test-quality.yml` and copy its proven setup.
- The job is **non-failing during burn-in**: set `continue-on-error: true` at job
  level (mirror how `test-quality.yml` / `security-scan.yml` handle burn-in jobs).

### 6. Docs, skill, and plan updates

- `docs/IW_AI_Core_Testing_Strategy.md`: document the new contract test layer —
  add it to the layers section (§3), add a gate-table row (§5), and flip the
  relevant "known gap" rows (§9) that describe the missing route/contract
  coverage.
- `skills/iw-ai-core-testing/SKILL.md`: add a short sub-section describing the
  contract sweep layer — what it does, and how to extend it (a newly-added route
  is covered automatically; a newly-added JSON endpoint should be considered for
  the schemathesis filter). Then run `uv run iw sync-skills --force iw-ai-core-testing`
  and verify `.claude/skills/iw-ai-core-testing/SKILL.md` is byte-identical to
  the master.
- `ai-dev/work/TESTS_ENHANCEMENT.md`: set item 3.2's status to
  `DONE 2026-05-21 (CR-00072)` with the link; add a `## 11. Changelog` entry
  dated 2026-05-21 summarising what shipped (route sweep + schemathesis nightly,
  the `EXPECTED_5XX` allowlist outcome with counts, any `TODO(file-incident)`
  placeholders raised for operator follow-up);
  update the §9 CI-gate-matrix prose if the contract sweep / schemathesis belong
  in the blocking / periodic lists.

## "Every test must be able to fail" — required demonstration

This is a test-infrastructure CR, so there is no production code to RED-GREEN.
Instead, **prove each new test can fail** — and do it **entirely within the new
test files**, never by editing production `dashboard/` or `orch/` code (those
are out of scope; a botched revert would trip the merge-time scope gate):

1. **Route sweep**: register a throwaway, deliberately-5xx route on the test's
   own `create_app()` instance — e.g. add a `GET /__cr72_selfcheck__` handler
   that does `raise RuntimeError("CR-00072 sweep check")`. The sweep enumerates
   `app.routes`, so it picks the throwaway route up. Run `make test-route-sweep`,
   confirm that route's parametrized case fails with a 5xx, then **remove the
   throwaway route**.
2. **schemathesis**: register a throwaway JSON route on the test app that 5xx's
   and falls inside the fuzz filter, run `make test-contract-fuzz`, confirm it
   reports the `not_a_server_error` failure, then **remove the throwaway route**.

Record both demonstrations (the failing output snippets) as your
`tdd_red_evidence`. Before reporting completion, confirm via
`git diff origin/main -- dashboard/ orch/` that it is **empty** (no production
code touched) and that **no throwaway route remains** in the committed test
files.

## Project Conventions

Read `CLAUDE.md` and `tests/CLAUDE.md` for: the live-DB guard (never touch port
5433), the testcontainer rules, the `dashboard.routers.*` collection-time import
gotcha, `pytest-randomly` being on by default (your new tests must be
order-independent), and the assertion-strength rules in
`skills/iw-ai-core-testing/SKILL.md`. Match existing code in `tests/dashboard/`.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `completion_status: complete`, run in order and fix anything
they report:

1. `make format` — auto-fixes formatting drift; inspect the diff and re-stage.
2. `make typecheck` — zero errors involving files you touched.
3. `make lint` — zero errors.

Also run `make test-assertions` — your new test files must not trip the
assertion scanner (no no-assert / tautology / mock-only / bare
`pytest.raises`). The sweep's assertions are real (`status_code < 500`); make
sure every test body has a meaningful assert.

## Test Verification (NON-NEGOTIABLE)

Run **only your own new test files** — do NOT run the full suite (that is the
QV gates' job, S08/S09/S10):

```bash
uv run pytest tests/dashboard/test_route_contract_sweep.py -v --no-cov
uv run pytest tests/dashboard/test_schemathesis_contract.py -m contract_fuzz -v --no-cov
```

Also confirm the marker exclusion works — `contract_fuzz` tests must NOT be
collected by the default selection:

```bash
uv run pytest tests/dashboard/test_schemathesis_contract.py --collect-only -q
# expect: no tests collected (deselected by the addopts -m filter)
```

Do not report `tests_passed: true` unless the sweep is green (genuine 5xx
allowlisted) and the schemathesis module passes under `-m contract_fuzz`.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "CR-00072",
  "completion_status": "complete|partial|blocked",
  "files_changed": [],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, Y xfailed, 0 failed (route sweep); Z passed (schemathesis)",
  "tdd_red_evidence": "deliberate-break demonstration — route sweep: throwaway /__cr72_selfcheck__ route case failed with HTTP 500; schemathesis: throwaway JSON route reported not_a_server_error failure. Both throwaway routes removed; git diff origin/main -- dashboard/ orch/ is empty.",
  "blockers": [],
  "notes": "EXPECTED_5XX allowlist: <N> route(s) — list each with Incident ID. UNRESOLVED routes: <M>. Total routes swept: <T>."
}
```

- In `notes`, report: total routes swept, how many were skipped (with why),
  the `EXPECTED_5XX` count + each route's `TODO(file-incident)` rationale, and
  the `UNRESOLVED` count.
- A genuine pre-existing 5xx is **not** a blocker — allowlist it, `xfail` it,
  and list it under "Operator follow-up" in your step report. Set
  `completion_status: partial` only if the sweep cannot be made green for some
  other reason (e.g. a harness artefact you could not resolve).
