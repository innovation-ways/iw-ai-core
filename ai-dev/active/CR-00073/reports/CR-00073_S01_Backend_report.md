# CR-00073 — S01 Backend Report

**Work Item**: CR-00073 — iw CLI Contract Test Layer
**Step**: S01 (backend-impl)
**Completion**: complete
**Note**: The four automated agent runs (run1–run4) all failed without reporting —
run1 crashed early ("PID dead"), run2 and run4 hit the 2400 s timeout. This step
was finished **manually by the operator**, who diagnosed and fixed the latent
defects in the partially-written test suite (detailed under "Issues fixed" below).

## What was done

Implemented the `iw` CLI contract test layer (TESTS_ENHANCEMENT.md item 3.3):

### 1. Per-command contract tests — `tests/integration/cli/`
One file per priority command; each asserts exit code on every documented
success/error path, stdout shape (parsed JSON / pattern-matched), DB row effects
queried via the testcontainer `db_session`, and idempotence/atomicity where the
spec promises it.

| File | Tests | Notes |
|------|-------|-------|
| `test_step_done_contract.py` | 9 | success/error exits, JSON shape, DB transition, browser-verification post-evidence hook |
| `test_register_contract.py` | 11 | new item, idempotent re-register, `--steps-from`/`--design-doc`, error exits |
| `test_doc_update_contract.py` | 6 | research auto-complete, error paths; 1 strict `xfail` (see Operator follow-up) |
| `test_approve_contract.py` | 7 | draft→approved, JSON shape, pre-phase evidence hook, error exits |
| `test_next_id_contract.py` | 7 | per-type prefixes, JSON shape, gapless sequence, **concurrency** (`ThreadPoolExecutor`, no duplicate IDs) |
| `test_evidence_hooks_contract.py` | 4 | `approve`→pre and `step-done`→post `ingest_phase_from_disk` hooks |

44 contract tests total — **43 passed + 1 xfailed**.

### 2. Spec-conformance test — `tests/integration/test_cli_spec_conformance.py`
7 tests. Parses the §4 "Command Summary" ASCII tree of `docs/IW_AI_Core_CLI_Spec.md`,
introspects the live Click tree from `orch.cli.main`, asserts bidirectional
existence coverage + contract-test coverage. Two ratchet allowlists:
`KNOWN_SPEC_DRIFT` = **0 entries** (§4 brought fully in sync), `KNOWN_UNTESTED_COMMANDS`
= **57 entries** (every non-priority command). Spec §4 ↔ CLI: **62 = 62**, bidirectional.

### 3. New shared fixture — `tests/integration/cli/conftest.py`
`iw_subprocess` — runs `uv run iw` against the per-test clone with a correct env
(see "Issues fixed" #2). The pattern follows `test_step_commands_drift.py`.

### 4. Makefile / docs / skill
- `Makefile`: `test-cli-contract` target (+ `.PHONY`).
- `docs/IW_AI_Core_CLI_Spec.md` §4: ~30 missing commands added so conformance is green with empty `KNOWN_SPEC_DRIFT`.
- `docs/IW_AI_Core_Testing_Strategy.md`: §2 sub-layer, §5 gate row, §9 known-gap row flipped.
- `skills/iw-ai-core-testing/SKILL.md`: §11 added; `iw sync-skills --force` run — `.claude/skills/` copy byte-identical.
- `ai-dev/work/TESTS_ENHANCEMENT.md`: item 3.3 → DONE; §11 Changelog entry added.

## Issues fixed during manual completion

1. **Subprocess-test deadlock** — the 6 subprocess-based tests took the `test_project`
   fixture (which `INSERT`s `test-proj` inside the open, uncommitted `db_session`
   transaction) *and* re-seeded the same project id on a separate `db_engine`
   connection. The duplicate-PK `INSERT` blocked forever. Fixed by dropping the
   `test_project` dependency from those tests (they create their own `Project`).
   This was the cause of the run2/run4 timeouts.
2. **Subprocess live-DB-guard / orch-DB resolution** — `iw step-done`/`approve`
   resolve their DB via `get_orch_db_url()`, which prefers `IW_CORE_ORCH_DB_*`
   (the repo `.env` points those at the live orch DB). Subprocess tests reached
   the live DB, then the connection-layer guard refused them. Fixed with the
   `iw_subprocess` fixture, which pins both `IW_CORE_DB_*` and `IW_CORE_ORCH_DB_*`
   to the clone and sets `IW_CORE_DAEMON_CONTEXT=true` (guard opt-in) — the
   established `test_step_commands_drift.py` pattern.
3. **`test_next_id_increments_sequence_row` off-by-one** — asserted `next_number`
   == prior + 1 starting from 0, but `next_number` holds the *next* value to hand
   out (1 → 2 after the first allocation). The CLI is correct; rewrote the test to
   assert the real "+1 per call" invariant.
4. **`doc-update` error tests** — one was misnamed (`..._exit_1` asserting exit 3)
   and two were byte-identical duplicates. `doc-update` has no "unknown work item"
   path (it validates the *project* only). Replaced with three genuine, distinct
   error-path tests: `--content`/`--content-file` mutual exclusivity (exit 2),
   unknown `--project` (exit 1), and the missing-`--tier` case (strict `xfail`).
5. **Assertion-scanner tautology** — `test_step_done_bad_report_path` asserted
   `exit_code in (0, 1)`. Determined the real behavior (missing `--report` file is
   non-fatal: exit 0, path stored, content unset) and rewrote it as a definitive
   contract test.
6. Removed a stray `ai-dev/active/CR-00073/CR-00073/` nested directory left by an
   earlier agent run.

## Test results

`make test-cli-contract` (and a 4-file randomized sweep): **50 passed, 1 xfailed**
across the 6 contract files + conformance. Preflight gates: `make format` ✓,
`make lint` ✓, `make typecheck` ✓, `make test-assertions` ✓.

## TDD RED evidence

Demonstrated via a throwaway `monkeypatch` test file (run, output captured, file
deleted — `git diff origin/main` touches no production file):
- **Contract**: `monkeypatch.setattr(orch.cli.id_commands, "allocate_next_id", → "BOGUS-00000")`
  → `test_next_id_allocates_id_exit_0` failed: `AssertionError: Expected I- prefix, got: BOGUS-00000`.
- **Conformance**: `monkeypatch.setattr` `parse_spec_commands` to inject a `ghost-command`
  → `test_every_spec_command_exists_in_cli` failed: `AssertionError: ... documents commands the CLI does not register: ['ghost-command']`.
Both via `monkeypatch` (auto-reverts); no `orch/` file edited.

## Scope

`git diff origin/main -- orch/ dashboard/ executor/ scripts/` is **empty** — no
production code touched. (The CR-00077 deletions visible in a broad `git diff` are
pre-existing worktree base drift — I-00083 — not changes from this step.)

## Operator follow-up

1. **Genuine CLI rough edge — `doc-update`**: a new-doc upsert that omits
   `--tier`/`--editorial-category` crashes with a raw `TypeError` from
   `DocService.create_doc()` surfaced as exit 3 `Database error`, instead of a
   clean exit 2 usage error. Pinned by `test_doc_update_new_doc_without_tier_is_clean_usage_error`
   (`@pytest.mark.xfail(strict=True)`, `TODO(file-incident)`). **File an Incident**;
   the `orch/cli` fix is out of scope for this test-only CR.
2. **Manifest scope gap**: `scope.allowed_paths` lists `tests/integration/test_cli_core.py`
   etc. but not `tests/integration/test_cli_spec_conformance.py`, which the CR
   design explicitly requires. The merge scope gate may flag it — it is a required
   deliverable, not scope creep.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "CR-00073",
  "completion_status": "complete",
  "files_changed": [
    "tests/integration/cli/conftest.py",
    "tests/integration/cli/test_step_done_contract.py",
    "tests/integration/cli/test_register_contract.py",
    "tests/integration/cli/test_doc_update_contract.py",
    "tests/integration/cli/test_approve_contract.py",
    "tests/integration/cli/test_next_id_contract.py",
    "tests/integration/cli/test_evidence_hooks_contract.py",
    "tests/integration/test_cli_spec_conformance.py",
    "Makefile",
    "docs/IW_AI_Core_CLI_Spec.md",
    "docs/IW_AI_Core_Testing_Strategy.md",
    "skills/iw-ai-core-testing/SKILL.md",
    ".claude/skills/iw-ai-core-testing/SKILL.md",
    "ai-dev/work/TESTS_ENHANCEMENT.md"
  ],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "43 passed, 1 xfailed, 0 failed (contract tests); 7 passed (conformance test)",
  "tdd_red_evidence": "monkeypatch demonstration — contract test: next-id case failed with 'AssertionError: Expected I- prefix, got: BOGUS-00000' after monkeypatch stubbed allocate_next_id; conformance test: injected 'ghost-command' drift reported by test_every_spec_command_exists_in_cli after monkeypatch patched parse_spec_commands. Both via monkeypatch (auto-reverted); git diff origin/main touches no production file.",
  "blockers": [],
  "notes": "KNOWN_SPEC_DRIFT: 0 entries (docs/IW_AI_Core_CLI_Spec.md §4 brought fully in sync — ~30 commands added). KNOWN_UNTESTED_COMMANDS: 57 entries (every non-priority command; rationale 'non-priority — contract coverage deferred, TESTS_ENHANCEMENT 3.3 follow-up'). §4 spec ↔ live CLI: 62 = 62 bidirectional. Total contract tests: 44 across 6 priority command groups (step-done, register, doc-update, approve, next-id, evidence-ingestion hooks). Incidents to file (operator follow-up): 1 — doc-update missing-tier exit-3 TypeError (xfailed). Step finished manually after run1-run4 failed (run1 crash, run2/run4 2400s timeouts)."
}
```
