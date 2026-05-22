# CR-00072_S03_CodeReview_Final_prompt

**Work Item**: CR-00072 — Contract / No-5xx Route Sweep + schemathesis Fuzzing
**Review Step**: S03 (Final Review)
**Implementation Steps Reviewed**: S01..S02

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY command that changes Docker container/volume/network
state. Allowed: testcontainers via pytest fixtures; read-only `docker ps|inspect|logs`;
`./ai-core.sh` and `make` targets. If your task seems to require a prohibited
command, STOP and raise a blocker. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

CR-00072 adds no migration. A migration file in the changeset is a **CRITICAL**
finding. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — prefer `uv run iw item-status CR-00072 --json`.
- `ai-dev/work/CR-00072/CR-00072_CR_Design.md` — design document.
- All step reports: `ai-dev/work/CR-00072/reports/CR-00072_S*_*_report.md`.
- All files listed in S01's `files_changed`.

## Output Files

- `ai-dev/work/CR-00072/reports/CR-00072_S03_CodeReview_Final_report.md` — final review report.

## Context

You are performing the **final cross-agent review** of CR-00072 — a
test-infrastructure CR adding a no-5xx route sweep and a nightly schemathesis
fuzz module. The per-agent review (S02) is done; your job is to verify the whole
package is coherent, complete against the design, and safe to merge.

## Read the Design Document FIRST

Read `## Acceptance Criteria` (AC1–AC6) and `## TDD Approach` in full. Cross-check
the two named test files against S01's `files_changed` — a missing one is
**CRITICAL**.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Run `make lint` and `make format-check` on the changed files. Any NEW violation
is a **CRITICAL** finding (`category: conventions`). If a command is unavailable,
STOP and raise a blocker.

## Review Checklist

### 1. Completeness vs the design — every AC

Verify each acceptance criterion end-to-end:

- **AC1** — the sweep enumerates `app.routes`, exercises every GET/HEAD route
  minus the documented skip set, uses `raise_server_exceptions=False`, asserts
  `status_code < 500`, is parametrized one case per route.
- **AC2** — the sweep lives under `tests/dashboard/` (so `make test-integration`
  runs it); confirm `skills/iw-workflow/SKILL.md`'s canonical QV-gate list was
  **not** modified — this CR deliberately adds no new QV gate. A new gate entry
  is scope creep → **HIGH**.
- **AC3** — `contract_fuzz` marker registered + in the `addopts` exclusion;
  independently verify
  `uv run pytest tests/dashboard/test_schemathesis_contract.py --collect-only -q`
  collects **zero** tests.
- **AC4** — `contract-fuzz.yml` triggers on `schedule` + `workflow_dispatch`
  only; runs `make test-contract-fuzz`; non-failing during burn-in.
- **AC5** — any `EXPECTED_5XX` entry has a `TODO(file-incident)` placeholder +
  rationale + `xfail` and is listed as operator follow-up in the S01 report;
  the sweep exits 0 on `main`; **no production code was edited** to fix a 5xx,
  and no incident package (`ai-dev/active/I-NNNNN/**`) was created in the
  worktree.
- **AC6** — strategy doc, skill, and plan updated; `.claude/skills/iw-ai-core-testing/SKILL.md`
  byte-identical to its master (run `diff`).

### 2. Scope integrity (CRITICAL)

- Every changed file is within `scope.allowed_paths`. No `orch/` / `dashboard/` /
  `executor/` / `scripts/` production code edited.
- **No residual deliberate-break injection** — run
  `git diff origin/main -- dashboard/ orch/` and confirm it is empty. S01
  proves the sweep can fail by registering throwaway 5xx routes on the *test*
  app (never editing production code), then removing them; a leftover production
  edit, or a throwaway `/__cr72_selfcheck__`-style route left in the committed
  test files, is **CRITICAL**.

### 3. Cross-cutting coherence

- The `pyproject.toml` marker description, the `Makefile` target, the workflow
  file, and the docs all describe `contract_fuzz` / the contract layer
  consistently — no contradictory claims (e.g. docs saying "blocking" while the
  workflow is `continue-on-error`).
- `uv.lock` is consistent with the `schemathesis` constraint in `pyproject.toml`.
- The `TESTS_ENHANCEMENT.md` §11 changelog counts (routes swept, `EXPECTED_5XX`,
  `TODO(file-incident)` placeholders raised) match S01's report exactly.

### 4. Test effectiveness (holistic)

- The route sweep **can fail** — confirm `tdd_red_evidence` records the
  deliberate-break demonstration. As an independent spot-check, you MAY (when
  quick and safe) register a throwaway 5xx route on the test app, confirm its
  case fails, then remove it — never edit production code — and state explicitly
  whether you did this.
- Assertions are behavioural and strong (apply `skills/iw-ai-core-testing/SKILL.md`'s
  red-flag checklist).
- Both new tests are order-independent under `pytest-randomly` and use the
  testcontainer DB, never the live DB.

### 5. Architecture & security

- Read `CLAUDE.md`. The new tests follow the established `tests/dashboard/`
  `TestClient` + `get_db`-override pattern.
- No hardcoded secrets, URLs, or credentials in the workflow file or the tests.

## Test Verification (NON-NEGOTIABLE)

Run the **full unit + integration suites**:

```bash
make test-unit
make test-integration
```

`make test-integration` runs the new route sweep — if it fails, that is a
**CRITICAL** finding. Report results accurately. (You need not run
`make test-contract-fuzz` — it is nightly-only — but you may run it once to
confirm it is green.)

## Severity Levels

| Severity | Meaning |
|----------|---------|
| **CRITICAL** | Breaks functionality, scope violation, residual injection, missing requirement, integration suite fails |
| **HIGH** | Significant bug, missing AC, scope creep (new QV gate / fuzzer in blocking suite) |
| **MEDIUM (fixable)** | Code-quality / convention issue |
| **MEDIUM (suggestion)** | Better pattern available |
| **LOW** | Nitpick |

## Review Result Contract

```json
{
  "step": "S03",
  "agent": "CodeReview_Final",
  "work_item": "CR-00072",
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
