# CR-00033_S02_CodeReview_prompt

**Work Item**: CR-00033 -- Document Tailwind CLI Fallback Strategy in Tech Stack Docs
**Step Being Reviewed**: S01 (backend-impl)
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

Allowed exceptions: testcontainers, read-only `docker ps/inspect/logs`, and
`./ai-core.sh`/`make` targets.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This item makes no migrations. Standard agent-context restrictions apply.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00033 --json` (authoritative).
- `ai-dev/active/CR-00033/CR-00033_CR_Design.md` — Design document, especially the Acceptance Criteria.
- `ai-dev/active/CR-00033/reports/CR-00033_S01_BackendImpl_report.md` — Implementation report.
- `docs/IW_AI_Core_Tech_Stack.md` — Reviewed file (use `git diff` to see the change).
- `Makefile` — Verify the `css`-target claims in the new prose.
- `dashboard/static/styles.css`, `dashboard/static/tailwind.src.css`, `dashboard/tailwind.config.js` — Verify file-name claims in the new prose.
- `ai-dev/active/I-00067/reports/I-00067_self_assess_report.md` — Verify I-00067 evidence citations.

## Output Files

- `ai-dev/active/CR-00033/reports/CR-00033_S02_CodeReview_report.md` — Review report.

## Context

You are reviewing a documentation-only edit that adds a Tailwind CLI fallback
strategy subsection to `docs/IW_AI_Core_Tech_Stack.md` and lightly updates two
existing locations (the "Why Tailwind CSS via CDN" prose and §10 Decisions Log).

This review's job is to catch:

1. **Factual errors** in the new prose (file names, target behavior, citations).
2. **Acceptance-criteria misses** (AC1–AC5 in the design doc).
3. **Markdown breakage** (tables, headings, anchors).
4. **Scope creep** (any file other than `docs/IW_AI_Core_Tech_Stack.md` modified).

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Run these before reading the diff. Fix nothing yourself — only report.

```bash
make lint
make format-check
```

If either tool reports NEW violations in `files_changed`, classify each as a
**CRITICAL** finding with `category: "conventions"` and quote the exact tool
output. Markdown is not Python-linted, so genuine new lint errors here would
indicate the implementer touched a non-doc file — flag this aggressively.

## Review Checklist

### 1. Scope

- Verify exactly one file changed: `docs/IW_AI_Core_Tech_Stack.md`. Any other
  file appearing in `git diff` is a CRITICAL finding (violates AC5 and the
  scope `allowed_paths`).

### 2. Factual accuracy

- The new subsection states `make css` is `.PHONY` with no rule body. Open
  the `Makefile` and confirm. (Today: line ~8 declares `css` in `.PHONY`,
  no rule body exists.) If the Makefile has changed since this CR was drafted
  and `make css` now does something, file a CRITICAL finding — the doc would
  ship a false claim.
- The new subsection references `dashboard/static/styles.css`,
  `dashboard/static/tailwind.src.css`, and `dashboard/tailwind.config.js`.
  Confirm each path exists. Missing paths = CRITICAL.
- The I-00067 citation must reference the work item ID (not internal log
  paths from the worktree). Internal `.worktrees/...` paths in the doc =
  HIGH (will rot quickly and leak run state into committed docs).

### 3. Acceptance criteria (AC1–AC5)

Walk each AC in the design doc and verify:

- **AC1**: New subsection titled exactly "Tailwind CLI fallback strategy" with all 6 required content elements present.
- **AC2**: The line-95 sentence no longer implies CLI compilation is the production path.
- **AC3**: §10 Decisions Log mentions the fallback (either as an extended Notes cell on the existing row or as a new adjacent row).
- **AC4**: Cross-reference §2.4 Dashboard, §6 Makefile, §10 Decisions Log — they must not contradict each other.
- **AC5**: Only one file modified.

Each missed AC is a HIGH finding minimum.

### 4. Doc craft

- Tone matches the rest of `docs/IW_AI_Core_Tech_Stack.md` (concise,
  decisions-with-rationale, no marketing prose, no emoji).
- No fenced code blocks for narrative content. (One short code block to show
  the rule is acceptable, not required.)
- Heading level is `###` (subsection of §2.4), not `##`.
- Total subsection length is ~150–250 words. Significantly outside that band
  is MEDIUM (suggestion).
- No accidental Markdown breakage: pipe-aligned tables still parse, no
  duplicated heading numbers introduced (the pre-existing duplicate
  `### 2.4. Compression` is NOT in scope; do NOT flag it).

### 5. Project conventions (CLAUDE.md)

Read `CLAUDE.md` for any documentation conventions. The Quick Navigation table
should still resolve correctly after the edit.

## Test Verification

Run `make test-unit` and confirm no regressions. Markdown should not affect any
test; a failure here would indicate a non-doc edit slipped in.

## Severity Levels

| Severity | Meaning |
|----------|---------|
| CRITICAL | Wrong file modified, false factual claim, broken Markdown table, missing AC |
| HIGH | Citation rot risk, missed AC element, internal contradiction with §6/§10 |
| MEDIUM (fixable) | Length way outside band, tone drift, weak rationale |
| MEDIUM (suggestion) | Wording polish, layout preference |
| LOW | Nitpick |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "CR-00033",
  "step_reviewed": "S01",
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

`verdict`: `pass` only if zero CRITICAL/HIGH/MEDIUM_FIXABLE findings.
