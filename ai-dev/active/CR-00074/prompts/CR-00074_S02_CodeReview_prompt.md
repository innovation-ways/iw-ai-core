# CR-00074_S02_CodeReview_prompt

**Work Item**: CR-00074 — Cross-Project Isolation Test Matrix
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

CR-00074 adds no migration. If you find a migration file in the changeset, that
is a **CRITICAL** scope violation. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — prefer `uv run iw item-status CR-00074 --json`.
- `ai-dev/work/CR-00074/CR-00074_CR_Design.md` — design document.
- `ai-dev/work/CR-00074/reports/CR-00074_S01_Backend_report.md` — S01 report.
- All files listed in the S01 report's `files_changed`.

## Output Files

- `ai-dev/work/CR-00074/reports/CR-00074_S02_CodeReview_report.md` — review report.

## Context

You are reviewing the S01 implementation of CR-00074 — a test-infrastructure CR
that adds a cross-project isolation test matrix. Read the design document first
(especially the Acceptance Criteria and TDD Approach sections), then the S01
report, then every changed file.

## Read the Design Document FIRST

Read `## Acceptance Criteria` (AC1–AC7) and `## TDD Approach` in full. Every AC
is a mandatory check. Note the test file the design names by path
(`tests/integration/test_cross_project_isolation.py`) — it MUST appear in S01's
`files_changed`; a missing one is **CRITICAL**. Also confirm
`tests/integration/conftest.py` is in `files_changed` (the `second_project`
fixture was added there).

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Run `make lint` and `make format-check` on the changed files. Fix nothing — only
report. Any NEW violation (not on `main` before S01) is a **CRITICAL** finding
with `category: conventions`, the file/line, and the exact code+message. Also run
`make test-assertions` — a new assertion-scanner violation in the new test file
is **CRITICAL**. If a command is unavailable, STOP and raise a blocker.

## Review Checklist

### 1. Scope discipline (CRITICAL category)

- **No production code touched.** The only files changed must be within
  `scope.allowed_paths`: `tests/integration/test_cross_project_isolation.py`,
  `tests/integration/conftest.py`, `tests/fixtures/**`, `Makefile`,
  `docs/IW_AI_Core_Testing_Strategy.md`, `skills/iw-ai-core-testing/**`,
  `.claude/skills/iw-ai-core-testing/**`, `ai-dev/work/TESTS_ENHANCEMENT.md`.
  Any edit to `orch/`, `dashboard/`, `executor/`, `scripts/` is a **CRITICAL**
  scope violation — including a "fix" for an isolation leak the matrix found
  (those must be allowlisted, not fixed; see AC2/AC6).
- **No deliberate-break injection left behind.** S01's TDD demonstration inverts
  assertions inside the test file (never editing production code), then reverts
  both. Confirm via `git diff origin/main -- orch/ dashboard/ executor/ scripts/`
  that it is **empty** (no production code touched), and that no inverted assertion
  remains in the committed test files. Any production-code edit, or a residual
  inverted assertion, is **CRITICAL**.

### 2. AC1 — `second_project` fixture correctness

- `tests/integration/conftest.py` contains a `second_project` fixture.
- The fixture is function-scoped — module or session scope would violate the
  `pgtestdbpy` template-clone strategy (CR-00055) → **HIGH**.
- Both projects (project A = `test_project`, project B = `second_project`) are
  seeded with at least one work item, one batch, one doc, one code-index row,
  and one job-like row each.
- The seeded identifiers are distinct between the two projects — no ID or name
  overlap that would make a leak undetectable → **HIGH** if overlap exists.
- Existing tests using `test_project` alone are unaffected.

### 3. AC2 — Dashboard-route isolation matrix correctness

- The matrix enumerates project-scoped dashboard routes and requests each scoped
  to project B.
- The `get_db` override is wired correctly (follow `test_jobs_filter_ui.py`
  pattern; `IW_CORE_EXPECTED_INSTANCE_ID` popped if needed).
- Assertions are behavioural: `assert str(proj_a_item_id) not in response.text`
  (or equivalent). An assertion like `assert response.status_code == 200` alone
  is NOT sufficient for isolation → **HIGH**.
- Cases are parametrized one per route so failures name the leaking route.
- `KNOWN_LEAK` entries each carry a `TODO(file-incident)` placeholder and rationale,
  and the corresponding case is `xfail`-ed — not deleted, not skipped silently.
  Each placeholder must also be listed under "Operator follow-up" in the S01
  report. An allowlisted route with no placeholder, no rationale, or not listed
  for the operator is **HIGH**. An entry with a real Incident ID (meaning S01 ran
  `/iw-new-incident` from inside the worktree) is a **CRITICAL** scope violation —
  check that no `ai-dev/active/I-NNNNN/**` path appears in the changeset.
- The matrix exits 0 on current `main`.

### 4. AC3 — `iw`-command isolation assertions

- Project-scoped `iw` commands are exercised targeting project B.
- **Read/query commands** assert *output isolation* — the command output contains
  none of project A's identifiers. A vacuous "row counts unchanged after a read"
  assertion is **HIGH** (a read never mutates rows, so it can never fail and will
  trip the `test-assertions` scanner).
- **Mutating commands** assert *mutation isolation* — project A's rows are
  byte-for-byte unchanged (counts AND content) before/after, and the command's
  effect did land on project B.
- The isolation mode (`output` / `mutation`) is labelled in the parametrize ID.
- Global `iw` commands (e.g. `iw db-identity check`) are NOT included — including
  them would be incorrect scope → **MEDIUM (fixable)**.
- Cases are parametrized one per command.

### 5. AC4 — Global-aggregation positive assertion

- Global `/docs` and `/jobs` routes are requested without a project scope filter.
- Assertions confirm identifiers from BOTH projects appear in the response.
- These cases are labelled `aggregation_check` (or equivalent) in the parametrize
  ID so their intent is clear.

### 6. AC5 — Per-worktree-DB vs orch-DB boundary (F-00062)

- The boundary test exercises `orch/config.py` resolution: `get_db_url()` and
  `get_orch_db_url()` are resolved against two distinct testcontainers pointed at
  by `IW_CORE_DB_*` and `IW_CORE_ORCH_DB_*`. A test that only opens two unrelated
  SQLAlchemy sessions and asserts they don't share rows is a **tautology** →
  **HIGH** (it tests Postgres, not IW AI Core).
- Assertions confirm `get_db_url()` / `get_orch_db_url()` resolve to the correct
  distinct containers, a session on each sees only its own rows, and the
  `_prefer` fallback holds when `IW_CORE_ORCH_DB_*` is unset.
- Env vars are set via `monkeypatch.setenv` — `importlib.reload(orch.config)` is
  forbidden (CLAUDE.md) → **HIGH** if used.
- References `tests/integration/test_per_worktree_isolation.py` and the
  F-00062 / `IW_CORE_DB_*` vs `IW_CORE_ORCH_DB_*` contract.

### 7. AC6 — KNOWN_LEAK allowlist mechanism + TDD RED evidence

- The `KNOWN_LEAK` allowlist is a module-level dict with the correct structure
  (route/command key → `TODO(file-incident)` placeholder + rationale).
- `tdd_red_evidence` records the **deliberate-break demonstration** for both the
  isolation axis and the boundary axis — S01 inverts assertions inside the test
  file (never editing production code), confirms RED, then reverts. If
  `tdd_red_evidence` is missing, says `n/a` with no demonstration, or describes
  editing production `orch/` / `dashboard/` code, raise a **HIGH** finding: an
  isolation matrix that cannot be shown to fail (or whose proof edits production
  code) is worthless.

### 8. AC7 — Docs / skill / plan

- `docs/IW_AI_Core_Testing_Strategy.md` describes the isolation-matrix layer (§3/§5/§9).
- `skills/iw-ai-core-testing/SKILL.md` notes the matrix layer + how to extend it.
- `.claude/skills/iw-ai-core-testing/SKILL.md` is **byte-identical** to the
  master (`diff` them — a mismatch means `iw sync-skills --force` was not run →
  **HIGH**).
- `ai-dev/work/TESTS_ENHANCEMENT.md`: item 3.4 → DONE (CR-00074); a §11
  changelog entry exists; counts in the changelog match the S01 report.

### 9. Test quality & isolation

- New tests use the testcontainer `db_session` — never the live DB.
- Tests are order-independent (`pytest-randomly` is on by default). Seeding
  happens per-test/per-fixture; no reliance on another test's state.
- The `second_project` fixture is function-scoped — no shared state.
- Assertions are behavioural and strong — re-read `skills/iw-ai-core-testing/SKILL.md`'s
  red-flag checklist and apply it.

## TDD RED Evidence

S01 is a test-infrastructure step. Confirm `tdd_red_evidence` records the
**deliberate-break demonstration** — S01 inverts assertions inside the test file
(an isolation case failing RED when a `not in` check is temporarily changed to
`in`; a boundary case failing RED when the URL-not-equal assertion is inverted),
then reverts both test-file edits. The demonstration NEVER touches production
`orch/` or `dashboard/` code. This is the "every test must be able to fail" proof.

## Test Verification (NON-NEGOTIABLE)

Run the new test file:

```bash
uv run pytest tests/integration/test_cross_project_isolation.py -v --no-cov
```

Report results accurately in the contract.

## Severity Levels

| Severity | Meaning |
|----------|---------|
| **CRITICAL** | Breaks functionality, scope violation, residual injection, security issue |
| **HIGH** | Significant bug, missing AC, assertions not behavioural, KNOWN_LEAK without Incident |
| **MEDIUM (fixable)** | Code-quality / convention issue, weak assertion |
| **MEDIUM (suggestion)** | Better pattern available |
| **LOW** | Nitpick |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "CR-00074",
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
