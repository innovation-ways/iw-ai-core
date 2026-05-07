# CR-00037_S03_CodeReview_Final_prompt

**Work Item**: CR-00037 — Add vendored-library API verification rule to frontend-impl agent
**Review Step**: S03 (Final Review)
**Implementation Steps Reviewed**: S01

---

## ⛔ Docker is off-limits

Standard policy. Read the full text in any sibling implementation prompt. Do not run any docker mutating command.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This CR does not touch alembic.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00037 --json`.
- `ai-dev/active/CR-00037/CR-00037_CR_Design.md` — full design and acceptance criteria.
- All implementation reports: `ai-dev/active/CR-00037/reports/CR-00037_S01_Backend_report.md`.
- All per-agent code review reports: `ai-dev/active/CR-00037/reports/CR-00037_S02_CodeReview_report.md`.
- The two files modified by S01:
  - `agents/claude/frontend-impl.md`
  - `agents/opencode/frontend-impl.md`

## Output Files

- `ai-dev/active/CR-00037/reports/CR-00037_S03_CodeReview_Final_report.md` — final review report.

## Context

You are performing the **final cross-agent review** of CR-00037. This CR has only a single implementation step (S01) and a single per-agent review (S02), because the change is a markdown-only edit to two agent-definition files. The "cross-agent" framing is therefore mostly trivial — there is no integration surface to assess. Your job in this case is to:

1. Confirm the design's acceptance criteria are all satisfied by reading both modified files end-to-end (do not rely on S02's word).
2. Confirm scope compliance (no path outside `scope.allowed_paths` was touched, in particular nothing under `.claude/agents/` or `.opencode/agents/`).
3. Confirm cross-file consistency between the Claude and OpenCode masters.
4. Confirm no incidental breakage to the wider repo (lint, tests).

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Run:

```bash
make lint
make format-check
```

S01 modified no `.py` file. Both commands should be clean. If either reports new violations attributable to this CR, classify as CRITICAL with `category: conventions`. If a command is unavailable, STOP and raise a blocker. Do NOT run `make format` (which writes); use `make format-check` (read-only).

## Review Checklist

### 1. Completeness vs Design Document

For each AC1..AC4 in `CR-00037_CR_Design.md`, perform an independent read of both modified files and confirm:

- **AC1**: Both `agents/claude/frontend-impl.md` and `agents/opencode/frontend-impl.md` carry a numbered Required-Workflow step containing all five required elements (vendored / third-party scope words; explicit verification instruction with grep / `.d.ts` / DevTools; slim-vs-full surface caveat; F-00079 self-assess Finding 1 reference). Verify with: `grep -n "F-00079\|vendored\|third-party\|third party" agents/claude/frontend-impl.md agents/opencode/frontend-impl.md`.
- **AC2**: Run `grep -n "Diff2HtmlUI\.create(" agents/claude/frontend-impl.md agents/opencode/frontend-impl.md`. Negative-form mentions inside the historical-incident clause are acceptable; any recommendation of a `.create(` factory shape as a default is CRITICAL.
- **AC3**: No file under `.claude/agents/` or `.opencode/agents/` is in the diff against `main`. Verify: `git diff --name-only main...HEAD -- '.claude/agents/' '.opencode/agents/'` MUST be empty.
- **AC4**: The diff against `main` for each of the two master files is confined to one new numbered list item and any contiguous renumbering. Any other section, frontmatter field, Mission line, Safety Constraint, or other agent-definition file altered is a CRITICAL finding.

Each unmet acceptance criterion is automatically a CRITICAL finding (record it in `missing_requirements`).

### 2. Cross-Agent Consistency

Trivially satisfied at the agent-execution level — only one implementation agent ran. **However, do verify cross-file consistency between the two master copies**: the new step body in `agents/claude/frontend-impl.md` and `agents/opencode/frontend-impl.md` MUST be substantively identical (same rule, same verification methods, same motivation sentence). Substantive divergence is a HIGH finding.

### 3. Integration Points

Trivially satisfied at runtime — markdown-only change with no integration surface. The only "integration" concern is `iw sync-agents`: confirm the implementation did NOT run it (S01 prompt forbids it; running it would have edited `.claude/agents/` and `.opencode/agents/` and busted AC3).

### 4. Test Coverage (Holistic)

Not applicable — no code path. Confirm `tests_passed: true` with skip rationale across S01 and S02 reports.

### 5. Architecture Compliance

Read `CLAUDE.md`. None of its hard rules should be implicated by a markdown edit. Flag anything cross-cutting you find.

### 6. Scope Compliance (Cross-Cutting)

The manifest's `scope.allowed_paths` is exactly:

- `agents/claude/frontend-impl.md`
- `agents/opencode/frontend-impl.md`

Run `git diff --name-only main...HEAD` (or the equivalent against the merge base) and confirm only those two paths plus `ai-dev/active/CR-00037/**` are in the diff. Any other path is a CRITICAL finding.

### 7. Security (Cross-Cutting)

Not applicable — no secrets, no auth, no input handling. Trivially clean.

## Test Verification (NON-NEGOTIABLE)

Run the **full test suite**:

```bash
make test-unit
make test-integration
```

Expected: pass with no diffs from `main` other than the two markdown edits. Report results in the contract. If integration tests fail, that is CRITICAL — but in this CR they should not, because no Python is touched.

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| CRITICAL | AC unmet; scope violation; broken markdown; sync surface edited; test regression | Must fix before merge |
| HIGH | Substantive divergence between Claude and OpenCode copies; missing F-00079 reference; missing one of the five required elements | Must fix before merge |
| MEDIUM (fixable) | Wording or placement issues | Should fix in fix cycle |
| MEDIUM (suggestion) | Better phrasing available | Optional |
| LOW | Nitpick | Informational only |

## Review Result Contract

```json
{
  "step": "S03",
  "agent": "CodeReview_Final",
  "work_item": "CR-00037",
  "steps_reviewed": ["S01"],
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "completeness|consistency|integration|testing|architecture|security",
      "file": "agents/claude/frontend-impl.md",
      "line": 0,
      "description": "What the issue is",
      "suggestion": "How to fix it",
      "cross_cutting": false
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```
