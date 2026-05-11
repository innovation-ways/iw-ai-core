# {TYPE}{NNN}_S{NN}_{Agent}_prompt

**Work Item**: {ID} -- {Title}
**Step**: S{NN}
**Agent**: {Agent}

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

You MUST NOT run the following alembic commands against the live
orchestration DB (port 5433) from an agent context:

```
alembic upgrade head
alembic upgrade <revision>
alembic downgrade <anything>
alembic stamp <anything>
```

Your job in a Database step is to WRITE the migration FILE. The daemon
will apply it as part of the merge pipeline (pre-merge dry-run against
a testcontainer, post-merge apply to live DB). If the migration is
broken, the daemon will refuse to merge the batch.

Allowed for agents:
  - alembic revision --autogenerate -m "..."   (writes a file only)
  - alembic history / current / show           (read-only)
  - Running migrations inside testcontainer fixtures
    (tests/conftest.py does this — agents don't call it directly)

Allowed for OPERATORS only (not agents):
  - uv run iw migrations list-pending          (read-only, safe for anyone)
  - uv run iw migrations dry-run               (testcontainer, safe)
  - uv run iw migrations apply --i-am-operator (refuses if IW_CORE_AGENT_CONTEXT=true)
  - Direct invocation via ./ai-core.sh or make db-migrate (operator entry points)

If your task seems to require applying a migration to the live DB,
STOP and raise a blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — for the current step list, status, prompt paths, gate commands, etc., prefer `uv run iw item-status {ID} --json`. The `workflow-manifest.json` file is a design-time snapshot and may be out of date (CR-00023).
- `ai-dev/work/{ID}/{ID}_{Type}_Design.md` -- Design document
- Previous step reports (if applicable): `ai-dev/work/{ID}/reports/{ID}_S{prev}_*_report.md`

## Output Files

- `ai-dev/work/{ID}/reports/{ID}_S{NN}_{Agent}_report.md` -- Step report

## Context

You are implementing part of **{Work Item Title}**.

Read the design document first to understand the full scope and your step's deliverables. Then read `CLAUDE.md` for project-specific patterns and conventions.

## Requirements

### 1. {First deliverable}

{Detailed description of what to build, referencing design document sections.}

### 2. {Second deliverable}

{Detailed description of what to build, referencing design document sections.}

{Add more numbered deliverables as needed.}

## Project Conventions

Read the project's `CLAUDE.md` for:

- Architecture patterns and layer boundaries
- Coding conventions and naming rules
- Framework-specific patterns (ORM style, API patterns, etc.)
- Test organization and fixtures
- Build and run commands

Follow all rules defined there exactly. When in doubt, match existing code in the repository.

## TDD Requirement

Follow TDD (Red-Green-Refactor):

1. **RED**: Write failing tests first that define the expected behavior.
   Then **run the new failing test** — a *targeted* run only
   (`uv run pytest tests/.../test_x.py -v`), never the full suite.
   **Confirm the failure is for the expected reason** — an
   `AssertionError` or `NotImplementedError`/`AttributeError` from
   missing implementation, *not* an `ImportError`, `SyntaxError`,
   fixture error, or collection error (those mean the test itself is
   broken, not RED). Capture the failing line(s).
2. **GREEN**: Write the minimal implementation to make tests pass.
3. **REFACTOR**: Improve code structure while keeping all tests green.

Do not skip the RED phase. Tests must exist before implementation code.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`, you MUST run these in order
and fix any issues they report. Skipping any of these wastes a fix-cycle slot
when the QV gate steps catch the same issue downstream — see I-00041 finding
[3] for the cost case (S05/S01 shipped unformatted code and an `object not
callable` mypy regression that S09 and S10 caught later, each burning a
fix-cycle).

1. **`make format`** — auto-fixes formatting drift. If it reformats files,
   inspect the diff and re-stage; do NOT skip.
2. **`make typecheck`** — must report zero errors involving the files you
   touched. Errors elsewhere are pre-existing — note them in your report but
   do not ignore your own.
3. **`make lint`** — must report zero errors.

If a tool isn't available in your worktree, STOP and raise a blocker — do not
silently skip.

In your Subagent Result Contract, populate the new `preflight` object recording
the result of each command:
- `"ok"` — ran cleanly, no changes / no errors
- `"fixed"` — applies to `format` only; the tool auto-fixed something
- `"skipped:<reason>"` — only if you raised a blocker explaining why

## Test Verification (NON-NEGOTIABLE)

After implementation, verify your own changes — but **DO NOT run the full
test suite**. Full-suite execution is owned by the dedicated QV gate steps
downstream (`unit-tests`, `integration-tests`, `frontend-tests`); duplicating
them here burns this step's budget and is a common cause of step timeouts
(see I-00073/S03 post-mortem, 2026-05-08).

Scope rules:

1. **Tests step (`tests-impl`)** — run only the test file(s) **you wrote or
   modified** in this step:
   ```bash
   uv run pytest tests/integration/path/to/your_new_test.py -v
   ```
   That is sufficient to prove your tests work. Do **NOT** run
   `make test-integration` or `make test-unit` — those are S{NN} QV gates
   and will run with their own (longer) budgets.

2. **Implementation steps (Backend / API / Database / Frontend / Pipeline /
   Template)** — run the **targeted** unit tests that exercise the code
   path you changed:
   ```bash
   uv run pytest tests/unit/path/to/affected_module/ -v
   ```
   If you cannot identify a narrow target, run the full unit suite — but
   **never** the full integration suite. Integration-suite verification is
   the QV gate's job.

3. Run lint and type checking on your touched files (check Makefile or
   `CLAUDE.md` for project-specific commands).

4. Do **NOT** report `tests_passed: true` unless your targeted tests pass
   with zero failures.

5. If your targeted tests fail, fix them before reporting completion. If
   they pass but you suspect a wider regression, note it in your report
   under `notes` — do not pre-emptively run the full suite to "be safe".

6. **CSS class renames — required test update.** When the design renames a
   CSS class name, grep the test suite for the old class name and update
   every assertion to match the new name before reporting
   `tests_passed: true`. Stale CSS class assertions in tests are a
   code-review failure mode (see CR-00039 self-assess finding [3]).

## Migration Verification (Database steps only — NON-NEGOTIABLE)

If your step generated or modified an alembic migration under
`orch/db/migrations/versions/**`, you MUST run **`make migration-check`**
before reporting completion. This spins a fresh testcontainer Postgres,
runs `alembic upgrade head` from base, asserts the resulting schema matches
`Base.metadata.create_all()` (catches model↔migration drift), and
round-trips through `downgrade base → upgrade head` (catches broken
`downgrade()` bodies).

If `make migration-check` fails, fix the migration file (or the model) so
both halves agree, and re-run until green. Do not report
`tests_passed: true` while this gate is red — downstream agents will inherit
a wrong schema and waste fix-cycles diagnosing the symptom (see F-00079
post-mortem for the cost case: four S19 attempts spent debugging a JS
"e.map is not a function" that traced back to a missing column in a stack
that hadn't applied the new migration).

## Subagent Result Contract

When your work is complete, report results in this JSON structure:

```json
{
  "step": "S{NN}",
  "agent": "{Agent}",
  "work_item": "{ID}",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "path/to/file1.py",
    "path/to/file2.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "tests/unit/test_x.py::test_foo — AssertionError: assert 0 == 42  // captured RED run",
  "blockers": [],
  "notes": ""
}
```

- `tdd_red_evidence`: **Required for Backend steps.** When the step adds
  behavioural test(s), record the test id(s) and a 1–3 line snippet of
  the RED run output (the failure line), e.g. `"tests/unit/test_x.py::test_foo
  — AssertionError: assert 0 == 42"`. When the step legitimately adds no
  behavioural test (pure refactor, config-only, doc/template-only), use
  `"n/a — <one-line reason>"`, e.g. `"n/a — template/markdown edits only,
  no production logic"`. Non-backend steps should use the `"n/a — …"` form
  when no behavioural tests are added.

- `completion_status`: Use `complete` when all deliverables are done and tests pass. Use `partial` if some deliverables are done but others remain. Use `blocked` if external dependencies prevent progress.
- `blockers`: List any issues that prevented full completion. Include enough detail for the orchestrator to decide next steps.
- `notes`: Any context the next step or reviewer should know.
