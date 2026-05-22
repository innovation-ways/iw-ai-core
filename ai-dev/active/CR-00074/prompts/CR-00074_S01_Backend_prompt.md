# CR-00074_S01_Backend_prompt

**Work Item**: CR-00074 — Cross-Project Isolation Test Matrix
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

- **Runtime step state** — prefer `uv run iw item-status CR-00074 --json` for the current step list, gate commands, and prompt paths. `workflow-manifest.json` is a design-time snapshot and may be out of date (CR-00023).
- `ai-dev/work/CR-00074/CR-00074_CR_Design.md` — the design document. **Read it in full before writing any code.**
- `ai-dev/work/CR-00074/CR-00074_Functional.md` — human-facing summary.
- Reference patterns: `tests/integration/conftest.py` (existing `test_project` fixture), `tests/integration/test_per_worktree_isolation.py` (existing cross-project isolation slice + F-00062 boundary pattern), `tests/integration/test_chat_pi_mixed_tabs_independence.py` (another existing slice), `tests/dashboard/test_jobs_filter_ui.py` (canonical `TestClient` + `app.dependency_overrides[get_db]` pattern), `tests/integration/test_jobs_api.py` (`_seed_all_sources`).

## Output Files

- `ai-dev/work/CR-00074/reports/CR-00074_S01_Backend_report.md` — step report.

## Context

You are implementing **all of CR-00074** — it is a single-step test-infrastructure
change. Read `CLAUDE.md` and `tests/CLAUDE.md` for project conventions before
starting. Read `skills/iw-ai-core-testing/SKILL.md` — it is MUST-read for any
test work here.

This CR adds a systematic cross-project isolation test matrix. **It is strictly
test-only: you MUST NOT edit any production code** (`orch/`, `dashboard/`,
`executor/`, `scripts/` — except where explicitly listed below). The merge-time
scope gate enforces this against `scope.allowed_paths`.

## Requirements

### 1. `second_project` fixture — `tests/integration/conftest.py`

Add a `second_project` fixture that creates a second `Project` row alongside the
existing `test_project`. The fixture must:

- Be function-scoped (consistent with the `pgtestdbpy` template-clone strategy
  from CR-00055 — do NOT introduce shared mutable state across tests).
- Create a `Project` row with a distinct slug, name, and path from `test_project`.
- Seed BOTH projects (project A = `test_project`, project B = `second_project`)
  with at least one of each: `WorkItem`, `Batch`, doc row, code-index row, and
  job-like row. Use identifiable, distinguishable names/titles for each so the
  isolation assertions can check for project A's identifiers in project B's response.
- Reuse existing seed helpers where they exist (`_seed_all_sources` in
  `tests/integration/test_jobs_api.py`, helpers under `tests/fixtures/`). If you
  need a shared helper, add it under `tests/fixtures/` — it is in scope.
- Not break any existing test that uses `test_project` alone — the new fixture is
  purely additive.

### 2. Isolation matrix — `tests/integration/test_cross_project_isolation.py`

Create a new test module implementing the parametrized matrix across four axes.

#### Axis 1: Dashboard-route isolation

- Build the app with `create_app()` from `dashboard.app`. Override `get_db`
  (from `dashboard.dependencies`) to return the testcontainer `db_session`
  fixture — follow the fixture pattern in `tests/dashboard/test_jobs_filter_ui.py`
  (including popping `IW_CORE_EXPECTED_INSTANCE_ID`).
- For every project-scoped dashboard route (routes whose path contains a
  `project_id` or equivalent project-scoping parameter), issue a request
  scoped to project B.
- **Assert the response body contains none of project A's identifiers** — work
  item IDs, batch IDs, doc titles/slugs, job IDs. Use string-search assertions
  (`assert str(proj_a_item_id) not in response.text`, etc.). These are behavioural
  assertions — they would fail if the handler returned the wrong data.
- Parametrize one case per route so a failure names the leaking route.
- **`KNOWN_LEAK` allowlist**: a module-level dict keyed by route path. If you find
  a genuine isolation leak on current `main` (not a test-harness artefact), add
  the route to `KNOWN_LEAK` with a filed **high-priority** Incident ID and a
  one-line rationale, and `xfail` that parametrized case. **Investigate every
  apparent leak before allowlisting** — most will be harness artefacts (wrong
  seed, wrong path parameter). Only genuine handler bugs are allowlisted.
- **A genuine leak is a security/correctness bug — do NOT fix it in production code.**
  File an Incident via `/iw-new-incident` (or flag as a blocker if you cannot)
  and allowlist it. CR-00074 stays test-only.

#### Axis 2: `iw`-command isolation

Project-scoped `iw` commands split into two isolation modes — assert the mode
that matches each command. Consult `orch/CLAUDE.md` (CLI command table),
`docs/IW_AI_Core_CLI_Spec.md`, and `orch/cli/` for the real command set
(`iw list` and `iw queue-status` do NOT exist — do not invent commands).

- **Read/query commands** (e.g. `iw search` with the global `--project` flag,
  `iw item-status`, `iw item-report`) — run the command scoped to project B and
  assert its **output** (stdout, or the `--json` payload) contains **none of
  project A's identifiers** (work item IDs, doc IDs, titles). This is *output
  isolation* — the CLI analogue of Axis 1.
  **Do NOT assert "project A's row counts are unchanged after a read"** — a read
  never mutates rows, so that assertion can never fail; it is vacuous and will
  trip the `make test-assertions` scanner.
- **Mutating commands** (e.g. `iw next-id`, `iw doc-update`) — capture project
  A's relevant row counts AND content, run the command scoped to project B, then
  assert project A's rows are **byte-for-byte unchanged** (*mutation isolation*).
  Also assert the command's effect *did* land on project B (e.g. for `iw
  next-id`, project B's `id_sequences` advanced while project A's did not) — so
  the test fails on both an over-reaching command and a no-op command.
- Parametrize one case per command, with the isolation mode (`output` /
  `mutation`) in the parametrize ID so a failure names the command and what it
  leaked.
- Only project-scoped commands are in scope — skip global commands like
  `iw db-identity check`.
- If a command's isolation is already broken on `main`, add it to the
  `KNOWN_LEAK` allowlist following the same rules as Axis 1.

#### Axis 3: Global-aggregation positive assertion

- Request the global `/docs` and `/jobs` routes (no project scope filter) against
  the same `TestClient`.
- Assert the response body contains identifiers from **both** project A and
  project B.
- Label these cases as `aggregation_check` in the parametrize ID so their intent
  is clear in test output — they are positive assertions, not isolation checks.

#### Axis 4: Per-worktree-DB vs orch-DB boundary (F-00062)

The real F-00062 boundary is the env-var **resolution code** in `orch/config.py`
(`get_db_url()` reads `IW_CORE_DB_*`; `get_orch_db_url()` reads
`IW_CORE_ORCH_DB_*` with a `_prefer` fallback to `IW_CORE_DB_*`). Two unrelated
SQLAlchemy sessions trivially do not share rows — asserting *that* tests Postgres,
not IW AI Core, and is a tautology the `test-assertions` scanner will flag.
Exercise the actual resolution path instead:

- Spin up **two distinct testcontainer Postgres databases**. Point `IW_CORE_DB_*`
  at the first (the per-worktree DB) and `IW_CORE_ORCH_DB_*` at the second (the
  orch DB) via `monkeypatch.setenv`. **Never** call `importlib.reload(orch.config)`
  (CLAUDE.md rule) — `get_db_url()` / `get_orch_db_url()` read `os.environ` fresh
  on every call, so monkeypatch alone is sufficient. Seed each container with a
  distinguishable row.
- Assert `orch.config.get_db_url()` resolves to the per-worktree container and
  `orch.config.get_orch_db_url()` resolves to the orch container — the two URLs
  must **not** be equal.
- Build a SQLAlchemy session (or engine) from each resolved URL and assert the
  per-worktree session sees only per-worktree rows and the orch session sees only
  orch rows.
- Assert the `_prefer` fallback: with `IW_CORE_ORCH_DB_*` unset,
  `get_orch_db_url()` falls back to `IW_CORE_DB_*` and resolves to the
  per-worktree container.
- **Recommended additional case** (not mandatory): the I-00062 agent-context leak
  guard — with `IW_CORE_AGENT_CONTEXT=true` and `IW_CORE_DB_PORT` equal to
  `IW_CORE_ORCH_DB_PORT`, `get_db_url()` raises `RuntimeError`.
- Reference the docker-compose-stack slice in
  `tests/integration/test_per_worktree_isolation.py` and the F-00062 +
  `IW_CORE_DB_*` vs `IW_CORE_ORCH_DB_*` contract in `CLAUDE.md`. Axis 4 is the
  lightweight config-resolution counterpart to that test, not a duplicate.

### 3. Makefile target

- `test-isolation` — `uv run pytest tests/integration/test_cross_project_isolation.py -v --no-cov` (convenience; the `integration-tests` gate already runs it via `make test-integration`).
- Add `test-isolation` to the `.PHONY` line.

### 4. Docs, skill, and plan updates

- `docs/IW_AI_Core_Testing_Strategy.md`: document the new isolation-matrix layer —
  add it to the layers section (§3), add a gate-table row (§5), and flip the
  relevant "known gap" rows (§9) that describe missing cross-project isolation
  coverage.
- `skills/iw-ai-core-testing/SKILL.md`: add a short sub-section describing the
  isolation matrix — what it does, and how to extend it (a new project-scoped
  route or command should be considered for the matrix). Then run
  `uv run iw sync-skills --force iw-ai-core-testing` and verify
  `.claude/skills/iw-ai-core-testing/SKILL.md` is byte-identical to the master.
- `ai-dev/work/TESTS_ENHANCEMENT.md`: set item 3.4's status to
  `DONE 2026-05-21 (CR-00074)` with the link; add a `## 11. Changelog` entry
  dated 2026-05-21 summarising what shipped (isolation matrix, axes covered,
  `KNOWN_LEAK` allowlist outcome with counts, any high-priority Incidents filed);
  update the §9 CI-gate-matrix prose if applicable.

## "Every test must be able to fail" — required demonstration

This is a test-infrastructure CR, so there is no production code to RED-GREEN.
Instead, **prove each new test can fail**:

1. **Isolation matrix (Axis 1)**: temporarily remove the `project_id` filter from
   one project-scoped route handler (e.g. comment out the `.where(Project.id == project_id)`
   clause), run `make test-isolation`, confirm the corresponding parametrized case
   fails (project A's identifier appears in project B's response), then **revert
   the change completely**.
2. **Per-worktree-DB boundary (Axis 4)**: temporarily break the env-var
   resolution in `orch/config.py` — e.g. make `get_orch_db_url()` return
   `get_db_url()`, ignoring `IW_CORE_ORCH_DB_*` — run `make test-isolation`,
   confirm the boundary case fails (the orch session now sees per-worktree
   rows / the two URLs are equal), then **revert the change completely**.

Record both demonstrations (the failing output snippets) as your
`tdd_red_evidence`. Double-check via `git status` / `git diff` that **no
injection remains** before reporting completion.

## Project Conventions

Read `CLAUDE.md` and `tests/CLAUDE.md` for: the live-DB guard (never touch port
5433), the testcontainer rules, the `pgtestdbpy` template-clone strategy
(CR-00055) and its function-scope requirement, `pytest-randomly` being on by
default (your new tests must be order-independent), and the assertion-strength
rules in `skills/iw-ai-core-testing/SKILL.md`. Match existing code in
`tests/integration/`.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `completion_status: complete`, run in order and fix anything
they report:

1. `make format` — auto-fixes formatting drift; inspect the diff and re-stage.
2. `make typecheck` — zero errors involving files you touched.
3. `make lint` — zero errors.

Also run `make test-assertions` — your new test files must not trip the
assertion scanner (no no-assert / tautology / mock-only / bare
`pytest.raises`). The matrix's assertions are real (project A identifiers absent
from project B response); make sure every test body has a meaningful assert.

## Test Verification (NON-NEGOTIABLE)

Run **only your own new test files** — do NOT run the full suite (that is the
QV gates' job, S08/S09/S10):

```bash
uv run pytest tests/integration/test_cross_project_isolation.py -v --no-cov
```

Do not report `tests_passed: true` unless the isolation matrix is green
(genuine leaks allowlisted, tdd_red_evidence recorded).

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "CR-00074",
  "completion_status": "complete|partial|blocked",
  "files_changed": [],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, Y xfailed, 0 failed (isolation matrix)",
  "tdd_red_evidence": "deliberate-break demonstration — Axis 1: <route> case failed with project A identifier in project B response after removing project_id filter; Axis 4: boundary case failed after breaking orch/config.py env-var resolution (get_orch_db_url returned get_db_url). Both injections reverted (git status clean).",
  "blockers": [],
  "notes": "KNOWN_LEAK allowlist: <N> route(s)/command(s) — list each with Incident ID. Total routes asserted: <T>. Commands asserted: <C>. Aggregation routes confirmed: <A>. Boundary cases: <B>."
}
```

- In `notes`, report: total project-scoped routes asserted, total commands asserted,
  the `KNOWN_LEAK` count + each Incident ID, and any genuine leak you could not file
  an Incident for (set `completion_status: partial` and list it in `blockers`).
