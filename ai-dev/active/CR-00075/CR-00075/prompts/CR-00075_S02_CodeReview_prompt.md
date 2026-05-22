# CR-00075_S02_CodeReview_prompt

**Work Item**: CR-00075 — Security Test Module
**Step Being Reviewed**: S01 (backend-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY command that changes Docker container/volume/network
state (`docker kill|stop|rm|restart`, `docker compose up|down|restart`,
`docker volume rm|prune`, `docker system prune`, …). Allowed: testcontainers via
pytest fixtures; read-only `docker ps|inspect|logs`; `./ai-core.sh` and `make`
targets. If your task seems to require a prohibited command, STOP and raise a
blocker. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

CR-00075 adds no migration. If you find a migration file in the changeset, that
is a **CRITICAL** scope violation. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — prefer `uv run iw item-status CR-00075 --json`.
- `ai-dev/work/CR-00075/CR-00075_CR_Design.md` — design document.
- `ai-dev/work/CR-00075/reports/CR-00075_S01_Backend_report.md` — S01 report.
- All files listed in the S01 report's `files_changed`.

## Output Files

- `ai-dev/work/CR-00075/reports/CR-00075_S02_CodeReview_report.md` — review report.

## Context

You are reviewing the S01 implementation of CR-00075 — a test-infrastructure CR
that adds an organised security regression test package. Read the design document
first (especially the Acceptance Criteria and TDD Approach sections), then the
S01 report, then every changed file.

## Read the Design Document FIRST

Read `## Acceptance Criteria` (AC1–AC6) and `## TDD Approach` in full. Every AC
is a mandatory check. Note the four test modules the design names by path
(`tests/integration/security/test_live_db_write_guard.py`,
`tests/integration/security/test_authz_negative_paths.py`,
`tests/integration/security/test_doc_render_ssrf_path_traversal.py`,
`tests/integration/security/test_agent_context_env_handling.py`) — all four MUST
appear in S01's `files_changed`; a missing one is **CRITICAL**.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Run `make lint` and `make format-check` on the changed files. Fix nothing — only
report. Any NEW violation (not on `main` before S01) is a **CRITICAL** finding
with `category: conventions`, the file/line, and the exact code+message. Also run
`make test-assertions` — a new assertion-scanner violation in any new test file is
**CRITICAL**. If a command is unavailable, STOP and raise a blocker.

## Review Checklist

### 1. Scope discipline (CRITICAL category)

- **No production code touched.** The only files changed must be within
  `scope.allowed_paths`: `tests/integration/security/**`,
  `tests/integration/conftest.py`, `tests/fixtures/**`, `Makefile`,
  `docs/IW_AI_Core_Testing_Strategy.md`, `skills/iw-ai-core-testing/**`,
  `.claude/skills/iw-ai-core-testing/**`, `ai-dev/work/TESTS_ENHANCEMENT.md`.
  Any edit to `orch/`, `dashboard/`, `executor/`, `scripts/` is a **CRITICAL**
  scope violation — including a "fix" for a genuine vulnerability (those must be
  xfailed + Incident, not fixed; see AC5).
- **No deliberate-break injection left behind.** S01's TDD demonstration
  temporarily inverts or weakens assertions inside the test files to prove tests
  can fail, then reverts — it never edits production code. Confirm via
  `git diff origin/main -- orch/ dashboard/ executor/ scripts/` that it is
  **empty** — any production-code edit, or a residual inverted assertion left in
  the committed test files, is **CRITICAL**.

### 2. AC1 — live-DB write-guard regression net

- The test module covers at least two contexts (test-collection and agent-worktree).
- **Never connects to port 5433.** All live-DB URL simulation is via `monkeypatch`
  env-var injection — if S01 used an actual connection to port 5433, that is a
  **CRITICAL** live-DB violation.
- Assertions are behavioural: the guard raises `LiveDbConnectionRefusedError` (or
  equivalent), not merely logs. An assertion that only checks a log message is
  **HIGH** (a log-only guard does not protect anything).
- `monkeypatch` is used for env-var injection so teardown is automatic; no
  manually-managed env-var mutation is left in module state.

### 3. AC2 — authz negative paths

- The `TestClient` is set up with `create_app()` + `get_db` override pointing at
  the testcontainer `db_session` (never the live DB).
- Requests are sent without credentials or with wrong-scope credentials — not
  merely unauthenticated requests to routes that have no auth (which would be
  trivially vacuous).
- Assertions check both status code (4xx) **and** that the response body does not
  contain data the caller should not see. An assertion of only `status_code == 403`
  with no body check is **MEDIUM (fixable)**.
- Chat endpoints from `tests/dashboard/test_chat_security.py` are covered or
  explicitly documented as out-of-scope with a rationale.

### 4. AC3 — doc-render SSRF and path-traversal

- All three input classes are tested: `file://` URLs, path-traversal strings,
  internal-URL SSRF attempts.
- If no attack surface was found, the S01 report says "No SSRF/path-traversal
  surface found" and there is at least one test documenting that assertion.
  If the surface exists and is not tested, that is **HIGH**.
- Assertions confirm the function raises or returns a safe sentinel — not merely
  that the mock was called. A test that only checks `mock.assert_called` without
  asserting the caller did not receive file contents is **MEDIUM (fixable)**.
- No real network requests are made — `monkeypatch` / `unittest.mock` is used to
  prevent outbound HTTP.

### 5. AC4 — agent-context env-var handling

- At minimum: migration apply (or any command guarded by the agent-context check)
  is asserted to be blocked with `IW_CORE_AGENT_CONTEXT=true`.
- At least one bypass attempt is covered (capital `T`, value `"1"`, or
  unset-then-reset).
- Assertions confirm an explicit refusal (raises, non-zero exit, or clear error
  message) — not merely a silent no-op. An assertion of only
  `result.returncode != 0` with no inspection of the error message is
  **MEDIUM (fixable)**.

### 6. AC5 — genuine vulnerability handling

- If S01's report lists any genuine vulnerability:
  - The test is written as the failing reproduction (it fails on current `main`).
  - It is marked `@pytest.mark.xfail(strict=False, reason="<one-liner>")`.
  - It carries a `# NOTE: genuine vulnerability — TODO(file-incident: SECURITY) <one-line rationale>` comment. The `xfail` reason and `# NOTE` comment must contain a `TODO(file-incident)` placeholder — **not** a real Incident ID (which would mean `/iw-new-incident` was run from the worktree, creating a package outside `scope.allowed_paths` → **CRITICAL**).
  - It is listed under **"Operator follow-up — SECURITY"** in the S01 report (test name + rationale + short repro snippet) — not merely under "SECURITY BLOCKERS". Verify the operator has everything needed to file the Incident on `main` post-merge.
  - S01 must NOT have run `/iw-new-incident` or created an `ai-dev/active/I-NNNNN/` package — an `ai-dev/active/I-NNNNN/**` path in the changeset is a **CRITICAL** scope violation.
  - **No production code was edited** — any edit to `orch/` or `dashboard/` is a
    **CRITICAL** scope violation.
- If S01's report claims no genuine vulnerabilities were found, spot-check at
  least one test from each module to confirm the assertion is behavioural (not
  vacuous) — a test that always passes because the attack surface does not exist
  should still be documented, not silently omitted.

### 7. AC6 — docs / skill / plan

- `docs/IW_AI_Core_Testing_Strategy.md` describes the security test layer (§3/§5/§9).
- `skills/iw-ai-core-testing/SKILL.md` notes the security module and how to extend it.
- `.claude/skills/iw-ai-core-testing/SKILL.md` is **byte-identical** to the master
  (`diff` them — a mismatch means `iw sync-skills --force` was not run → **HIGH**).
- `ai-dev/work/TESTS_ENHANCEMENT.md`: item 3.5 → DONE (CR-00075); a §11 changelog
  entry exists; counts in the changelog match the S01 report.
- The `test-security-module` Makefile target has a comment explicitly distinguishing
  it from `make security-secrets` / `make security-sast`. Missing comment → **MEDIUM (fixable)**.

### 8. Test quality and isolation

- All new tests use the testcontainer `db_session` — never the live DB.
- Tests are order-independent (`pytest-randomly` is on by default). Seeding
  happens per-test/per-fixture; no reliance on another test's state.
- `monkeypatch` is used for all env-var injection — no global state mutation.
- Assertions are behavioural and strong — re-read `skills/iw-ai-core-testing/SKILL.md`'s
  red-flag checklist and apply it.

## TDD RED Evidence

S01 is a test-infrastructure step. Confirm `tdd_red_evidence` records the
**deliberate-break demonstration** for all four test modules — a temporarily
inverted or weakened assertion inside each test file causing the case to fail
RED, then reverted. The demonstration must have been confined entirely to the
test files: no patching of production guards in `orch/`, `dashboard/`,
`executor/`, or `scripts/`. If `tdd_red_evidence` is missing or says `n/a`
with no demonstration, raise a **HIGH** finding: a security test that cannot
be shown to fail is a false sense of security. If the demonstration involved
editing production code (e.g. patching `is_live_db_url` directly), raise a
**CRITICAL** finding — a botched revert would silently disable a real safety
guard.

## Test Verification (NON-NEGOTIABLE)

Run the new security test module to confirm no regressions:

```bash
uv run pytest tests/integration/security/ -v --no-cov
```

Report results accurately in the contract. If any test fails unexpectedly (i.e.
not an xfailed genuine vulnerability), that is a **CRITICAL** finding.

## Severity Levels

| Severity | Meaning |
|----------|---------|
| **CRITICAL** | Breaks functionality, scope violation (production code touched), live-DB connection attempted, residual injection, genuine vulnerability fixed in-CR rather than xfailed |
| **HIGH** | Significant bug, missing AC, test module missing, vacuous guard (log-only), sync mismatch |
| **MEDIUM (fixable)** | Weak assertion, missing body check, marker not applied, Makefile comment missing |
| **MEDIUM (suggestion)** | Better pattern available |
| **LOW** | Nitpick |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "CR-00075",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "path/to/file.py",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, Y xfailed, 0 failed",
  "notes": ""
}
```

- `verdict`: `pass` only if zero CRITICAL/HIGH and zero MEDIUM (fixable).
- `mandatory_fix_count`: CRITICAL + HIGH + MEDIUM (fixable).
