# CR-00074_S03_CodeReview_Final_prompt

**Work Item**: CR-00074 — Cross-Project Isolation Test Matrix
**Review Step**: S03 (Final Review)
**Implementation Steps Reviewed**: S01..S02

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY command that changes Docker container/volume/network
state. Allowed: testcontainers via pytest fixtures; read-only `docker ps|inspect|logs`;
`./ai-core.sh` and `make` targets. If your task seems to require a prohibited
command, STOP and raise a blocker. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

CR-00074 adds no migration. A migration file in the changeset is a **CRITICAL**
finding. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — prefer `uv run iw item-status CR-00074 --json`.
- `ai-dev/work/CR-00074/CR-00074_CR_Design.md` — design document.
- All step reports: `ai-dev/work/CR-00074/reports/CR-00074_S*_*_report.md`.
- All files listed in S01's `files_changed`.

## Output Files

- `ai-dev/work/CR-00074/reports/CR-00074_S03_CodeReview_Final_report.md` — final review report.

## Context

You are performing the **final cross-agent review** of CR-00074 — a
test-infrastructure CR adding a cross-project isolation test matrix. The
per-agent review (S02) is done; your job is to verify the whole package is
coherent, complete against the design, and safe to merge.

## Read the Design Document FIRST

Read `## Acceptance Criteria` (AC1–AC7) and `## TDD Approach` in full. Cross-check
the named test file and modified conftest against S01's `files_changed` — a missing
file is **CRITICAL**.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Run `make lint` and `make format-check` on the changed files. Any NEW violation
is a **CRITICAL** finding (`category: conventions`). If a command is unavailable,
STOP and raise a blocker.

## Review Checklist

### 1. Completeness vs the design — every AC

Verify each acceptance criterion end-to-end:

- **AC1** — `second_project` fixture in `tests/integration/conftest.py`: function-scoped,
  both projects seeded with full entity set, distinct identifiers, no impact on
  existing `test_project` tests.
- **AC2** — Dashboard-route isolation matrix: project B requests return no project A
  identifiers, behavioural assertions (`not in response.text` or equivalent),
  parametrized per route, `KNOWN_LEAK` entries carry filed high-priority Incidents +
  `xfail`, matrix exits 0 on `main`.
- **AC3** — `iw`-command isolation: read/query commands assert *output isolation*
  (project A identifiers absent from the project-B command output); mutating
  commands assert *mutation isolation* (project A rows byte-for-byte unchanged);
  no vacuous "rows unchanged after a read" assertion; isolation mode labelled in
  the parametrize ID; only project-scoped commands covered.
- **AC4** — Global-aggregation positive assertion: `/docs` and `/jobs` contain
  both projects' data, cases labelled as `aggregation_check`.
- **AC5** — Per-worktree-DB vs orch-DB boundary: exercises `orch/config.py`
  resolution — `get_db_url()` / `get_orch_db_url()` resolved against two distinct
  testcontainers, sessions see only their own rows, `_prefer` fallback verified —
  NOT two unrelated sessions (a tautology → **HIGH**); references the F-00062
  contract.
- **AC6** — `KNOWN_LEAK` mechanism + TDD RED evidence: `tdd_red_evidence` records
  the deliberate-break demonstration (isolation case fail + boundary case fail);
  both injections confirmed reverted.
- **AC7** — strategy doc, skill, and plan updated; `.claude/skills/iw-ai-core-testing/SKILL.md`
  byte-identical to its master (run `diff`).

### 2. Scope integrity (CRITICAL)

- Every changed file is within `scope.allowed_paths`. No `orch/` / `dashboard/` /
  `executor/` / `scripts/` production code edited.
- **No residual deliberate-break injection** — run
  `git diff origin/main -- dashboard/ orch/` and confirm it is empty. S01 removes
  a `project_id` filter from a route handler and breaks `orch/config.py`'s
  env-var resolution to prove the tests can fail, then reverts both; a leftover
  injection would cause a real isolation leak in production → **CRITICAL**.
- No migration file was added → **CRITICAL** if present.

### 3. Cross-cutting coherence

- The `second_project` fixture, the isolation matrix, the `KNOWN_LEAK` dict,
  and the docs all describe the same scope consistently — no contradictory claims.
- `TESTS_ENHANCEMENT.md` §11 changelog counts (routes asserted, commands asserted,
  `KNOWN_LEAK` entries, Incidents filed) match S01's report exactly.
- The `Makefile` `test-isolation` target is wired to
  `tests/integration/test_cross_project_isolation.py` and is in `.PHONY`.
- `skills/iw-workflow/SKILL.md`'s canonical QV-gate list was **not** modified —
  this CR adds no new canonical gate. A new gate entry is scope creep → **HIGH**.

### 4. Test effectiveness (holistic)

- The isolation matrix **can fail** — confirm `tdd_red_evidence` records the
  deliberate-break demonstration. As an independent spot-check, you MAY (when
  quick and safe) re-run one parametrized case after temporarily removing a
  `project_id` filter from a trivial route, then revert — state explicitly
  whether you did this.
- Assertions are behavioural and strong (apply `skills/iw-ai-core-testing/SKILL.md`'s
  red-flag checklist). An assertion of `assert response.status_code == 200`
  alone is not sufficient for an isolation check → **HIGH**.
- All new tests are order-independent under `pytest-randomly` and use the
  testcontainer DB, never the live DB.
- The `second_project` fixture is function-scoped — a module or session scope
  would violate the `pgtestdbpy` contract → **HIGH**.

### 5. Architecture & security

- Read `CLAUDE.md`. The new tests follow the established `tests/integration/`
  testcontainer + SQLAlchemy session patterns.
- No hardcoded secrets, URLs, credentials, or port numbers in the test file
  or the fixture.
- `KNOWN_LEAK` entries for genuine isolation leaks each carry a filed
  high-priority Incident — a genuine leak with no Incident and no blocker is a
  security-class finding → **HIGH**.

## Test Verification (NON-NEGOTIABLE)

Run the **full unit + integration suites**:

```bash
make test-unit
make test-integration
```

`make test-integration` runs the new isolation matrix — if it fails, that is a
**CRITICAL** finding. Report results accurately.

## Severity Levels

| Severity | Meaning |
|----------|---------|
| **CRITICAL** | Breaks functionality, scope violation, residual injection, missing requirement, integration suite fails |
| **HIGH** | Significant bug, missing AC, non-behavioural isolation assertion, KNOWN_LEAK without Incident, scope creep (new QV gate) |
| **MEDIUM (fixable)** | Code-quality / convention issue |
| **MEDIUM (suggestion)** | Better pattern available |
| **LOW** | Nitpick |

## Review Result Contract

```json
{
  "step": "S03",
  "agent": "CodeReview_Final",
  "work_item": "CR-00074",
  "steps_reviewed": ["S01", "S02"],
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "completeness|consistency|integration|testing|architecture|security",
      "file": "path/to/file.py",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it",
      "cross_cutting": true
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```

- `verdict`: `pass` only if zero CRITICAL/HIGH and zero MEDIUM (fixable).
- `missing_requirements`: any AC with no corresponding implementation — each is automatically CRITICAL.
