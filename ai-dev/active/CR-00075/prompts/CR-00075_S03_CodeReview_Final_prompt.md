# CR-00075_S03_CodeReview_Final_prompt

**Work Item**: CR-00075 — Security Test Module
**Review Step**: S03 (Final Review)
**Implementation Steps Reviewed**: S01..S02

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY command that changes Docker container/volume/network
state. Allowed: testcontainers via pytest fixtures; read-only `docker ps|inspect|logs`;
`./ai-core.sh` and `make` targets. If your task seems to require a prohibited
command, STOP and raise a blocker. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

CR-00075 adds no migration. A migration file in the changeset is a **CRITICAL**
finding. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — prefer `uv run iw item-status CR-00075 --json`.
- `ai-dev/work/CR-00075/CR-00075_CR_Design.md` — design document.
- All step reports: `ai-dev/work/CR-00075/reports/CR-00075_S*_*_report.md`.
- All files listed in S01's `files_changed`.

## Output Files

- `ai-dev/work/CR-00075/reports/CR-00075_S03_CodeReview_Final_report.md` — final review report.

## Context

You are performing the **final cross-agent review** of CR-00075 — a
test-infrastructure CR adding an organised security regression test package.
The per-agent review (S02) is done; your job is to verify the whole package is
coherent, complete against the design, and safe to merge.

## Read the Design Document FIRST

Read `## Acceptance Criteria` (AC1–AC6) and `## TDD Approach` in full. Cross-check
the four named test modules against S01's `files_changed` — a missing one is
**CRITICAL**.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Run `make lint` and `make format-check` on the changed files. Any NEW violation
is a **CRITICAL** finding (`category: conventions`). If a command is unavailable,
STOP and raise a blocker.

## Review Checklist

### 1. Completeness vs the design — every AC

Verify each acceptance criterion end-to-end:

- **AC1** — the live-DB write-guard module covers at least two contexts (test-collection
  and agent-worktree); uses `monkeypatch` env-var injection only (never connects to
  port 5433); asserts the guard raises `LiveDbConnectionRefusedError` (or equivalent)
  behaviorally, not merely logs.
- **AC2** — the authz negative-path module sends requests without credentials or
  with wrong-scope credentials; asserts 4xx; never data, never 5xx; chat endpoints
  covered.
- **AC3** — the doc-render module tests all three input classes (`file://`, path
  traversal, internal-URL SSRF); asserts refusal or safe sentinel; no real network
  requests made; if no attack surface found, documented with at least one test.
- **AC4** — the agent-context module asserts operator-only commands blocked with
  `IW_CORE_AGENT_CONTEXT=true`; at least one bypass attempt covered; explicit
  refusal asserted (not silent no-op).
- **AC5** — any genuine vulnerability found is xfailed with a filed high-priority
  Incident ID, not fixed in-CR; no production code touched; SECURITY BLOCKER section
  in S01 report if any; the scope gate (scope.allowed_paths) has not been violated.
- **AC6** — strategy doc, skill, and plan updated; `.claude/skills/iw-ai-core-testing/SKILL.md`
  byte-identical to its master (run `diff`); `test-security-module` Makefile target
  has the comment distinguishing it from scanner targets.

### 2. Scope integrity (CRITICAL)

- Every changed file is within `scope.allowed_paths`. No `orch/` / `dashboard/` /
  `executor/` / `scripts/` production code edited.
- **No residual deliberate-break injection** — run
  `git diff origin/main -- orch/ dashboard/` and confirm it is empty. S01 patches
  guards to prove tests can fail, then reverts; a leftover patch would silently
  disable a production safety guard → **CRITICAL**.
- **No genuine vulnerability fixed in-CR.** If a genuine vulnerability was discovered
  and the production code was patched to fix it within this CR, that is a **CRITICAL**
  scope violation. The correct handling is xfail + high-priority Incident.

### 3. Security test effectiveness (holistic)

- **AC1 — live-DB guard can fail.** Confirm `tdd_red_evidence` records the deliberate-break
  demonstration. As an independent spot-check, you MAY temporarily patch `is_live_db_url`
  to return `False` and re-run `test_live_db_write_guard.py` to confirm it fails,
  then revert — state explicitly whether you did this.
- **AC3 — SSRF/path-traversal tests are not vacuous.** If S01 reported "No attack
  surface found", verify this claim by reading `orch/doc_service.py` and `orch/doc_sections.py`
  yourself. If a surface exists that S01 missed, that is **HIGH**.
- All four modules are order-independent under `pytest-randomly` and use the
  testcontainer DB, never the live DB.
- Assertions are behavioural (apply `skills/iw-ai-core-testing/SKILL.md`'s red-flag
  checklist to all four modules).

### 4. Cross-cutting coherence

- The Makefile target comment, the docs update, and the skill update all describe the
  security test module consistently — no contradictory claims (e.g. docs saying "blocking
  gate" while the tests are merely advisory, or Makefile comment missing the scanner
  distinction).
- `TESTS_ENHANCEMENT.md` §11 changelog counts (total security tests, xfailed count,
  Incidents filed) match the S01 report exactly.
- `skills/iw-workflow/SKILL.md` canonical QV-gate list was **not** modified — this
  CR deliberately adds no new QV gate. A new gate entry is scope creep → **HIGH**.

### 5. Architecture and security

- Read `CLAUDE.md`. The new tests follow the established `tests/integration/`
  testcontainer + `db_session` fixture pattern.
- No hardcoded secrets, URLs, or credentials in any test file.
- `monkeypatch` is used for all env-var injection — no module-level global state mutation.

## Test Verification (NON-NEGOTIABLE)

Run the **full unit + integration suites**:

```bash
make test-unit
make test-integration
```

`make test-integration` runs the new security modules — if any module fails
unexpectedly (i.e. not an xfailed genuine vulnerability), that is a **CRITICAL**
finding. Report results accurately. Also run the convenience target to confirm it
works in isolation:

```bash
make test-security-module
```

## Severity Levels

| Severity | Meaning |
|----------|---------|
| **CRITICAL** | Breaks functionality, scope violation (production code touched or genuine vulnerability fixed in-CR), live-DB connection attempted, residual injection, missing test module, integration suite fails |
| **HIGH** | Significant bug, missing AC, SSRF surface missed, scope creep (new QV gate), sync mismatch |
| **MEDIUM (fixable)** | Weak assertion, Makefile comment missing, body check missing |
| **MEDIUM (suggestion)** | Better pattern available |
| **LOW** | Nitpick |

## Review Result Contract

```json
{
  "step": "S03",
  "agent": "CodeReview_Final",
  "work_item": "CR-00075",
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
  "test_summary": "X unit passed, Y integration passed, Z xfailed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```

- `verdict`: `pass` only if zero CRITICAL/HIGH and zero MEDIUM (fixable).
- `missing_requirements`: any AC with no corresponding implementation — each is automatically CRITICAL.
