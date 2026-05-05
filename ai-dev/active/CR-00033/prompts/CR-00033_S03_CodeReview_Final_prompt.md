# CR-00033_S03_CodeReview_Final_prompt

**Work Item**: CR-00033 -- Document Tailwind CLI Fallback Strategy in Tech Stack Docs
**Step**: S03
**Agent**: code-review-final-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

Allowed exceptions: testcontainers, read-only `docker ps/inspect/logs`, and
`./ai-core.sh`/`make` targets.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This item makes no migrations. Standard agent-context restrictions apply.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00033 --json`.
- `ai-dev/active/CR-00033/CR-00033_CR_Design.md` — Design document.
- `ai-dev/active/CR-00033/CR-00033_Functional.md` — Functional summary.
- `ai-dev/active/CR-00033/reports/CR-00033_S01_BackendImpl_report.md` — S01 report.
- `ai-dev/active/CR-00033/reports/CR-00033_S02_CodeReview_report.md` — S02 review.
- `git diff main..HEAD -- docs/IW_AI_Core_Tech_Stack.md` — Net change.

## Output Files

- `ai-dev/active/CR-00033/reports/CR-00033_S03_CodeReview_Final_report.md` — Final review report.

## Context

You are running the **global cross-agent review** for CR-00033. This is a
documentation-only CR with a single implementation step (S01) and one per-agent
review (S02). The review here verifies that the change as a whole — diff +
design doc + functional doc — composes into a complete, mergeable change.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

Any new violations in `files_changed` from any prior step = CRITICAL finding.

## Review Focus

### 1. Diff completeness vs. design

Open `git diff main..HEAD` and walk through it once. Confirm:

- Exactly one source file is modified: `docs/IW_AI_Core_Tech_Stack.md`.
  Anything else is CRITICAL (scope violation per `allowed_paths`).
- All five Acceptance Criteria (AC1–AC5) are visibly satisfied in the diff.
  Missing AC = HIGH.

### 2. Functional doc consistency

Re-read `CR-00033_Functional.md` and confirm:

- It still describes the change accurately after the implementation. If the
  S01 implementer made wording choices that contradict the functional doc,
  that is HIGH and must be reconciled before merge (either by amending the
  functional doc or by amending the implementation).
- The functional doc body is ≤500 words and contains no file paths,
  class names, or fenced code blocks. (The review skill blocks otherwise.)

### 3. Internal consistency of the edited file

Read the affected sections of `docs/IW_AI_Core_Tech_Stack.md` end-to-end:

- §2.4 Dashboard (especially the new "Tailwind CLI fallback strategy" subsection).
- §6 Makefile (do not edit, but confirm the surrounding doc does not contradict
  the new claims about `make css`).
- §10 Decisions Log (the updated/new row).

Any contradiction across these three sections = HIGH.

### 4. No regression in surrounding doc

Quickly re-read §2.4 Dashboard from the start. The pre-existing duplicate
`### 2.4. Compression` heading is a known issue and is NOT in scope — do
not flag it. But verify the CR did not introduce a NEW duplicate or break
the heading hierarchy.

### 5. Test suite

Run:

```bash
make test-unit
make test-integration
```

Both must pass. Failures here would indicate a non-doc edit leaked in.

## Verdict

The verdict is `pass` only if all of the following hold:

- Exactly one source file modified.
- All AC1–AC5 satisfied in the diff.
- Functional doc and design doc remain consistent with the implementation.
- No new lint/format/test failures.
- No internal contradictions in the edited file.

Otherwise: `fail`, with each issue tagged at the appropriate severity.

## Final Review Result Contract

```json
{
  "step": "S03",
  "agent": "code-review-final-impl",
  "work_item": "CR-00033",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "docs/IW_AI_Core_Tech_Stack.md",
      "line": 0,
      "description": "...",
      "suggestion": "..."
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
