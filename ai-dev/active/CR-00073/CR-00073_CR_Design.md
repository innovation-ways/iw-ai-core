# CR-00073: iw CLI Contract Test Layer

**Type**: Change Request
**Priority**: Medium
**Reason**: Phase 3 item 3.3 of the Testing Enhancement Plan — the `iw` CLI is the agent-to-DB bridge, but its exit-code/stdout/DB-effect contract is only piecemeal-tested. Drift between the CLI and its spec doc goes undetected, and no bidirectional check verifies that every documented command exists and every existing command is documented.
**Created**: 2026-05-21
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt — this CR's new tests use the existing testcontainer `db_session` fixture and nothing else.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. **This item leaves migrations unchanged** — it adds no schema change and no migration file.

## Description

Add a CLI contract test layer that proves the `iw` CLI honours its documented contract for each priority command, and add a spec-conformance test that detects drift in either direction between the CLI command tree and `docs/IW_AI_Core_CLI_Spec.md`. The layer lands under `tests/integration/cli/` and is picked up by the existing `integration-tests` gate — no new canonical QV gate is introduced.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Relevant: the `iw` CLI is assembled in `orch/cli/main.py` from ~17 command modules under `orch/cli/`; agents call it to record results (`iw step-done`), allocate IDs (`iw next-id`), register items (`iw register`), and ingest evidences (hooks in the approve / step-done flow described in `orch/evidences.py`); the spec is `docs/IW_AI_Core_CLI_Spec.md`, whose §4 "Command Summary" lists the command tree as a fenced ASCII tree (the live CLI currently exposes more commands than the spec documents — real drift this CR is designed to catch); existing CLI tests live in `tests/integration/test_cli_*.py` and `tests/integration/cli/`; all tests use the testcontainer `db_session` fixture and never the live DB on port 5433. This CR is part of the phased plan in `ai-dev/work/TESTS_ENHANCEMENT.md` (item 3.3).

## Current Behavior

- CLI contract coverage is incidental — a command is tested only if someone wrote a targeted test for it; no test checks the full set of documented exit codes, stdout shapes, DB effects, or idempotence guarantees.
- `tests/integration/test_cli_*.py` and `tests/integration/cli/` exist but do not systematically cover every success path, every documented error path, stdout format, or DB row effects for each command.
- `docs/IW_AI_Core_CLI_Spec.md` lists the command tree in its §4 "Command Summary"; there is no automated check that the actual Click command tree matches the spec (in either direction). Drift — a command added to the CLI but not documented, or a command documented but silently deleted — is only discovered by human inspection. (It already exists at scale: the live CLI has well over a dozen commands the spec omits.)
- There is no `KNOWN_SPEC_DRIFT` allowlist; any pre-existing drift between the CLI and its spec is untracked.
- There is no `test-cli-contract` convenience Makefile target.

## Desired Behavior

### Part A — Per-command contract tests

A new or extended test layer under `tests/integration/cli/` with, for each priority command, a test class asserting:

1. Exit code 0 on each documented success path.
2. A non-zero exit code plus a clear stderr message on each documented error path.
3. stdout shape matches the documented format.
4. The DB row(s) created or mutated match expectations (asserted against the testcontainer `db_session`).
5. Idempotence or atomicity where the CLI spec promises it (e.g. `next-id` atomic allocation, `register` idempotency-key behaviour).

Tests use Click's `CliRunner` against the testcontainer `db_session` fixture, or subprocess invocation where a command spawns subprocesses — matching the existing pattern in `tests/integration/test_cli_*.py` and `tests/integration/cli/`.

**Priority commands** to cover first: `step-done`, `register`, `doc-update`, `approve`, `next-id`, and the evidence-ingestion hooks (the `iw` calls in the approve / step-done flow described in `orch/evidences.py`).

### Part B — Spec-conformance test

A test module that parses the **§4 "Command Summary"** command tree in `docs/IW_AI_Core_CLI_Spec.md` (a fenced ASCII tree — *not* a Markdown table; the per-command §3.x tables list flags/options, not the canonical command set), introspects the actual Click command tree (the root group in `orch/cli/main.py` and its sub-groups, recursively, via `.commands`), and asserts:

1. Every command documented in the spec exists in the CLI.
2. Every command in the CLI is documented in the spec.
3. Every spec command either has at least one contract test (detected by scanning the CLI test files) **or** is listed in the `KNOWN_UNTESTED_COMMANDS` allowlist.

Two module-level allowlists make the gate fire only on *new* problems:

- **`KNOWN_SPEC_DRIFT`** — keyed by command, each entry carrying a `TODO(file-incident)` placeholder or a one-line rationale plus a `"direction"` (`"spec_only"` / `"cli_only"`). Absorbs pre-existing existence drift (assertions 1 and 2). The CR may fix doc drift directly in `docs/IW_AI_Core_CLI_Spec.md` — docs are not production code and are within scope; prefer fixing the doc over allowlisting.
- **`KNOWN_UNTESTED_COMMANDS`** — keyed by command, each entry carrying a one-line rationale. Pre-seeded at merge time with every command that does **not** yet have a contract test (i.e. everything outside the 6 priority commands). Absorbs the pre-existing coverage gap (assertion 3) so the gate fires only when a *newly added* command ships with neither a contract test nor an allowlist entry. This keeps assertion 3 compatible with the "priority commands first, rest is follow-up" scope while still flagging future regressions.

### Wiring

The tests land under `tests/integration/` so the existing `integration-tests` daemon QV gate (`make test-integration`) and the `test-quality.yml` integration job run them automatically — **no new canonical QV gate**. A `test-cli-contract` convenience Makefile target is added. Documentation and skill files are updated at S01 time.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `tests/integration/cli/` | Partial coverage; no systematic per-command contract assertions | + per-command contract test classes for the 6 priority commands + evidence-ingestion hooks |
| `tests/integration/` | No spec-conformance test | + spec-conformance bidirectional drift check with `KNOWN_SPEC_DRIFT` (existence) and `KNOWN_UNTESTED_COMMANDS` (coverage) allowlists |
| `Makefile` | No CLI contract convenience target | + `test-cli-contract` target |
| `docs/IW_AI_Core_CLI_Spec.md` | May have doc drift vs the actual CLI | Drift fixed in the doc (docs are in scope); pre-existing drift absorbed by `KNOWN_SPEC_DRIFT` |
| `docs/IW_AI_Core_Testing_Strategy.md` | Does not describe the CLI contract layer | + CLI contract layer (§3 layers / §5 gate table / §9 gap rows) |
| `skills/iw-ai-core-testing/SKILL.md` | Does not mention the CLI contract layer | + CLI contract layer sub-section |
| `ai-dev/work/TESTS_ENHANCEMENT.md` | Item 3.3 open | Item 3.3 marked DONE + §11 changelog |

### Breaking Changes

- None. This CR adds tests and a convenience Makefile target. No production code, no API, no schema, no behaviour change.

### Data Migration

- None. No schema change, no migration file, nothing to reverse.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | Per-command contract tests (Part A, priority commands); spec-conformance test (Part B) with `KNOWN_SPEC_DRIFT` allowlist; `test-cli-contract` Makefile target; strategy-doc + skill + plan updates | — |
| S02 | code-review-impl | Per-agent review of S01 | — |
| S03 | code-review-final-impl | Global cross-agent review of all work | — |
| S04 | qv-gate | `lint` → `make lint` | — |
| S05 | qv-gate | `assertions` → `make test-assertions` | — |
| S06 | qv-gate | `format` → `make format-check` | — |
| S07 | qv-gate | `typecheck` → `make type-check` | — |
| S08 | qv-gate | `unit-tests` → `make test-unit` | — |
| S09 | qv-gate | `integration-tests` → `make test-integration` (this runs the new contract tests) | — |
| S10 | qv-gate | `diff-coverage` → `make diff-coverage` | — |
| S11 | qv-gate | `security-secrets` → `make security-secrets` | — |
| S12 | self-assess-impl | Self-assessment via the `iw-item-analyze` skill | — |

Agent slugs: `backend-impl`, `code-review-impl`, `code-review-final-impl`, `qv-gate`, `self-assess-impl`.

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None — no migration file is added.

### API Changes

- **New endpoints**: None
- **Modified endpoints**: None
- **Removed endpoints**: None

### Frontend Changes

- **New components**: None
- **Modified components**: None
- **Removed components**: None

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `CR-00073_CR_Design.md` | Design | This document |
| `CR-00073_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for the orchestrator |
| `prompts/CR-00073_S01_Backend_prompt.md` | Prompt | S01 implementation instructions |
| `prompts/CR-00073_S02_CodeReview_prompt.md` | Prompt | S02 per-agent review instructions |
| `prompts/CR-00073_S03_CodeReview_Final_prompt.md` | Prompt | S03 final cross-agent review instructions |
| `prompts/CR-00073_S12_SelfAssess_prompt.md` | Prompt | S12 self-assessment instructions |

Reports are created during execution in `ai-dev/work/CR-00073/reports/`.

### Files created/modified by the implementation

| File | Action | Purpose |
|------|--------|---------|
| `tests/integration/cli/test_step_done_contract.py` | Create | Per-command contract tests for `step-done` |
| `tests/integration/cli/test_register_contract.py` | Create | Per-command contract tests for `register` |
| `tests/integration/cli/test_doc_update_contract.py` | Create | Per-command contract tests for `doc-update` |
| `tests/integration/cli/test_approve_contract.py` | Create | Per-command contract tests for `approve` |
| `tests/integration/cli/test_next_id_contract.py` | Create | Per-command contract tests for `next-id` (incl. concurrency) |
| `tests/integration/cli/test_evidence_hooks_contract.py` | Create | Per-command contract tests for evidence-ingestion hooks |
| `tests/integration/test_cli_spec_conformance.py` | Create | Spec-conformance bidirectional drift check with `KNOWN_SPEC_DRIFT` |
| `tests/integration/conftest.py` | Modify (if needed) | Shared CLI test fixtures |
| `tests/fixtures/**` | Create (if needed) | Shared CLI seed helpers |
| `Makefile` | Modify | `test-cli-contract` convenience target, `.PHONY` |
| `docs/IW_AI_Core_CLI_Spec.md` | Modify (if needed) | Fix doc drift found by the conformance test |
| `docs/IW_AI_Core_Testing_Strategy.md` | Modify | Document the CLI contract layer (§3 / §5 / §9) |
| `skills/iw-ai-core-testing/SKILL.md` | Modify | Note the CLI contract layer + how to extend it |
| `.claude/skills/iw-ai-core-testing/SKILL.md` | Modify | Synced copy (`iw sync-skills --force iw-ai-core-testing`) |
| `ai-dev/work/TESTS_ENHANCEMENT.md` | Modify | Mark item 3.3 DONE; §11 changelog |

## Acceptance Criteria

### AC1: Per-command contract coverage of the priority commands

```
Given the per-command contract test classes exist under tests/integration/cli/
When the integration-tests gate (make test-integration) runs
Then for each of step-done, register, doc-update, approve, next-id, and the
     evidence-ingestion hooks:
     - at least one test asserts exit code 0 on a documented success path
     - at least one test asserts a non-zero exit code and a clear stderr message
       on a documented error path
     - at least one test asserts stdout shape matches the documented format
     - at least one test asserts the DB row(s) created or mutated match
       expectations via the testcontainer db_session
     - for next-id: at least one test asserts atomic allocation (no duplicate IDs
       under concurrent calls)
     - for register: at least one test asserts idempotency-key behaviour
```

### AC2: Spec-conformance bidirectional drift check

```
Given tests/integration/test_cli_spec_conformance.py exists
When the integration-tests gate runs
Then the test parses the §4 "Command Summary" command tree in
     docs/IW_AI_Core_CLI_Spec.md (a fenced ASCII tree) and introspects the
     actual Click command tree recursively via .commands
And asserts that every command documented in the spec exists in the CLI
And asserts that every command in the CLI is documented in the spec
And asserts that every spec command has at least one contract test, OR is
     listed in the KNOWN_UNTESTED_COMMANDS allowlist
```

### AC3: Allowlists absorb pre-existing drift and the pre-existing coverage gap

```
Given pre-existing existence drift between the CLI and its spec may exist at
     merge time, and only the 6 priority commands have contract tests
When the conformance test runs
Then KNOWN_SPEC_DRIFT (command-keyed; each entry carries a TODO(file-incident)
     placeholder or a one-line rationale plus a "direction" of "spec_only" or
     "cli_only") absorbs
     pre-existing existence drift, so assertions 1 and 2 fail only on NEW drift
And KNOWN_UNTESTED_COMMANDS (command-keyed; each entry carries a one-line
     rationale) is pre-seeded with every command lacking a contract test, so
     assertion 3 fails only when a NEWLY added command ships with neither a
     contract test nor an allowlist entry
And both allowlists are module-level constants in test_cli_spec_conformance.py,
     auditable by code review
```

### AC4: Tests run under the existing integration gate — no new QV gate

```
Given all new tests live under tests/integration/
When the integration-tests QV gate (make test-integration) or the
     test-quality.yml integration job runs
Then all new contract tests and the conformance test are collected and executed
And no new entry is added to the canonical QV-gate list in
     skills/iw-workflow/SKILL.md
```

### AC5: Every new test can fail — monkeypatch demonstration

```
Given CR-00073 is a test-infrastructure CR with no production code to RED-GREEN
When S01 reports completion
Then the step report contains tdd_red_evidence recording, for at least one
     per-command contract test, an in-test monkeypatch that broke the command's
     observable behaviour (e.g. patched its DB-write to a no-op), under which
     the contract test was shown to fail
And for the spec-conformance test, an in-test monkeypatch of the parsed spec set
     or the introspected CLI command set, under which the conformance test was
     shown to report the injected drift
And no orch/ or other production file was edited at any point — the
     demonstration lives entirely in test code and the monkeypatch auto-reverts
     at test teardown (git diff against origin/main touches no production path)
```

### AC6: Docs, skill, and plan updated and synced

```
Given the CLI contract test layer now exists
When S01 completes
Then docs/IW_AI_Core_Testing_Strategy.md describes the CLI contract layer
     (§3 layers, §5 gate table, §9 gap rows)
And skills/iw-ai-core-testing/SKILL.md notes the layer and how to extend it
     (adding a new command: add a test class; updating the spec: re-run the
     conformance test)
And .claude/skills/iw-ai-core-testing/SKILL.md is byte-identical to its master
     (iw sync-skills --force iw-ai-core-testing was run)
And ai-dev/work/TESTS_ENHANCEMENT.md marks item 3.3 DONE with a §11
     changelog entry
```

## Rollback Plan

- **Database**: Not applicable — no migration, no schema change.
- **Code**: Revert the squash-merge commit. The CR adds only tests, a convenience Makefile target, and doc updates — reverting removes them cleanly with no residue.
- **Data**: No data loss on rollback — nothing in the CR writes to any persistent store.

## Dependencies

- **Depends on**: None functionally. The `pgtestdbpy` per-test DB isolation (CR-00055) and the `integration-tests` gate are already on `main` and are relied upon, but no in-flight item is required.
- **Shared-file serialization**: CR-00073 modifies `docs/IW_AI_Core_Testing_Strategy.md`, `skills/iw-ai-core-testing/**`, `.claude/skills/iw-ai-core-testing/**`, and `ai-dev/work/TESTS_ENHANCEMENT.md`, which are ALSO modified by CR-00072, CR-00074, CR-00075, and CR-00076 (the other Phase 3 testing CRs). These five CRs therefore **must NOT run in the same parallel batch** — the batch executor must serialize them (one at a time) to avoid merge conflicts on those shared files.
- **Blocks**: None.

## Impacted Paths

- `tests/integration/cli/**`
- `tests/integration/test_cli_core.py`
- `tests/integration/test_cli_items.py`
- `tests/integration/test_cli_batches.py`
- `tests/integration/test_cli_steps.py`
- `tests/integration/conftest.py`
- `tests/fixtures/**`
- `Makefile`
- `docs/IW_AI_Core_CLI_Spec.md`
- `docs/IW_AI_Core_Testing_Strategy.md`
- `skills/iw-ai-core-testing/**`
- `.claude/skills/iw-ai-core-testing/**`
- `ai-dev/work/TESTS_ENHANCEMENT.md`

## TDD Approach

This is a test-infrastructure CR — the new tests *are* the deliverable, so classic RED-GREEN does not apply to production code. The "every test must be able to fail" requirement is satisfied **entirely within test code** — no production file under `orch/` is ever edited, not even temporarily:

- **Per-command contract tests — prove they can fail.** Before reporting completion, S01 must demonstrate the contract tests catch a regression using an **in-test `monkeypatch`**: inside a dedicated demonstration (a temporary throwaway test, or an interactive run), monkeypatch the command's observable behaviour — e.g. patch its DB-write helper to a no-op so the expected row is never written, or patch its callback to return a non-zero exit — then run the affected contract test and confirm it fails. The `monkeypatch` fixture auto-reverts at test teardown; nothing in `orch/` is touched. The captured failing output is recorded as `tdd_red_evidence`.
- **Spec-conformance test — prove it can fail.** Similarly, monkeypatch the conformance module's spec-parse result (drop one command name) or its Click-tree introspection result (drop one command), run the conformance test, and confirm it reports the injected drift. Again `monkeypatch` auto-reverts — no edit to the spec doc or the CLI.
- **Unit tests**: None — there is no pure logic to unit-test; the deliverable is integration-level CLI contract tests.
- **Integration tests**: all new tests under `tests/integration/cli/` and `tests/integration/test_cli_spec_conformance.py`. All use the testcontainer `db_session` fixture; none touches the live DB.
- **Updated tests**: None — no existing test changes behaviour. If the conformance test surfaces genuine undocumented CLI commands, the fix is updating `docs/IW_AI_Core_CLI_Spec.md` (in scope) or adding to `KNOWN_SPEC_DRIFT` with a `TODO(file-incident)` placeholder (if the command warrants its own item).

## Notes

- **Risk — conformance test finds real spec drift on `main`.** Expected and acceptable — and confirmed: the live CLI currently exposes well over a dozen commands the §4 "Command Summary" does not document. S01 should **fix the spec doc** to add the missing rows (docs are in scope) rather than mass-allowlisting; `KNOWN_SPEC_DRIFT` is only for drift that genuinely cannot be resolved in-CR (e.g. a CLI command that ought to be removed — a production change requiring its own item). Each `KNOWN_SPEC_DRIFT` entry carries a `TODO(file-incident)` placeholder and a one-line rationale; each placeholder is surfaced as operator follow-up in the S01 report so the operator files the Incident on `main` post-merge. New drift detected after this CR merges will fail the conformance gate — the desired behaviour.
- **`KNOWN_UNTESTED_COMMANDS` will be sizeable on first merge.** This CR adds contract tests for only the 6 priority commands, so every other documented command goes into `KNOWN_UNTESTED_COMMANDS` with a one-line rationale (e.g. "non-priority — contract coverage deferred, TESTS_ENHANCEMENT follow-up"). That is expected and correct: the allowlist makes assertion 3 a *ratchet* — it never fails for today's known gap, but fails the moment a new command is added without a test. Shrinking the allowlist is the explicit follow-up.
- **`CliRunner` vs subprocess.** Most CLI commands can be tested with Click's `CliRunner` (which avoids process overhead and allows direct injection of the testcontainer `db_session`). Commands that spawn subprocesses or rely on process-level env vars may require subprocess invocation — match the pattern already established in `tests/integration/cli/` and `tests/integration/test_cli_*.py`.
- **Concurrency test for `next-id`.** The atomicity assertion for `next-id` should use a `ThreadPoolExecutor` to issue concurrent calls and verify no duplicate IDs are allocated — follow the pattern in `tests/unit/properties/test_iw_next_id_atomicity_properties.py`.
- **Doc drift edits to `docs/IW_AI_Core_CLI_Spec.md` are allowed.** Docs are not production code. S01 may fix doc drift found by the conformance test directly. However, S01 must NOT edit `orch/cli/` or any other production module — `scope.allowed_paths` excludes it and the merge-time scope gate enforces this.
- **If a contract test surfaces a genuine CLI bug**, the failing test is marked `pytest.mark.xfail` (or recorded in a `KNOWN_CLI_BUG` allowlist in the affected contract test file) with a `TODO(file-incident)` placeholder and a one-line rationale — never fixed in-CR. Each placeholder is surfaced as operator follow-up in the S01 report (command + rationale + a short failing snippet) so the operator files the Incident on `main` post-merge. Do NOT run `/iw-new-incident` and do NOT create any `ai-dev/active/I-NNNNN/**` from the worktree (it would land outside `scope.allowed_paths`). A CLI bug is neither spec drift nor a coverage gap, so it does **not** belong in `KNOWN_SPEC_DRIFT` or `KNOWN_UNTESTED_COMMANDS`. The scope gate enforces that no production fix lands here.
- **Out of scope**: fixing any CLI bug the contract tests surface (operator files the Incident on `main` post-merge); adding contract tests for non-priority commands in this CR (a follow-up can extend coverage); porting the layer to sibling repos.
