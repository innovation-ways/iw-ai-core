# CR-00073_S02_CodeReview_prompt

**Work Item**: CR-00073 — iw CLI Contract Test Layer
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

CR-00073 adds no migration. If you find a migration file in the changeset, that
is a **CRITICAL** scope violation. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — prefer `uv run iw item-status CR-00073 --json`.
- `ai-dev/work/CR-00073/CR-00073_CR_Design.md` — design document.
- `ai-dev/work/CR-00073/reports/CR-00073_S01_Backend_report.md` — S01 report.
- All files listed in the S01 report's `files_changed`.

## Output Files

- `ai-dev/work/CR-00073/reports/CR-00073_S02_CodeReview_report.md` — review report.

## Context

You are reviewing the S01 implementation of CR-00073 — a test-infrastructure CR
that adds a per-command CLI contract test layer and a spec-conformance drift
check. Read the design document first (especially the Acceptance Criteria and TDD
Approach sections), then the S01 report, then every changed file.

## Read the Design Document FIRST

Read `## Acceptance Criteria` (AC1–AC6) and `## TDD Approach` in full. Every AC
is a mandatory check. Note the test files the design names by path — all must
appear in S01's `files_changed`; any missing file is **CRITICAL**.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Run `make lint` and `make format-check` on the changed files. Fix nothing — only
report. Any NEW violation (not on `main` before S01) is a **CRITICAL** finding
with `category: conventions`, the file/line, and the exact code+message. Also run
`make test-assertions` — a new assertion-scanner violation in any new test file
is **CRITICAL**. If a command is unavailable, STOP and raise a blocker.

## Review Checklist

### 1. Scope discipline (CRITICAL category)

- **No production code touched.** The only files changed must be within
  `scope.allowed_paths`: test files under `tests/integration/cli/` and
  `tests/integration/test_cli_spec_conformance.py`, possibly `tests/integration/conftest.py`
  and `tests/fixtures/**`, `Makefile`, `docs/IW_AI_Core_CLI_Spec.md` (doc-only
  fixes allowed), `docs/IW_AI_Core_Testing_Strategy.md`,
  `skills/iw-ai-core-testing/**`, `.claude/skills/iw-ai-core-testing/**`,
  `ai-dev/work/TESTS_ENHANCEMENT.md`. Any edit to `orch/cli/`, `orch/`,
  `dashboard/`, `executor/`, or `scripts/` is a **CRITICAL** scope violation —
  including a "fix" for a CLI bug the contract tests found (those must be
  allowlisted in `KNOWN_SPEC_DRIFT` or a `KNOWN_CLI_BUG` dict with a filed
  Incident, never fixed in-CR).
- **No production-code edit, not even temporary.** S01's TDD demonstration uses
  pytest `monkeypatch` inside test code — it must never edit `orch/`, the spec
  doc's executable areas, or any production module. Confirm via
  `git diff origin/main -- orch/ dashboard/ executor/ scripts/` that it is
  **empty** — any production-code change at all is a **CRITICAL** scope
  violation. Also confirm no throwaway demonstration test was left behind.

### 2. AC1 — per-command contract coverage

- All six priority command groups have contract test classes:
  `step-done`, `register`, `doc-update`, `approve`, `next-id`,
  evidence-ingestion hooks.
- For each group: at least one test asserts exit code 0 on a success path; at
  least one asserts non-zero exit + clear stderr on an error path; at least one
  asserts stdout shape; at least one asserts DB row effects via `db_session`.
- For `next-id`: at least one test asserts concurrency safety (no duplicate IDs
  under concurrent calls, using `ThreadPoolExecutor`).
- For `register`: at least one test asserts idempotency-key behaviour.
- For the evidence-ingestion hooks: the test asserts that evidence records are
  written to the DB after the triggering command runs.
- Assertions are behavioural and strong — re-read `skills/iw-ai-core-testing/SKILL.md`'s
  red-flag checklist and apply it. An assertion like `assert result.exit_code is not None`
  is worthless → **CRITICAL**.

### 3. AC2 — spec-conformance bidirectional drift check

- `tests/integration/test_cli_spec_conformance.py` exists.
- It parses the **§4 "Command Summary"** fenced ASCII tree in
  `docs/IW_AI_Core_CLI_Spec.md` (NOT the §3.x option tables) and introspects the
  Click command tree recursively via `.commands`.
- It asserts both directions: every spec command exists in the CLI, and every CLI
  command is in the spec.
- It asserts that every spec command either has at least one contract test in
  `tests/integration/cli/` **or** is listed in `KNOWN_UNTESTED_COMMANDS`.

### 4. AC3 — KNOWN_SPEC_DRIFT and KNOWN_UNTESTED_COMMANDS allowlists

- Both allowlists are module-level constants in `test_cli_spec_conformance.py`.
- `KNOWN_SPEC_DRIFT` (existence drift): each entry keyed by command name, with a
  `"reason"` (Incident ID or one-line rationale) and a `"direction"`
  (`"spec_only"` or `"cli_only"`). An entry with no Incident ID and no rationale
  is **HIGH**.
- `KNOWN_UNTESTED_COMMANDS` (coverage gap): each entry keyed by command name with
  a `"reason"`. It must be pre-seeded with every non-priority command so the
  conformance test passes on first merge; an entry with no rationale is **HIGH**.
  An entry for one of the 6 priority commands (which DO have tests) is a mistake
  → **MEDIUM (fixable)**.
- The conformance test skips allowlisted entries and fails only on NEW drift /
  NEW untested commands.

### 5. AC4 — no new QV gate

- All new tests live under `tests/integration/` and are collected by
  `make test-integration` automatically.
- `skills/iw-workflow/SKILL.md` (the canonical QV-gate list) was NOT modified —
  adding a new gate entry would be scope creep → **HIGH**.
- The `test-cli-contract` Makefile target exists and is `.PHONY`-declared — it is
  a convenience target only, not a new canonical gate.

### 6. AC5 — tdd_red_evidence (monkeypatch demonstration)

- S01's report contains `tdd_red_evidence` describing the **monkeypatch**
  demonstration for both new test areas (a contract test failing when a
  monkeypatch breaks the command's DB-write/exit; the conformance test reporting
  injected drift when a monkeypatch drops a command from the parsed spec or CLI
  set).
- If `tdd_red_evidence` is missing or just says `n/a` with no demonstration,
  raise a **HIGH** finding: a contract test that cannot be shown to fail is
  worthless.
- The demonstration MUST be `monkeypatch`-based and in test code only. If the
  evidence describes editing `orch/` (or any production file) and reverting it,
  that is a process violation — raise **MEDIUM (fixable)** and confirm via
  `git diff origin/main` that no production file is actually modified.

### 7. AC6 — docs / skill / plan

- `docs/IW_AI_Core_Testing_Strategy.md` describes the CLI contract layer (§3/§5/§9).
- `skills/iw-ai-core-testing/SKILL.md` notes the layer + how to extend it.
- `.claude/skills/iw-ai-core-testing/SKILL.md` is **byte-identical** to the
  master (`diff` them — a mismatch means `iw sync-skills --force` was not run →
  **HIGH**).
- `ai-dev/work/TESTS_ENHANCEMENT.md`: item 3.3 → DONE (CR-00073); a §11
  changelog entry exists; counts in the changelog match the S01 report.

### 8. Test quality & isolation

- All new tests use the testcontainer `db_session` — never the live DB.
- Tests are order-independent (`pytest-randomly` is on by default). Seeding
  happens per-test/per-fixture; no reliance on another test's state.
- `CliRunner` is used with `mix_stderr=False` so stdout and stderr are testable
  independently.

## Test Verification (NON-NEGOTIABLE)

Run the new test files to confirm no regressions:

```bash
uv run pytest tests/integration/cli/ -v --no-cov
uv run pytest tests/integration/test_cli_spec_conformance.py -v --no-cov
```

Report results accurately in the contract.

## Severity Levels

| Severity | Meaning |
|----------|---------|
| **CRITICAL** | Breaks functionality, scope violation, residual injection, security issue |
| **HIGH** | Significant bug, missing AC, allowlist entry with no rationale, tdd_red_evidence absent |
| **MEDIUM (fixable)** | Code-quality / convention issue, weak assertion |
| **MEDIUM (suggestion)** | Better pattern available |
| **LOW** | Nitpick |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "CR-00073",
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
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```

- `verdict`: `pass` only if zero CRITICAL/HIGH and zero MEDIUM (fixable).
- `mandatory_fix_count`: CRITICAL + HIGH + MEDIUM (fixable).
