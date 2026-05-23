# CR-00073_S03_CodeReview_Final_prompt

**Work Item**: CR-00073 — iw CLI Contract Test Layer
**Review Step**: S03 (Final Review)
**Implementation Steps Reviewed**: S01..S02

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY command that changes Docker container/volume/network
state. Allowed: testcontainers via pytest fixtures; read-only `docker ps|inspect|logs`;
`./ai-core.sh` and `make` targets. If your task seems to require a prohibited
command, STOP and raise a blocker. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

CR-00073 adds no migration. A migration file in the changeset is a **CRITICAL**
finding. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — prefer `uv run iw item-status CR-00073 --json`.
- `ai-dev/work/CR-00073/CR-00073_CR_Design.md` — design document.
- All step reports: `ai-dev/work/CR-00073/reports/CR-00073_S*_*_report.md`.
- All files listed in S01's `files_changed`.

## Output Files

- `ai-dev/work/CR-00073/reports/CR-00073_S03_CodeReview_Final_report.md` — final review report.

## Context

You are performing the **final cross-agent review** of CR-00073 — a
test-infrastructure CR adding a per-command CLI contract test layer and a
spec-conformance drift check. The per-agent review (S02) is done; your job is to
verify the whole package is coherent, complete against the design, and safe to
merge.

## Read the Design Document FIRST

Read `## Acceptance Criteria` (AC1–AC6) and `## TDD Approach` in full. Cross-check
all named test files against S01's `files_changed` — a missing one is **CRITICAL**.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Run `make lint` and `make format-check` on the changed files. Any NEW violation
is a **CRITICAL** finding (`category: conventions`). If a command is unavailable,
STOP and raise a blocker.

## Review Checklist

### 1. Completeness vs the design — every AC

Verify each acceptance criterion end-to-end:

- **AC1** — all six priority command groups (`step-done`, `register`, `doc-update`,
  `approve`, `next-id`, evidence-ingestion hooks) have contract test classes;
  each class asserts exit code + stderr + stdout + DB effect; `next-id`
  concurrency test uses `ThreadPoolExecutor`; `register` idempotency-key tested.
- **AC2** — `test_cli_spec_conformance.py` exists; parses the **§4 "Command
  Summary"** fenced ASCII tree (not the §3.x option tables); introspects the
  Click tree recursively; asserts both directions of coverage (spec→CLI and
  CLI→spec); asserts every spec command has a contract test OR is in
  `KNOWN_UNTESTED_COMMANDS`.
- **AC3** — `KNOWN_SPEC_DRIFT` and `KNOWN_UNTESTED_COMMANDS` are both
  module-level constants; `KNOWN_SPEC_DRIFT` entries carry `"reason"` +
  `"direction"`; `KNOWN_UNTESTED_COMMANDS` entries carry `"reason"` and are
  pre-seeded with every non-priority command; the test skips allowlisted entries
  and fails on NEW drift / NEW untested commands only.
- **AC4** — all tests live under `tests/integration/` and are collected by
  `make test-integration`; confirm `skills/iw-workflow/SKILL.md`'s canonical
  QV-gate list was **not** modified (no new gate — this is scope creep → **HIGH**).
- **AC5** — `tdd_red_evidence` records the **monkeypatch** demonstration for both
  a contract test and the conformance test; the demonstration is test-code-only
  (no `orch/` edit at any point).
- **AC6** — strategy doc, skill, and plan updated; `.claude/skills/iw-ai-core-testing/SKILL.md`
  byte-identical to its master (run `diff`).

### 2. Scope integrity (CRITICAL)

- Every changed file is within `scope.allowed_paths`. No `orch/cli/`, `orch/`,
  `dashboard/`, `executor/`, or `scripts/` production code was edited (other than
  allowed doc fixes in `docs/IW_AI_Core_CLI_Spec.md`).
- **No production-code edit at all** — run
  `git diff origin/main -- orch/ dashboard/ executor/ scripts/` and confirm it
  is empty. S01 proves the tests can fail with pytest `monkeypatch` (test code
  only, auto-reverting); it must never edit a production file, even temporarily.
  Any non-empty diff here is a **CRITICAL** scope violation.
- **No incident package created inside the worktree** — an `ai-dev/active/I-NNNNN/**`
  path anywhere in the changeset is a **CRITICAL** scope violation. Genuine CLI
  bugs must be `xfail`-ed (or recorded in `KNOWN_CLI_BUG`) with a
  `TODO(file-incident)` placeholder and listed as operator follow-up in the S01
  report; the operator files the Incident on `main` post-merge.
- Any edit to `docs/IW_AI_Core_CLI_Spec.md` is doc-only (text/table changes);
  no executable code or imports were added.

### 3. Cross-cutting coherence

- The `KNOWN_SPEC_DRIFT` allowlist, the `Makefile` target, the strategy doc,
  and the skill all describe the CLI contract layer consistently — no contradictory
  claims (e.g. skill saying "run test-cli-contract for the canonical gate" while
  the design says it is a convenience target only).
- `TESTS_ENHANCEMENT.md` §11 changelog counts (priority commands covered, drift
  entries, `TODO(file-incident)` placeholders raised) match S01's report exactly.
- `docs/IW_AI_Core_CLI_Spec.md` changes (if any) are limited to adding or
  correcting entries in the §4 "Command Summary" tree (and matching §3.x detail
  prose) — no structural rewrites.

### 4. Test effectiveness (holistic)

- The contract tests **can fail** — confirm `tdd_red_evidence` records the
  monkeypatch demonstration. As an independent spot-check, you MAY (when quick
  and safe) add a temporary throwaway test that `monkeypatch`-breaks one
  command's behaviour, run `make test-cli-contract`, confirm a failure, then
  delete the throwaway test — state explicitly whether you did this. Do NOT edit
  any `orch/` file for the spot-check.
- Assertions are behavioural and strong (apply `skills/iw-ai-core-testing/SKILL.md`'s
  red-flag checklist).
- All new tests are order-independent under `pytest-randomly` and use the
  testcontainer DB, never the live DB.
- The spec-conformance test is deterministic — it does not rely on file-system
  ordering or import-time side effects.

### 5. Architecture & security

- Read `CLAUDE.md`. The new tests follow the established `tests/integration/`
  pattern for CLI testing (CliRunner + testcontainer `db_session`).
- No hardcoded secrets, live DB credentials, or production DB URLs in any test
  file.
- The spec parser does not execute the spec document — it only reads and parses
  Markdown text.

## Test Verification (NON-NEGOTIABLE)

Run the **full unit + integration suites**:

```bash
make test-unit
make test-integration
```

`make test-integration` runs the new CLI contract tests — if it fails, that is a
**CRITICAL** finding. Report results accurately.

## Severity Levels

| Severity | Meaning |
|----------|---------|
| **CRITICAL** | Breaks functionality, scope violation, residual injection, missing requirement, integration suite fails |
| **HIGH** | Significant bug, missing AC, scope creep (new QV gate), allowlist entry with no rationale |
| **MEDIUM (fixable)** | Code-quality / convention issue |
| **MEDIUM (suggestion)** | Better pattern available |
| **LOW** | Nitpick |

## Review Result Contract

```json
{
  "step": "S03",
  "agent": "CodeReview_Final",
  "work_item": "CR-00073",
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
