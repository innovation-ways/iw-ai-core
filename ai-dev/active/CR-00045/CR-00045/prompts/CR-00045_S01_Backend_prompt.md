# CR-00045_S01_Backend_prompt

**Work Item**: CR-00045 -- Require & verify TDD RED-run evidence from the backend-impl agent
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

- **Runtime step state** — for the current step list, status, prompt paths, gate commands, etc., prefer `uv run iw item-status CR-00045 --json`. The `workflow-manifest.json` file is a design-time snapshot and may be out of date (CR-00023).
- `ai-dev/work/CR-00045/CR-00045_CR_Design.md` -- Design document
- Previous step reports (if applicable): `ai-dev/work/CR-00045/reports/  (none — S01 is the first step)`

## Output Files

- `ai-dev/work/CR-00045/reports/CR-00045_S01_Backend_report.md` -- Step report

## Context

You are implementing **CR-00045 — Require & verify TDD RED-run evidence from the `backend-impl` agent** (the whole CR is one implementation step: this one).

**Read `ai-dev/work/CR-00045/CR-00045_CR_Design.md` first** — the "Current Behavior", "Desired Behavior", "Acceptance Criteria", "Notes", and "Impacted Paths" sections are the source of truth and contain detail this prompt summarises. Also skim `docs/IW_AI_Core_Testing_Strategy.md` §6 and `skills/iw-ai-core-testing/SKILL.md` §5 (they describe the TDD/RED-evidence intent), and read `CLAUDE.md` for project conventions.

This change is markdown (agent definitions + workflow prompt templates) plus one small content-assertion unit test. You are the implementation agent because there is no better fit and — fittingly — you get to demonstrate the very RED-first flow this CR mandates by writing the guard test first.

## Requirements

Do these in order. **Apply TDD: deliverable 1 is your RED test — write it, run it, watch it fail — then deliverables 2–7 make it GREEN.**

### 1. RED — write the guard test (it must fail at this point)

Create `tests/unit/test_tdd_red_evidence_contract.py`: pure file-content assertions (no DB, no I/O concerns — it just reads repo files). Assert that **each** of these files contains the literal marker string `tdd_red_evidence` **and** a short phrase from the mandatory-RED language (pick a stable phrase you introduce in deliverables 2–3, e.g. `run the new failing test`):

- `agents/claude/backend-impl.md`
- `agents/opencode/backend-impl.md`
- `templates/design/Implementation_Prompt_Template.md`
- `ai-dev/templates/Implementation_Prompt_Template.md`
- `templates/design/SelfAssess_Prompt_Template.md`
- `ai-dev/templates/SelfAssess_Prompt_Template.md`
- `templates/design/CodeReview_Prompt_Template.md`
- `ai-dev/templates/CodeReview_Prompt_Template.md`

Also assert each `templates/design/X.md` is byte-identical to its `ai-dev/templates/X.md` counterpart for the three templates above. Run `uv run pytest tests/unit/test_tdd_red_evidence_contract.py -v` and **confirm it fails for the right reason** — an `AssertionError` (the marker strings aren't present yet), *not* an `ImportError`/`SyntaxError`/collection error. Capture the failing line(s) — this is the `tdd_red_evidence` you will report. (You may use `tests/unit/test_template_hints.py` as a structural reference; do not edit that file.)

### 2. `agents/claude/backend-impl.md` and `agents/opencode/backend-impl.md`

In the "Required Workflow" TDD step ("Apply TDD (RED, GREEN, REFACTOR)"), make the RED phase explicit and mandatory: (a) write the failing behavioural test(s); (b) **run the new failing test** — a *targeted* run only (`uv run pytest tests/.../test_x.py -v`), never the full suite; (c) **confirm the failure is for the expected reason** — an `AssertionError` or `NotImplementedError`/`AttributeError`-from-missing-implementation, *not* an `ImportError`, `SyntaxError`, fixture error, or collection error (those mean the test itself is broken, not RED); (d) capture the failing line(s).

In the **Subagent Result Contract** JSON in that file, add a `"tdd_red_evidence"` field adjacent to `tests_passed`/`test_summary`, with the two documented forms:
- behavioural test(s) added → the test id(s) + a 1–3 line snippet of the RED run output (the failure line), e.g. `"tests/unit/test_x.py::test_foo — AssertionError: assert 0 == 42"`;
- no behavioural test added (pure refactor / config-only / doc-or-template-only) → `"n/a — <one-line reason>"`.
Keep the existing fields. Keep `agents/claude/backend-impl.md` and `agents/opencode/backend-impl.md` content-equivalent (mind any deliberate claude-vs-opencode differences already present — only add the new content).

### 3. `templates/design/Implementation_Prompt_Template.md` + `ai-dev/templates/Implementation_Prompt_Template.md`

In the "TDD Requirement" section, spell out the run-and-confirm-reason step (same wording as deliverable 2, including the phrase `run the new failing test`). In the "Subagent Result Contract" JSON block, add `"tdd_red_evidence": "..."` adjacent to `tests_passed`/`test_summary`, with a one-line comment noting it is required for Backend steps and the `"n/a — <reason>"` form is used for non-behavioural steps. Do not bloat non-backend prompts — the field lives in the shared contract block; the prose explains when `"n/a"` applies. Edit **both** files identically.

### 4. `templates/design/SelfAssess_Prompt_Template.md` + `ai-dev/templates/SelfAssess_Prompt_Template.md`

Add a checklist item (in a suitable existing section, or a short new "TDD RED evidence" line), **scoped to behaviour-implementing steps**: *"For each behaviour-implementing step (notably Backend) whose report claims new behavioural tests were added, that report contains `tdd_red_evidence` with a plausible RED failure snippet (`AssertionError` / `NotImplementedError`, not an import/collection error); if it added none, it says so with a one-line justification. Dedicated coverage steps (`tests-impl`) are exempt — they add tests after the code exists and are not RED-first by nature."* Edit **both** files identically.

### 5. `templates/design/CodeReview_Prompt_Template.md` + `ai-dev/templates/CodeReview_Prompt_Template.md`

Add a review check (extend the "Testing" subsection of the Review Checklist, or add a short "TDD RED evidence" item) that applies **when the reviewed step is a behaviour-implementing step** (notably Backend) — dedicated coverage steps (`tests-impl`) are exempt. The reviewer **must** (1) confirm `tdd_red_evidence` is present and plausible for any new behavioural tests; (2) for at least one new behavioural test, **reason about whether it would actually fail against the pre-change production code** and flag any that obviously would not (a test that passes without the new code is not a RED-first test); (3) **optionally**, when quick and safe, scope-stash only the production-code hunks for that test's target, re-run the test to see it fail, then restore — but state explicitly that this stash-recheck is **optional**, not mandatory, because a `git stash` mid-workflow in the worktree is risky. Edit **both** files identically.

### 6. Sync the agent copies

Run `uv run iw sync-agents` so `.claude/agents/backend-impl.md` and `.opencode/agents/backend-impl.md` reflect the master edits. Verify with `git diff` that those two synced files now match their masters (no remaining diff between `.claude/agents/backend-impl.md` and `agents/claude/backend-impl.md`, and likewise for opencode). **Do NOT run `iw sync-templates`** — that propagates to the other managed projects' repos (InnoForge / podforger / cv) and must happen post-merge by the operator, not from this worktree. Note this in your report under `notes`.

### 7. GREEN + REFACTOR, then update the plan

Re-run `uv run pytest tests/unit/test_tdd_red_evidence_contract.py -v` — it must now pass. Run the targeted unit tests for any module you touched (here, just the new test file). Then tick item **0.4** as DONE in `ai-dev/work/TESTS_ENHANCEMENT.md` (Phase 0 table — set its Status to `**DONE <date>** (CR-00045)` and `Link` to `CR-00045`) and add a changelog entry at the bottom.

**Scope discipline**: touch only the files in the design's "Impacted Paths" list (plus this CR's `ai-dev/active|work/CR-00045/**`). Do **not** modify `tests-impl`, `database-impl`, `api-impl`, `frontend-impl`, `pipeline-impl`, or `template-impl` agent definitions, or `tests/unit/test_template_hints.py`. Do **not** add dependencies (no `mutmut`). Do **not** change the workflow-manifest schema.

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

1. **RED**: Write failing tests first that define the expected behavior
2. **GREEN**: Write the minimal implementation to make tests pass
3. **REFACTOR**: Improve code structure while keeping all tests green

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
   `make test-integration` or `make test-unit` — those are the QV-gate
   steps downstream and will run with their own (longer) budgets.

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
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "CR-00045",
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
  "tdd_red_evidence": "tests/unit/test_tdd_red_evidence_contract.py — RED before edits: AssertionError: 'tdd_red_evidence' not found in agents/claude/backend-impl.md (… one line per assertion …); GREEN after deliverables 2–7",
  "blockers": [],
  "notes": "Ran `iw sync-agents` (regenerated .claude/agents/backend-impl.md + .opencode/agents/backend-impl.md). Did NOT run `iw sync-templates` — that propagates to other managed projects' repos and is a post-merge operator step. Item 0.4 ticked DONE in ai-dev/work/TESTS_ENHANCEMENT.md."
}
```

- `completion_status`: Use `complete` when all deliverables are done and tests pass. Use `partial` if some deliverables are done but others remain. Use `blocked` if external dependencies prevent progress.
- `tdd_red_evidence`: **Required.** Because this CR adds a behavioural test (`tests/unit/test_tdd_red_evidence_contract.py`), report the test id(s) and the RED failure line(s) you captured in deliverable 1, before the edits made it green. (For a step that legitimately adds no behavioural test you would instead write `"n/a — <one-line reason>"` — but that does **not** apply here.)
- `blockers`: List any issues that prevented full completion. Include enough detail for the orchestrator to decide next steps.
- `notes`: Any context the next step or reviewer should know — including the sync-agents-yes / sync-templates-no note above.
