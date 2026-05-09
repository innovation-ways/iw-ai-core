# {TYPE}{NNN}_S{NN}_CodeReview_Final_prompt

**Work Item**: {ID} -- {Title}
**Review Step**: S{NN} (Final Review)
**Implementation Steps Reviewed**: S{first}..S{last}

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (see the 2026-04-22 incident in
docs/IW_AI_Core_DB_Setup.md).

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run the following alembic commands against the live
orchestration DB (port 5433) from an agent context:

```
alembic upgrade head
alembic upgrade <revision>
alembic downgrade <anything>
alembic stamp <anything>
```

Your job in a Database step is to WRITE the migration FILE. The daemon
will apply it as part of the merge pipeline (pre-merge dry-run against
a testcontainer, post-merge apply to live DB). If the migration is
broken, the daemon will refuse to merge the batch.

Allowed for agents:
  - alembic revision --autogenerate -m "..."   (writes a file only)
  - alembic history / current / show           (read-only)
  - Running migrations inside testcontainer fixtures
    (tests/conftest.py does this — agents don't call it directly)

Allowed for OPERATORS only (not agents):
  - uv run iw migrations list-pending          (read-only, safe for anyone)
  - uv run iw migrations dry-run               (testcontainer, safe)
  - uv run iw migrations apply --i-am-operator (refuses if IW_CORE_AGENT_CONTEXT=true)
  - Direct invocation via ./ai-core.sh or make db-migrate (operator entry points)

If your task seems to require applying a migration to the live DB,
STOP and raise a blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — for the current step list, status, prompt paths, gate commands, etc., prefer `uv run iw item-status {ID} --json`. The `workflow-manifest.json` file is a design-time snapshot and may be out of date (CR-00023).
- `ai-dev/work/{ID}/{ID}_{Type}_Design.md` -- Design document
- All implementation step reports: `ai-dev/work/{ID}/reports/{ID}_S*_{Agent}_report.md`
- All per-agent code review reports: `ai-dev/work/{ID}/reports/{ID}_S*_CodeReview_report.md`
- All files listed in all implementation reports' `files_changed`

## Output Files

- `ai-dev/work/{ID}/reports/{ID}_S{NN}_CodeReview_Final_report.md` -- Final review report

## Context

You are performing the **final cross-agent review** of ALL implementation work for **{Work Item Title}**.

This review looks at the complete picture -- not individual steps in isolation, but how everything fits together. Per-agent reviews have already been done; your job is to catch cross-cutting issues they could not.

Read the design document to understand the full intended scope. Read all implementation and review reports to understand what was built. Then review all changed files holistically.

## Read the Design Document FIRST

Read the design document **before** running the lint/format gate and **before** opening any changed files. Specifically:

- Read the `## Acceptance Criteria` section in full — every criterion is a mandatory check, not a suggestion.
- Read the `## TDD Approach` section in full — note every test file the design names by path.
- Write down every test file the design doc mentions; carry these expectations into the `## Review Checklist` below as a first-class anchor.
- Cross-check every test file mentioned in the design doc's TDD section against the `files_changed` arrays of ALL implementation step reports. Any test file the design names that does not appear anywhere is a **CRITICAL** finding.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Before reading any code, run these two commands on the files listed in the
implementation report's `files_changed`. Fix nothing yourself — only report.

```bash
make lint          # ruff check — catches ARG001, F811, unused imports, etc.
make format  # ruff format --check — catches formatting drift (does NOT auto-fix)
```

If either command reports NEW violations in the changed files (i.e., violations
that do not appear on the `main` branch before this step), classify each one as
a **CRITICAL** finding in your review result contract with:
- `"category": "conventions"`
- `"file"` and `"line"` from the tool output
- `"description"` quoting the exact violation code and message

If a command is unavailable (e.g., `make` not found), STOP and raise a blocker.
Do NOT skip this step or mark it as optional.

## Review Checklist

### 1. Completeness vs Design Document

- Are ALL requirements from the design document implemented?
- Are there any design document sections with no corresponding code?
- Are there any TODO comments or placeholder implementations?
- Does the implementation match the design's API contracts and data models?
- Are all test files the design doc's TDD section names by path actually present in some implementation step's `files_changed`? Missing entries are **CRITICAL**.

### 2. Cross-Agent Consistency

- Do modules built by different agents integrate correctly?
- Are shared interfaces used consistently across boundaries?
- Are naming conventions consistent across all new code?
- Are there conflicting patterns or duplicated logic between agents?

### 3. Integration Points

- Do all new modules wire together correctly?
- Are imports and dependencies correct across module boundaries?
- Do database operations compose correctly (transactions, session management)?
- Are there any circular dependencies?

### 4. Test Coverage (Holistic)

- Is there adequate integration test coverage for cross-module behavior?
- Are the happy path AND error paths covered end-to-end?
- Are there missing test scenarios that per-agent reviews wouldn't catch?
- Do tests exercise the integration points between agents' work?

### 5. Architecture Compliance

- Read `CLAUDE.md` for project-specific architecture rules.
- Does the combined implementation respect the project's layered architecture?
- Are there any new patterns introduced that conflict with existing conventions?

### 6. Security (Cross-Cutting)

- No hardcoded secrets, credentials, or API keys across any file
- Consistent authorization enforcement across all new endpoints/commands
- Input validation at all system boundaries

## Test Verification (NON-NEGOTIABLE)

Before submitting your review:

1. Run the **full test suite** (both unit AND integration tests)
2. Report test results accurately in the result contract
3. If integration tests fail, this is a CRITICAL finding

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Breaks functionality, data loss risk, security vulnerability, missing requirement | Must fix before merge |
| **HIGH** | Significant bug, integration failure, architectural violation | Must fix before merge |
| **MEDIUM (fixable)** | Code quality issue, missing edge case, convention violation | Should fix in fix cycle |
| **MEDIUM (suggestion)** | Design improvement, better pattern available | Optional, author decides |
| **LOW** | Nitpick, style preference, minor readability | Informational only |

## Review Result Contract

```json
{
  "step": "S{NN}",
  "agent": "CodeReview_Final",
  "work_item": "{ID}",
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

- `verdict`: Use `pass` if there are zero CRITICAL or HIGH findings AND zero MEDIUM (fixable) findings. Use `fail` if any mandatory fixes are needed.
- `mandatory_fix_count`: Count of CRITICAL + HIGH + MEDIUM (fixable) findings.
- `missing_requirements`: List any design document requirements that have no corresponding implementation. Each missing requirement is automatically a CRITICAL finding.
- `cross_cutting`: Set to `true` on findings that span multiple agents' work or affect integration points.
