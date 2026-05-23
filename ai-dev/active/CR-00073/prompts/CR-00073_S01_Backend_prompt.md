# CR-00073_S01_Backend_prompt

**Work Item**: CR-00073 — iw CLI Contract Test Layer
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

- **Runtime step state** — prefer `uv run iw item-status CR-00073 --json` for the current step list, gate commands, and prompt paths. `workflow-manifest.json` is a design-time snapshot and may be out of date (CR-00023).
- `ai-dev/work/CR-00073/CR-00073_CR_Design.md` — the design document. **Read it in full before writing any code.**
- `ai-dev/work/CR-00073/CR-00073_Functional.md` — human-facing summary.
- Reference patterns: `tests/integration/cli/` (existing CLI contract patterns), `tests/integration/test_cli_*.py` (existing integration CLI tests), `tests/integration/conftest.py` (shared fixtures including `db_session`), `tests/unit/properties/test_iw_next_id_atomicity_properties.py` (concurrency pattern for `next-id`).

## Output Files

- `ai-dev/work/CR-00073/reports/CR-00073_S01_Backend_report.md` — step report.

## Context

You are implementing **all of CR-00073** — it is a single-step test-infrastructure
change. Read `CLAUDE.md` and `tests/CLAUDE.md` for project conventions before
starting. Read `skills/iw-ai-core-testing/SKILL.md` — it is MUST-read for any
test work here.

This CR adds a CLI contract test layer. **It is strictly test-only: you MUST NOT
edit any production code** (`orch/`, `dashboard/`, `executor/`, `scripts/` —
except `docs/IW_AI_Core_CLI_Spec.md` and the files explicitly listed in
`scope.allowed_paths`). The merge-time scope gate enforces this against
`scope.allowed_paths`.

If a contract test surfaces a genuine CLI bug, mark that test `pytest.mark.xfail`
(or record it in a `KNOWN_CLI_BUG` allowlist in the affected contract test file)
with a `TODO(file-incident)` placeholder and a one-line rationale — never fix the
production code in this CR, and do NOT run `/iw-new-incident` or create any
`ai-dev/active/I-NNNNN/**` from the worktree (it would land outside
`scope.allowed_paths`). Each placeholder must be surfaced as operator follow-up
under an **"Operator follow-up"** heading in your step report (command + rationale
+ a short failing snippet); the operator files the Incident on `main` post-merge.
A genuine pre-existing CLI bug is NOT a blocker — allowlist it, `xfail` it,
report it, and keep going. A CLI bug is neither spec drift nor a coverage gap, so
it does NOT belong in `KNOWN_SPEC_DRIFT` or `KNOWN_UNTESTED_COMMANDS`.

## Requirements

### 1. Per-command contract tests — `tests/integration/cli/`

Create a test class per priority command. For each command, the class must assert:

1. **Exit code 0** on each documented success path.
2. **Non-zero exit code + clear stderr message** on each documented error path.
3. **stdout shape** matches the documented format (parse or pattern-match the output).
4. **DB row(s)** created or mutated match expectations — query via the testcontainer
   `db_session` after the command runs.
5. **Idempotence / atomicity** where the CLI spec promises it.

Use Click's `CliRunner` (with `mix_stderr=False` so stdout and stderr are
separate) for commands testable in-process. Where a command spawns subprocesses
or relies on process-level env vars, use subprocess invocation — match the pattern
established in the existing `tests/integration/cli/` and `tests/integration/test_cli_*.py`
files. Always inject the testcontainer `db_session` (never touch the live DB on
port 5433).

**Priority commands:**

- **`step-done`** (`tests/integration/cli/test_step_done_contract.py`):
  success paths (marking a step complete with a report), error paths (unknown
  item ID, non-existent step, bad JSON report), stdout shape (the documented
  confirmation message), DB effect (the step row transitions to the expected
  state and the report is stored).

- **`register`** (`tests/integration/cli/test_register_contract.py`):
  success paths (registering a new item; re-registering with the same
  idempotency key), error paths (missing required flags, duplicate ID with
  conflicting data), stdout shape, DB effect (the `WorkItem` row is created or
  is unchanged on a re-registration with the same key).

- **`doc-update`** (`tests/integration/cli/test_doc_update_contract.py`):
  success paths (updating a doc for an existing item), error paths (unknown item,
  missing file), stdout shape, DB effect (the `DocGenerationJob` or doc record
  reflects the update).

- **`approve`** (`tests/integration/cli/test_approve_contract.py`):
  success paths (approving a work item in an approvable state), error paths
  (wrong state, unknown item), stdout shape, DB effect (the `WorkItem` status
  transitions to `approved`). Also test the evidence-ingestion hook that fires on
  approve — verify `orch/evidences.py` is called and the evidence records are
  written (see `orch/cli/item_commands.py`).

- **`next-id`** (`tests/integration/cli/test_next_id_contract.py`):
  success paths (allocating a new ID for each supported type), error paths
  (unknown type), stdout shape (the allocated ID string), DB effect (the counter
  row is incremented and the allocated ID is unique). **Concurrency assertion:**
  use a `ThreadPoolExecutor` to issue N concurrent `next-id` calls and assert
  that all returned IDs are unique — follow the pattern in
  `tests/unit/properties/test_iw_next_id_atomicity_properties.py`.

- **Evidence-ingestion hooks** (`tests/integration/cli/test_evidence_hooks_contract.py`):
  cover the `iw` calls in the approve and step-done flows described in
  `orch/evidences.py` and hooked in `orch/cli/item_commands.py` (approve) and
  `orch/cli/step_commands.py` (step-done). Assert that evidence records are
  written to the DB with the expected payload after the triggering command runs.

### 2. Spec-conformance test — `tests/integration/test_cli_spec_conformance.py`

Create a test module that detects drift between the CLI and its specification.

- **Parse** the **§4 "Command Summary"** section of `docs/IW_AI_Core_CLI_Spec.md`.
  This is the canonical command list and it is a **fenced ASCII tree** (a code
  block drawn with `├──`, `│`, `└──` branch characters) — *not* a Markdown
  table. Do NOT parse the per-command `### 3.x` Markdown tables: those list
  flags and options, not the command set. Extract command names from the tree,
  including the sub-commands nested under group nodes (`migration-lock`,
  `daemon`, `projects`, …). Be robust to the tree-branch characters and
  indentation; do not hard-code a command count.
- **Introspect** the actual Click command tree: import the root group from
  `orch.cli.main` and walk `.commands` recursively to collect the full set of
  registered command names (including sub-commands of groups).
- **Assert bidirectional coverage:**
  1. Every command documented in the spec exists in the CLI.
  2. Every command in the CLI is documented in the spec.
  3. Every spec command either has at least one contract test (scan the test
     files under `tests/integration/cli/` for the command name and assert at
     least one test function references it) **or** is listed in
     `KNOWN_UNTESTED_COMMANDS`.
- **`KNOWN_SPEC_DRIFT` allowlist** (assertions 1 & 2): a module-level dict keyed
  by command name. Each entry carries a `"reason"` (a `TODO(file-incident)`
  placeholder or a one-line rationale) and a `"direction"` (`"spec_only"` or
  `"cli_only"`).
  Existence drift in the allowlist does NOT fail; drift not in it DOES fail.
- **`KNOWN_UNTESTED_COMMANDS` allowlist** (assertion 3): a module-level dict
  keyed by command name, each entry carrying a `"reason"` (one-line rationale).
  **Pre-seed it with every command that does not yet have a contract test** —
  i.e. every command except the 6 priority commands. This is expected to be the
  large majority of commands and is correct: the CR covers priority commands
  first (see the design's Out of Scope). Assertion 3 then fails only when a
  *newly added* command ships with neither a contract test nor an entry here.
  Use a generic rationale such as `"non-priority — contract coverage deferred,
  TESTS_ENHANCEMENT 3.x follow-up"`.
- The live CLI currently exposes well over a dozen commands the §4 summary does
  not document. If `docs/IW_AI_Core_CLI_Spec.md` has genuine doc drift (a
  command exists in the CLI but is missing from §4), **fix the §4 tree
  directly** — it is in `scope.allowed_paths` and editing it is allowed. Prefer
  fixing the doc over adding to `KNOWN_SPEC_DRIFT`; only use that allowlist when
  the drift cannot be resolved in this CR (e.g. the CLI has a command that
  should be removed — a production change requiring its own item).

### 3. `test-cli-contract` Makefile target

Add a convenience target:

```
test-cli-contract:
	uv run pytest tests/integration/cli/ tests/integration/test_cli_spec_conformance.py -v --no-cov
```

Add the target name to the `.PHONY` line. Note: the `integration-tests` gate
(`make test-integration`) already runs these tests automatically; this target is
a developer convenience only.

### 4. Docs, skill, and plan updates

- `docs/IW_AI_Core_Testing_Strategy.md`: document the new CLI contract test
  layer — add it to the layers section (§3), add a gate-table row (§5), and flip
  the relevant "known gap" rows (§9) that describe the missing CLI contract
  coverage.
- `skills/iw-ai-core-testing/SKILL.md`: add a short sub-section describing the
  CLI contract layer — what it does and how to extend it (adding a new command:
  add a test class under `tests/integration/cli/`; updating the spec: re-run the
  conformance test to verify bidirectional coverage holds). Then run
  `uv run iw sync-skills --force iw-ai-core-testing` and verify
  `.claude/skills/iw-ai-core-testing/SKILL.md` is byte-identical to the master.
- `ai-dev/work/TESTS_ENHANCEMENT.md`: set item 3.3's status to
  `DONE 2026-05-21 (CR-00073)` with the link; add a `## 11. Changelog` entry
  (or append to it if it already exists) dated 2026-05-21 summarising what
  shipped (priority commands covered, conformance test, `KNOWN_SPEC_DRIFT` count,
  any `TODO(file-incident)` placeholders raised for operator follow-up).

## "Every test must be able to fail" — required demonstration

This is a test-infrastructure CR, so there is no production code to RED-GREEN.
Prove each new test can fail **entirely within test code, using pytest's
`monkeypatch` fixture** — you MUST NOT edit any file under `orch/` (or the spec
doc, or any production module) even temporarily. `monkeypatch` auto-reverts at
test teardown, so nothing leaks.

1. **Per-command contract test**: in a throwaway demonstration test (or an
   interactive run), use `monkeypatch` to break the command's observable
   behaviour — e.g. `monkeypatch.setattr` the command's DB-write helper to a
   no-op so the expected row is never written, or patch its callback to return a
   non-zero exit. Run the affected contract test and confirm it FAILS. The
   monkeypatch reverts automatically; no `orch/` file is touched.
2. **Spec-conformance test**: use `monkeypatch` to break the conformance
   module's inputs — e.g. patch its spec-parse function to drop one command
   name, or patch its Click-tree introspection to drop one command. Run the
   conformance test and confirm it reports the injected drift. Again the
   monkeypatch reverts automatically — no edit to the spec doc or the CLI.

Record both demonstrations (the failing output snippets) as your
`tdd_red_evidence`. The throwaway demonstration tests, if any, MUST be removed
before reporting completion. Double-check via `git status` / `git diff
origin/main` that **no production file (`orch/`, `dashboard/`, `executor/`,
`scripts/`) was modified at all** — with the monkeypatch approach there is
never a production edit to revert.

## Project Conventions

Read `CLAUDE.md` and `tests/CLAUDE.md` for: the live-DB guard (never touch port
5433), the testcontainer rules, `pytest-randomly` being on by default (your new
tests must be order-independent), and the assertion-strength rules in
`skills/iw-ai-core-testing/SKILL.md`. Match existing code in
`tests/integration/cli/`.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `completion_status: complete`, run in order and fix anything
they report:

1. `make format` — auto-fixes formatting drift; inspect the diff and re-stage.
2. `make typecheck` — zero errors involving files you touched.
3. `make lint` — zero errors.

Also run `make test-assertions` — your new test files must not trip the
assertion scanner (no no-assert / tautology / mock-only / bare
`pytest.raises`). The contract assertions are real (exit code, stderr content,
DB row fields); make sure every test body has a meaningful assert.

## Test Verification (NON-NEGOTIABLE)

Run **only your own new test files** — do NOT run the full suite (that is the
QV gates' job, S08/S09/S10):

```bash
uv run pytest tests/integration/cli/ -v --no-cov
uv run pytest tests/integration/test_cli_spec_conformance.py -v --no-cov
```

Do not report `tests_passed: true` unless all new contract tests pass (genuine
CLI bugs allowlisted with `TODO(file-incident)` placeholders and `xfail`-ed) and
the conformance test passes (pre-existing drift absorbed by `KNOWN_SPEC_DRIFT`).

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "CR-00073",
  "completion_status": "complete|partial|blocked",
  "files_changed": [],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, Y xfailed, 0 failed (contract tests); Z passed (conformance test)",
  "tdd_red_evidence": "monkeypatch demonstration — contract test: <command> case failed with <assertion error> after monkeypatch broke the DB-write/exit; conformance test: injected drift reported after monkeypatch dropped a command. Both via monkeypatch (auto-reverted); git diff origin/main touches no production file.",
  "blockers": [],
  "notes": "KNOWN_SPEC_DRIFT: <N> entry(ies) — list each with TODO(file-incident) placeholder or rationale. KNOWN_UNTESTED_COMMANDS: <M> entry(ies). docs/IW_AI_Core_CLI_Spec.md §4: <K> rows added/fixed. Total contract test count: <T> across 6 priority command groups. KNOWN_CLI_BUG TODO(file-incident) placeholders raised for operator follow-up: <list>."
}
```

- In `notes`, report: total contract tests across all priority command groups,
  the `KNOWN_SPEC_DRIFT` count + each entry with its `TODO(file-incident)` placeholder
  or rationale, the `KNOWN_UNTESTED_COMMANDS` count, how many §4 spec rows you
  added/fixed, and every `TODO(file-incident)` placeholder raised for operator
  follow-up (command + rationale + short failing snippet), under an **"Operator
  follow-up"** heading.
- A genuine pre-existing CLI bug is NOT a blocker — allowlist it, `xfail` it,
  and list it under "Operator follow-up". Set `completion_status: partial` only
  if the contract tests cannot be made green for some other reason.
