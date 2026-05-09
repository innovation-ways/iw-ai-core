# CR-00040_S02_CodeReview_prompt

**Work Item**: CR-00040 -- CodeReview Templates — Anchor Reviewers to Design Doc Before Code Inspection
**Step Being Reviewed**: S01 (template-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

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

This step is a code review only. You generate no migration and run no
alembic command.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — for the current step list, status, prompt paths, gate commands, etc., prefer `uv run iw item-status CR-00040 --json`.
- `ai-dev/work/CR-00040/CR-00040_CR_Design.md` -- Design document — read AC1–AC5 carefully; they are the contract S01 must satisfy.
- `ai-dev/work/CR-00040/reports/CR-00040_S01_Template_report.md` -- S01 implementation report
- All files listed in S01's `files_changed`:
  - `templates/design/CodeReview_Prompt_Template.md`
  - `templates/design/CodeReview_Final_Prompt_Template.md`
  - `ai-dev/templates/CodeReview_Prompt_Template.md`
  - `ai-dev/templates/CodeReview_Final_Prompt_Template.md`

## Output Files

- `ai-dev/work/CR-00040/reports/CR-00040_S02_CodeReview_report.md` -- Review report

## Context

You are reviewing the implementation work done in step S01 by `template-impl` for **CR-00040**.

Read the design document FIRST. The CR's whole point is that this anchoring step is non-negotiable. Then read the S01 report. Then read all four edited template files. Then trace AC1–AC5 against the file contents.

This CR is self-referential: the design doc you are now reading describes the very change you are reviewing. Use that to your advantage — the design doc's Acceptance Criteria are extremely concrete (exact heading text, exact placement) and lend themselves to mechanical verification.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Before reading any code, run these two commands on the files listed in the implementation report's `files_changed`. Fix nothing yourself — only report.

```bash
make lint          # ruff check
make format-check  # ruff format --check
```

Markdown files are not exercised by ruff, so both commands should pass with no NEW violations attributable to S01. If either reports NEW violations in any file (markdown or otherwise) attributable to S01, classify as a CRITICAL finding under `"category": "conventions"`.

If a command is unavailable (e.g., `make` not found), STOP and raise a blocker.

## Review Checklist

### 1. Architecture Compliance

- Is the new `## Read the Design Document FIRST` section placed BETWEEN the existing `## Context` section and the existing `## Pre-Review Lint & Format Gate` section? (AC1, AC2)
- Are the existing `## ⛔ Docker is off-limits` and `## ⛔ Migrations: agents generate, daemon applies` sections preserved byte-for-byte? (AC5)
- Is the existing `## Severity Levels` table unchanged?
- Is the existing `## Review Result Contract` JSON schema unchanged?

### 2. Code Quality (i.e., prompt copy quality)

- Is the new section's heading exactly `## Read the Design Document FIRST`? Wording matters — both AC1 and AC2 require this exact phrasing.
- Are the bullets imperative ("Read X", "Note Y") and short, or do they devolve into prose? Imperative + short is the design intent.
- Does the section open with one sentence that explicitly states the timing constraint ("BEFORE running lint/format AND BEFORE opening any changed files")?
- Is the closing CRITICAL-finding consequence line present, and does its wording match the design's intent (CodeReview vs CodeReview_Final variants differ — verify the right wording is in the right file)?

### 3. Project Conventions

- Read `CLAUDE.md`. Were `templates/design/` master copies edited AND were the per-project mirrors under `ai-dev/templates/` updated by `iw sync-templates`?
- Run these two diffs and verify both are empty (AC4):
  ```bash
  diff -u templates/design/CodeReview_Prompt_Template.md ai-dev/templates/CodeReview_Prompt_Template.md
  diff -u templates/design/CodeReview_Final_Prompt_Template.md ai-dev/templates/CodeReview_Final_Prompt_Template.md
  ```
  Either diff non-empty = CRITICAL finding (sync drift, exactly what this CR is meant to prevent).
- Was any file outside `scope.allowed_paths` modified? Run `git diff --name-only main...HEAD` against the worktree branch and verify only the four allowed files (plus implicit `ai-dev/active/CR-00040/**`) appear. Out-of-scope edits = CRITICAL finding.

### 4. Security

N/A for prompt-template edits. There are no secrets, no input handling, no auth surfaces.

### 5. Testing

- Was the new "Do test files cover the assertions the design doc's TDD section calls out by name?" bullet appended under `### 5. Testing` in `CodeReview_Prompt_Template.md`? (AC3, first half)
- Was the new "test files named in design doc TDD section must appear in `files_changed`" bullet appended under `### 1. Completeness vs Design Document` in `CodeReview_Final_Prompt_Template.md`? (AC3, second half)
- Are vacuous Python tests asserting markdown contents being added? They MUST NOT be. (See design Notes.) If S01 added any such test, that is a MEDIUM_FIXABLE finding under `category: testing`.

## Test Verification (NON-NEGOTIABLE)

Run the project's unit test command to verify no regressions:

```bash
make test-unit
```

This step changes no Python, so the suite must pass with the same green it had before S01. Any new failure = CRITICAL.

## Severity Levels

Classify each finding with one of these severities:

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Breaks AC, sync drift, out-of-scope edit, banner mutation | Must fix before merge |
| **HIGH** | Significant copy quality issue (heading wrong, placement wrong, missing bullet) | Must fix before merge |
| **MEDIUM (fixable)** | Minor wording drift, vacuous tests added, missing closing line | Should fix in fix cycle |
| **MEDIUM (suggestion)** | Phrasing improvement | Optional |
| **LOW** | Whitespace/formatting nit | Informational only |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "CR-00040",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "path/to/file.md",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": "AC1–AC5 trace summarized here, including diff -u results."
}
```

- `verdict`: `pass` only if zero CRITICAL/HIGH/MEDIUM_FIXABLE findings.
- `mandatory_fix_count`: count of CRITICAL + HIGH + MEDIUM_FIXABLE.
- `notes`: summarize your AC1–AC5 trace and the result of both `diff -u` invocations.
