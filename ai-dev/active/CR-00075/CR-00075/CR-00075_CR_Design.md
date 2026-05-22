# CR-00075: Security Test Module

**Type**: Change Request
**Priority**: Medium
**Reason**: Phase 3 item 3.5 of the Testing Enhancement Plan — security-relevant behaviours are tested only in scattered files; whole classes of risk (live-DB guard regression, authz negative paths, doc-render SSRF/path-traversal, agent-context env-var bypass) have no organised, asserted regression net.
**Created**: 2026-05-21
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt — this CR's new tests use the existing testcontainer `db_session` fixture and nothing else.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. **This item leaves migrations unchanged** — it adds no schema change and no migration file.

## Description

Add an organised security test package `tests/integration/security/` with four asserted test modules covering distinct security risk classes: the live-DB write-guard regression net (the I-00041 class), authorization negative paths, doc-render SSRF and path-traversal, and agent-context env-var handling. These are asserted regression tests, explicitly distinct from the existing scanner tools (`gitleaks`, Semgrep, bandit) already wired in earlier CRs.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Relevant: the live-DB guard lives in `orch/db/session.py` (`safe_create_engine` / `is_live_db_url`); the agent-context guard is referenced in `tests/integration/test_agent_migrate_guard.py`; chat security tests live in `tests/dashboard/test_chat_security.py`; doc generation / rendering is around `orch/doc_service.py`, `orch/doc_sections.py`, and `doc-system/`; the live-DB guard outage (incident I-00041) shipped because nothing pinned the guard — this CR closes that gap. This CR is part of the phased plan in `ai-dev/work/TESTS_ENHANCEMENT.md` (item 3.5).

## Current Behavior

- Security scan *tooling* (`gitleaks`, Semgrep, bandit) is wired via `make security-secrets` and `make security-sast` but produces no asserted test results — scanner output is advisory, not a regression net.
- Security-relevant behaviours are tested only in scattered files: `tests/dashboard/test_chat_security.py`, `tests/integration/test_live_db_guard_log_level.py`, the alembic-guard tests, `tests/integration/test_agent_migrate_guard.py`. There is no single owned location.
- The live-DB write-guard (I-00041 class) has no dedicated regression module — the outage shipped because nothing pinned the guard's firing behaviour in the contexts that matter (test collection, agent worktrees).
- Authorization negative paths — cross-scope access, unauthenticated access to protected endpoints — are covered only where individual test authors happened to write them; there is no systematic negative-path sweep.
- Doc-render SSRF and path-traversal inputs have no asserted tests. The doc-render / doc-system pipeline (`orch/doc_service.py`, `orch/doc_sections.py`, `doc-system/`) is untested for malicious inputs.
- `IW_CORE_AGENT_CONTEXT=true` env-var bypass paths are referenced but the existing agent-migrate-guard test file is narrow in scope.
- The `pytest` default selection excludes `browser` and `quarantine` markers; there is no `security` marker.

## Desired Behavior

- A new package `tests/integration/security/` (with `__init__.py`) organises all security regression tests under one owned location.
- **`test_live_db_write_guard.py`** — a regression net for the I-00041 class. Asserts that `safe_create_engine` / `is_live_db_url` in `orch/db/session.py` refuses connections whose URL resolves to the live orchestration DB (port 5433 or the configured live host). Covers the contexts where the guard must fire: test collection, agent worktrees. Nothing in this module pins the guard to the production host — it uses environment variable injection to simulate a live-DB URL without actually connecting.
- **`test_authz_negative_paths.py`** — authorization negative-path tests. Assert that unauthorized or cross-scope access to protected routes returns a 4xx (never data, never 5xx). Extends the `test_chat_security` family to cover chat endpoints and any other authz-bearing route exposed by the dashboard.
- **`test_doc_render_ssrf_path_traversal.py`** — feed the doc-render / doc-system path malicious inputs: `file://` URLs, `../../etc/passwd`-style path traversal, internal-URL SSRF attempts. Assert the doc system refuses to read arbitrary local files or fetch internal URLs.
- **`test_agent_context_env_handling.py`** — assert that `IW_CORE_AGENT_CONTEXT=true` correctly blocks operator-only commands (migration apply, etc.) and that the env-var handling cannot be trivially bypassed. References and extends `tests/integration/test_agent_migrate_guard.py`.
- **CRITICAL — genuine vulnerability handling**: if a security test surfaces a genuine vulnerability (a real SSRF, a real path-traversal, a guard that does not fire), the implementer writes the test as the **failing reproduction**, marks it `@pytest.mark.xfail(strict=False, reason="...")` with a `# NOTE` tracking comment containing a **`TODO(file-incident)` placeholder** and a one-line rationale, and lists every such finding prominently under an **"Operator follow-up — SECURITY"** heading in the S01 report (test name + rationale + a short repro snippet) so the operator files a high-priority security Incident on `main` post-merge. The implementer does **not** run `/iw-new-incident` from inside the worktree and does **not** create an `ai-dev/active/I-NNNNN/` package (it would land outside `scope.allowed_paths` and fail the merge-time scope gate). The CR stays strictly test-only — the fix is the operator's separate incident. The implementer MUST NOT edit production code to fix a vulnerability within this CR (the merge-time scope gate enforces this).
- Tests land under `tests/integration/` so the existing `integration-tests` daemon QV gate (`make test-integration`) runs them automatically — **no new canonical QV gate**.
- A `test-security-module` convenience Makefile target is added. This target runs only the new asserted security tests and is explicitly distinct from the existing scanner targets (`make security-secrets` / `make security-sast`) — the design distinction must be clear in the Makefile comment and docs to avoid confusion.
- At S01 time, `docs/IW_AI_Core_Testing_Strategy.md` (§3/§5/§9), `skills/iw-ai-core-testing/SKILL.md` (+ synced `.claude/skills/iw-ai-core-testing/SKILL.md` via `iw sync-skills --force iw-ai-core-testing`), and `ai-dev/work/TESTS_ENHANCEMENT.md` (mark item 3.5 DONE + §11 changelog entry) are updated.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `tests/integration/` | No security sub-package; scattered security tests | + `security/` package with 4 modules |
| `tests/integration/conftest.py` | Existing shared fixtures | Possibly extended with security-specific helpers |
| `Makefile` | `make security-secrets` + `make security-sast` (scanner targets) | + `test-security-module` (asserted tests, distinct from scanners) |
| `docs/IW_AI_Core_Testing_Strategy.md` | No security test layer documented | + security test layer in §3/§5/§9 |
| `skills/iw-ai-core-testing/SKILL.md` | No security module guidance | + security module layer description |

### Breaking Changes

- None. This CR adds tests and a Makefile target. No production code, no API, no schema, no behaviour change.

### Data Migration

- None. No schema change, no migration file, nothing to reverse.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | Security test package: 4 modules + `__init__.py`; `test-security-module` Makefile target; strategy-doc + skill + plan updates | — |
| S02 | code-review-impl | Per-agent review of S01 | — |
| S03 | code-review-final-impl | Global cross-agent review of all work | — |
| S04 | qv-gate | `lint` → `make lint` | — |
| S05 | qv-gate | `assertions` → `make test-assertions` | — |
| S06 | qv-gate | `format` → `make format-check` | — |
| S07 | qv-gate | `typecheck` → `make type-check` | — |
| S08 | qv-gate | `unit-tests` → `make test-unit` | — |
| S09 | qv-gate | `integration-tests` → `make test-integration` (this runs the new security modules) | — |
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
| `CR-00075_CR_Design.md` | Design | This document |
| `CR-00075_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for the orchestrator |
| `prompts/CR-00075_S01_Backend_prompt.md` | Prompt | S01 implementation instructions |
| `prompts/CR-00075_S02_CodeReview_prompt.md` | Prompt | S02 per-agent review instructions |
| `prompts/CR-00075_S03_CodeReview_Final_prompt.md` | Prompt | S03 final cross-agent review instructions |
| `prompts/CR-00075_S12_SelfAssess_prompt.md` | Prompt | S12 self-assessment instructions |

Reports are created during execution in `ai-dev/work/CR-00075/reports/`.

### Files created/modified by the implementation

| File | Action | Purpose |
|------|--------|---------|
| `tests/integration/security/__init__.py` | Create | Package marker |
| `tests/integration/security/test_live_db_write_guard.py` | Create | Regression net for the I-00041 live-DB guard class |
| `tests/integration/security/test_authz_negative_paths.py` | Create | Authorization negative-path tests |
| `tests/integration/security/test_doc_render_ssrf_path_traversal.py` | Create | Doc-render SSRF and path-traversal tests |
| `tests/integration/security/test_agent_context_env_handling.py` | Create | Agent-context env-var handling tests |
| `tests/integration/conftest.py` | Modify (if needed) | Shared security-test helpers |
| `tests/fixtures/**` | Create (if needed) | Shared seed or mock helpers |
| `Makefile` | Modify | `test-security-module` target + `.PHONY` |
| `docs/IW_AI_Core_Testing_Strategy.md` | Modify | Document the security test layer (§3 / §5 / §9) |
| `skills/iw-ai-core-testing/SKILL.md` | Modify | Note the security test module + how to extend it |
| `.claude/skills/iw-ai-core-testing/SKILL.md` | Modify | Synced copy (`iw sync-skills --force iw-ai-core-testing`) |
| `ai-dev/work/TESTS_ENHANCEMENT.md` | Modify | Mark item 3.5 DONE; §11 changelog |

## Acceptance Criteria

### AC1: Live-DB write-guard regression net asserts the guard fires in required contexts

```
Given the live-DB guard (safe_create_engine / is_live_db_url in orch/db/session.py)
When tests/integration/security/test_live_db_write_guard.py runs
Then the guard is asserted to refuse connections whose URL resolves to the configured
     live orchestration DB host:port (5433 / IW_CORE_DB_HOST)
And the test simulates a live-DB URL via environment variable injection — never by
     actually connecting to port 5433 — so the live-DB guard rule is not violated
And at least one test demonstrates the guard fires at test-collection time context
     and at least one demonstrates it fires in an agent-worktree context
And every assertion is behavioural: the guard raises LiveDbConnectionRefusedError
     (or equivalent) and not merely returns None or logs a warning
```

### AC2: Authorization negative-path tests assert 4xx for unauthorized access

```
Given the dashboard app assembled by create_app() backed by a seeded testcontainer DB
When tests/integration/security/test_authz_negative_paths.py runs
Then every protected route or action tested returns a 4xx response for an
     unauthorized or cross-scope request — never data, never a 5xx
And the test client sends requests without valid credentials or with wrong-scope
     credentials (not merely unauthenticated arbitrary requests)
And the chat endpoints and any other explicitly authz-bearing routes are covered
And assertions are on the response status code and the absence of data — not merely
     that response.status_code is not None
```

### AC3: Doc-render SSRF and path-traversal tests assert the doc system rejects malicious inputs

```
Given the doc-render / doc-system pipeline (orch/doc_service.py,
     orch/doc_sections.py, doc-system/ editorial config)
When tests/integration/security/test_doc_render_ssrf_path_traversal.py runs
Then feeding file:// URLs to the render path raises an error or returns a safe
     sentinel — never the file contents
And feeding ../../etc/passwd-style path traversal inputs raises an error or
     returns a safe sentinel — never the traversed file contents
And feeding internal-URL SSRF attempt inputs (e.g. http://localhost:5433/...)
     raises an error or returns a safe sentinel — never a successful fetch
And if a genuine vulnerability is found, the test is written as the failing
     reproduction, marked xfail(strict=False) with a TODO(file-incident) placeholder
     and a one-line rationale, and listed under "Operator follow-up — SECURITY"
     in the S01 report so the operator files the Incident on main post-merge
```

### AC4: Agent-context env-var handling tests assert operator-only commands are blocked

```
Given IW_CORE_AGENT_CONTEXT=true is set in the test environment
When tests/integration/security/test_agent_context_env_handling.py runs
Then operator-only commands (e.g. migration apply) are asserted to be blocked
     and not silently allowed
And the test asserts the block fires for at least the cases covered by
     tests/integration/test_agent_migrate_guard.py plus any additional bypass
     paths discovered during implementation
And a trivial bypass attempt (e.g. unset-then-reset the env var, provide a
     truthy-but-invalid value) is asserted to either still be blocked or to
     raise a clear error
```

### AC5: Genuine vulnerability handling — xfail + TODO(file-incident) placeholder + operator follow-up, no production fix in-CR

```
Given S01 discovers a genuine security vulnerability while implementing any
     of the four test modules (a real SSRF, a real path-traversal, a guard that
     does not fire)
When reporting completion
Then the test is written as the failing reproduction (it fails on current main)
And it is marked @pytest.mark.xfail(strict=False, reason="<one-liner>") with a
     # NOTE tracking comment containing a TODO(file-incident) placeholder and a
     one-line rationale
And it is listed prominently in the S01 report under an "Operator follow-up —
     SECURITY" heading (test name + rationale + short repro snippet) so the
     operator files a high-priority security Incident on main post-merge
And S01 does NOT run /iw-new-incident and does NOT create an ai-dev/active/I-NNNNN/
     package (that would land outside scope.allowed_paths and fail the scope gate)
And no file outside scope.allowed_paths is modified — in particular, no production
     code in orch/ or dashboard/ is edited to fix the vulnerability
And the CR scope gate (scope.allowed_paths) enforces this at merge time
```

### AC6: Every security test can fail — TDD demonstration + docs/skill/plan updated and synced

```
Given S01 completes implementation of all four test modules
When reporting completion
Then for each module, a deliberate-break-then-revert demonstration is recorded
     as tdd_red_evidence — confined entirely to the test file: temporarily invert
     or weaken one assertion inside the module (e.g. assert the guard allows the
     connection, or assert the SSRF input is accepted), confirm the case fails RED,
     then revert the test-file edit; production code (orch/, dashboard/, executor/,
     scripts/) is never touched, and git diff origin/main -- orch/ dashboard/
     executor/ scripts/ is empty before reporting completion
And docs/IW_AI_Core_Testing_Strategy.md describes the security test layer
     (§3 layers, §5 gate table, §9 gap rows)
And skills/iw-ai-core-testing/SKILL.md notes the security module and how to extend it
And .claude/skills/iw-ai-core-testing/SKILL.md is byte-identical to its master
     (iw sync-skills --force iw-ai-core-testing was run)
And ai-dev/work/TESTS_ENHANCEMENT.md marks item 3.5 DONE with a §11 changelog entry
And the test-security-module Makefile target is documented with a comment clearly
     distinguishing it from make security-secrets / make security-sast
```

## Rollback Plan

- **Database**: Not applicable — no migration, no schema change.
- **Code**: Revert the squash-merge commit. The CR adds only tests, one Makefile target, and doc updates — reverting removes them cleanly with no residue.
- **Data**: No data loss on rollback — nothing in the CR writes to any persistent store.

## Dependencies

- **Depends on**: None functionally. The `pgtestdbpy` per-test DB isolation (CR-00055) and the `integration-tests` gate flip to `make test-integration` are already on `main` and are relied upon, but no in-flight item is required.
- **Shared-file serialization**: CR-00075 modifies `docs/IW_AI_Core_Testing_Strategy.md`, `skills/iw-ai-core-testing/**`, `.claude/skills/iw-ai-core-testing/**`, `ai-dev/work/TESTS_ENHANCEMENT.md`, and `tests/integration/conftest.py`, which are ALSO modified by CR-00072, CR-00073, CR-00074, and CR-00076 (the other Phase 3 testing CRs). These five CRs therefore **must NOT run in the same parallel batch** — the batch executor must serialize them (one at a time) to avoid merge conflicts on those shared files.
- **Blocks**: None.

## Impacted Paths

- `tests/integration/security/**`
- `tests/integration/conftest.py`
- `tests/fixtures/**`
- `Makefile`
- `docs/IW_AI_Core_Testing_Strategy.md`
- `skills/iw-ai-core-testing/**`
- `.claude/skills/iw-ai-core-testing/**`
- `ai-dev/work/TESTS_ENHANCEMENT.md`

## TDD Approach

This is a test-infrastructure CR — the new tests *are* the deliverable, so classic RED-GREEN does not apply to production code. The "every test must be able to fail" requirement is satisfied differently:

- **Live-DB write-guard — prove it can fail.** Before reporting completion, S01 must demonstrate the guard regression test catches a regression — **entirely within the test file**, no production code touched: temporarily invert one assertion in `test_live_db_write_guard.py` (e.g. assert the guard *allows* the live-DB connection rather than refusing it), run `make test-security-module`, confirm the case fails RED, then revert the test-file edit. The demonstration must NEVER touch `orch/db/session.py` or any other production file. The captured failing output is recorded as `tdd_red_evidence`.
- **Doc-render SSRF/path-traversal — prove it can fail.** Similarly, and entirely within `test_doc_render_ssrf_path_traversal.py`: temporarily weaken one assertion (e.g. assert the SSRF input is *accepted* rather than refused), run the module, confirm it fails RED, then revert the test-file edit. No production code touched.
- **Authz negative paths and agent-context env-var — prove they can fail.** For each module, temporarily invert or weaken one assertion inside the respective test file (e.g. assert a 2xx is returned rather than a 4xx), confirm the case fails RED, then revert the test-file edit. No production guard or handler is modified.
- **Unit tests**: none — there is no pure logic to unit-test; the deliverable is integration-level security regression tests.
- **Integration tests**: all four modules under `tests/integration/security/`. All use the testcontainer `db_session` fixture; none touches the live DB.
- **Updated tests**: none — no existing test changes behaviour. If a genuine vulnerability is found, it is xfailed (AC5), not fixed.

## Notes

- **Risk — a module surfaces a genuine vulnerability.** Expected and acceptable. AC5's xfail + `TODO(file-incident)` placeholder workflow absorbs them so the CR can merge without expanding into a production fix; each genuine vulnerability is surfaced as operator follow-up under an **"Operator follow-up — SECURITY"** heading in the S01 report, and the operator files a high-priority security Incident on `main` post-merge so it is tracked and prioritized. The implementer must NOT run `/iw-new-incident` and must NOT create an `ai-dev/active/I-NNNNN/` package from the worktree (it would land outside `scope.allowed_paths` and fail the scope gate). The implementer MUST NOT edit production code — `scope.allowed_paths` excludes it and the merge-time scope gate enforces this.
- **Naming clarity — asserted tests vs scanners.** The Makefile target `test-security-module` runs asserted pytest tests. The existing `make security-secrets` (gitleaks) and `make security-sast` (Semgrep/bandit) run scanners that produce advisory output. These are distinct mechanisms. The Makefile target comment and the docs update must make this distinction explicit so operators do not confuse them.
- **Live-DB guard test must not touch port 5433.** The test validates `is_live_db_url()` and `safe_create_engine()` using environment variable injection (monkeypatching `IW_CORE_DB_HOST` and `IW_CORE_DB_PORT` to match what the live DB would look like), never by attempting an actual connection to port 5433. The live-DB guard is itself the safeguard — the test must not bypass it.
- **Auth test client setup.** For `test_authz_negative_paths.py`, the `TestClient` must be set up without valid credentials or with wrong-scope credentials — not merely an unauthenticated request if the route has no auth. Read the existing `tests/dashboard/test_chat_security.py` for the current authz pattern before implementing.
- **`pytest-randomly` is on.** All new tests must be order-independent. Seeding happens per-test/per-fixture; no reliance on another test's state.
- **Out of scope**: fixing any vulnerability the tests find; extending the scanner targets; porting the security module to sibling repos; adding a new canonical QV gate (the existing `integration-tests` gate covers it).
