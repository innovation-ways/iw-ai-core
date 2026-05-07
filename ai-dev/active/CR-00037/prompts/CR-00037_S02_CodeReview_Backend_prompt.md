# CR-00037_S02_CodeReview_Backend_prompt

**Work Item**: CR-00037 — Add vendored-library API verification rule to frontend-impl agent
**Step Being Reviewed**: S01 (backend-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits

Standard policy. Read the full text in any sibling implementation prompt. Do not run any docker mutating command.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This CR does not touch alembic. If you find yourself reaching for any `alembic upgrade/downgrade/stamp` command, STOP — something is wrong.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00037 --json`.
- `ai-dev/active/CR-00037/CR-00037_CR_Design.md` — the design you are reviewing against (especially the **Acceptance Criteria** AC1..AC4).
- `ai-dev/active/CR-00037/reports/CR-00037_S01_Backend_report.md` — implementation report from S01.
- The two files modified by S01:
  - `agents/claude/frontend-impl.md`
  - `agents/opencode/frontend-impl.md`

## Output Files

- `ai-dev/active/CR-00037/reports/CR-00037_S02_CodeReview_report.md` — review report.

## Context

You are reviewing the work done in S01 (backend-impl) for CR-00037. The CR is documentation-only: two markdown files (the master copies of the `frontend-impl` agent definition for Claude and OpenCode) edited to add a single new "Verify vendored / third-party library APIs" step in their Required Workflow. There is no Python, no template, no DB, no UI. Your review is therefore tightly scoped — verify the four acceptance criteria are met, the two files agree substantively, and nothing else was touched (in particular, nothing under `.claude/agents/` or `.opencode/agents/`).

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Run:

```bash
make lint
make format-check
```

The S01 step modified no `.py` file. Both commands should report no new violations attributable to S01. If either does, classify as a CRITICAL finding with `category: conventions`. If a command is unavailable, STOP and raise a blocker. Do NOT run `make format` (which writes); use `make format-check` (read-only) so you can faithfully report the on-disk state.

## Review Checklist

### 1. Acceptance Criteria Coverage

Verify each acceptance criterion from `CR-00037_CR_Design.md` is met by reading both modified files end-to-end:

- **AC1**: Both `agents/claude/frontend-impl.md` and `agents/opencode/frontend-impl.md` contain a numbered step in the `## Required Workflow` section that includes ALL of: (a) the words "vendored" and ("third-party" or "third party"), (b) an explicit grep / `.d.ts` / DevTools verification instruction, (c) a one-sentence reference to **F-00079 self-assess Finding 1** as the motivating incident. Verify with: `grep -n "F-00079" agents/claude/frontend-impl.md agents/opencode/frontend-impl.md` and `grep -n "vendored" agents/claude/frontend-impl.md agents/opencode/frontend-impl.md`. The wording in the two files must be substantively identical (small dialect differences acceptable).
- **AC2**: Run `grep -n "Diff2HtmlUI\.create(" agents/claude/frontend-impl.md agents/opencode/frontend-impl.md`. Matches MUST appear ONLY in the negative-form mention (the historical-incident sentence, where it is cited as the wrong call). The files MUST NOT recommend any `.create(` factory form as a default. A literal recommendation of `.create(` outside the historical-incident sentence is a CRITICAL finding.
- **AC3**: Confirm the diff did NOT touch any file under `.claude/agents/` or `.opencode/agents/`. Run: `git diff --name-only main...HEAD -- '.claude/agents/' '.opencode/agents/'`. Output MUST be empty. Any match is a CRITICAL finding (sync surfaces must not be hand-edited).
- **AC4**: The diff for each of the two master files consists of exactly one inserted numbered list item plus any renumbering of subsequent items. Confirm by inspecting `git diff main...HEAD -- agents/claude/frontend-impl.md agents/opencode/frontend-impl.md`. No frontmatter field, no Mission line, no Safety Constraint, no Output Format detail, no other section may be altered. Any other section touched is a CRITICAL finding. Any other agent-definition file (e.g., `agents/claude/backend-impl.md`) touched is a CRITICAL finding.

### 2. Scope Compliance

The manifest's `scope.allowed_paths` lists exactly:

- `agents/claude/frontend-impl.md`
- `agents/opencode/frontend-impl.md`

The implementation report's `files_changed` MUST list only those two paths (plus possibly the S01 report itself, which is implicitly allowed under `ai-dev/active/CR-00037/`). Any other file changed is a CRITICAL finding.

### 3. Markdown Quality

- The new step respects the file's existing heading depth, bullet style, bolded-lead-in convention, and code-span markup.
- Numbered list contiguity — no gaps or duplicates after the renumbering.
- No broken markdown syntax (unclosed fences, broken links, stray HTML).
- No emojis introduced (the existing frontend-impl files contain none).

### 4. Cross-File Consistency

Diff the new step body between the Claude and OpenCode copies. Differences should be limited to dialect or trivial whitespace. The rule, the listed verification methods, and the F-00079 motivation sentence MUST be the same. Any substantive divergence (different motivation, different verification methods, missing element in one file) is a HIGH finding.

### 5. Project Conventions

Read `CLAUDE.md`. The relevant rules for this CR are general (no playwright-cli misuse, no docker, no live-DB tests). None of them should be violated by a markdown edit; flag any cross-cutting violation you find as appropriate severity.

### 6. Sync-pipeline Hygiene

- The implementation MUST NOT have run `iw sync-agents` (which would propagate the change to `.claude/agents/` / `.opencode/agents/` and bust scope). Confirm by reading the S01 report's notes and by running the `git diff` check from AC3.
- The YAML frontmatter of both files MUST be byte-identical to `main` (no fields added, removed, reordered, or whitespace-shifted). Spot-check by running `git diff main...HEAD -- agents/claude/frontend-impl.md agents/opencode/frontend-impl.md | head -40` and confirming no frontmatter line appears.

### 7. Testing

Not applicable — no code path. The S01 report should declare `tests_passed: true` with `test_summary: "skipped: no code changes"`. Anything else is a finding.

## Test Verification (NON-NEGOTIABLE)

Run the project's unit test command (`make test-unit`) to confirm S01 introduced no incidental breakage. Expected: pass with no diffs from `main`. Report results faithfully in the result contract.

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| CRITICAL | Acceptance criterion not met; scope violation; broken markdown; non-allowed file modified; sync surface edited | Must fix before merge |
| HIGH | Substantive divergence between Claude and OpenCode copies; missing F-00079 reference; missing one of the five required elements of the new step | Must fix before merge |
| MEDIUM (fixable) | Minor wording issues, awkward placement within Required Workflow, inconsistent style with rest of file | Should fix in fix cycle |
| MEDIUM (suggestion) | Better phrasing available | Optional |
| LOW | Nitpick | Informational only |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "CR-00037",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "agents/claude/frontend-impl.md",
      "line": 0,
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
