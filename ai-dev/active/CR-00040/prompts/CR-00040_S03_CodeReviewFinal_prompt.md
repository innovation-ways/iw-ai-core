# CR-00040_S03_CodeReview_Final_prompt

**Work Item**: CR-00040 -- CodeReview Templates — Anchor Reviewers to Design Doc Before Code Inspection
**Review Step**: S03 (Final Review)
**Implementation Steps Reviewed**: S01..S01 (single implementation step)

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state.

Allowed exceptions: testcontainers (pytest fixtures), read-only `docker ps`/`inspect`/`logs`, and `./ai-core.sh` / `make` targets.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This step is a final review. You generate no migration and run no alembic command.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — for the current step list, status, prompt paths, gate commands, etc., prefer `uv run iw item-status CR-00040 --json`.
- `ai-dev/work/CR-00040/CR-00040_CR_Design.md` -- Design document (AC1–AC5)
- `ai-dev/work/CR-00040/reports/CR-00040_S01_Template_report.md` -- S01 implementation report
- `ai-dev/work/CR-00040/reports/CR-00040_S02_CodeReview_report.md` -- S02 per-step review
- All files listed in S01's `files_changed`

## Output Files

- `ai-dev/work/CR-00040/reports/CR-00040_S03_CodeReview_Final_report.md` -- Final review report

## Context

You are performing the **final cross-agent review** of ALL implementation work for **CR-00040**.

This CR has only one implementation step (S01) and one per-step review (S02), so the "cross-agent" surface is small. Your job is to (a) verify nothing fell through the cracks between S02's review and the final state of the worktree, (b) confirm consistency between the two CodeReview templates (master and Final variants must use the same `## Read the Design Document FIRST` heading and parallel structure), and (c) trace each acceptance criterion (AC1–AC5) end-to-end against the actual files.

Read the design document FIRST. Then read S01 and S02 reports. Then read all four edited files top-to-bottom.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

Markdown files are not exercised by ruff; both should pass cleanly. NEW violations attributable to this work item = CRITICAL under `"category": "conventions"`.

If a command is unavailable, STOP and raise a blocker.

## Review Checklist

### 1. Completeness vs Design Document

- AC1: `templates/design/CodeReview_Prompt_Template.md` contains `## Read the Design Document FIRST` placed BEFORE `## Pre-Review Lint & Format Gate`. ✓ / ✗
- AC2: `templates/design/CodeReview_Final_Prompt_Template.md` contains the same heading in the same position, with the test-file-cross-check closing line. ✓ / ✗
- AC3: existing review checklists augmented with the design-doc anchor bullets in both files. ✓ / ✗
- AC4: per-project mirrors are byte-identical to masters (run `diff -u` for both pairs). ✓ / ✗
- AC5: existing banner sections, lint/format gate, severity levels, and result contract preserved verbatim. ✓ / ✗

Any AC not satisfied is automatically a CRITICAL finding under `category: architecture`.

### 2. Cross-Agent Consistency

- The two templates serve sibling roles (per-step review vs final review). Their new `## Read the Design Document FIRST` sections should be **structurally parallel**: same heading, same number of bullets (or close to it), same opening sentence shape, but with closing lines that reflect each template's job. Verify this — drift between the two would re-introduce the very confusion this CR is fixing.
- Naming consistency: the heading must be exactly `## Read the Design Document FIRST` in both files (case, spacing, no decorations). Anything else is HIGH.

### 3. Integration Points

- The change integrates with the existing `iw sync-templates` flow. Verify S01 actually invoked it (S01 report should record the command output) and verify the per-project mirrors really were updated:
  ```bash
  diff -u templates/design/CodeReview_Prompt_Template.md ai-dev/templates/CodeReview_Prompt_Template.md
  diff -u templates/design/CodeReview_Final_Prompt_Template.md ai-dev/templates/CodeReview_Final_Prompt_Template.md
  ```
  Both must be empty. Non-empty = CRITICAL (sync drift).

### 4. Scope Compliance

- Run `git diff --name-only main...HEAD` against the worktree branch.
- The only files modified outside `ai-dev/active/CR-00040/**` should be the four declared in `scope.allowed_paths`. Any other file = CRITICAL (out-of-scope edit; would also be blocked by the merge-time scope gate).

### 5. Regression Check

- This CR changes only markdown prompt content. Confirm no executable code paths are touched. Verify with:
  ```bash
  git diff main...HEAD -- '*.py' '*.html' '*.js' '*.css' '*.toml' '*.json' | head
  ```
  (Note: `workflow-manifest.json` and the `prompts/*.md` under `ai-dev/active/CR-00040/` are expected; nothing outside that.)

## Test Verification (NON-NEGOTIABLE)

```bash
make test-unit
```

This step changes no Python, so the suite must pass with the same green it had before S01. Any new failure = CRITICAL.

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | AC violation, sync drift, out-of-scope edit, banner mutation, regression | Must fix before merge |
| **HIGH** | Heading drift between the two templates, missing bullet, structural inconsistency | Must fix before merge |
| **MEDIUM (fixable)** | Minor wording drift, missing trailing line, soft inconsistency | Should fix in fix cycle |
| **MEDIUM (suggestion)** | Phrasing improvement | Optional |
| **LOW** | Whitespace/formatting nit | Informational only |

## Review Result Contract

```json
{
  "step": "S03",
  "agent": "code-review-final-impl",
  "work_item": "CR-00040",
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
  "missing_requirements": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": "AC1–AC5 trace results, both diff -u outputs, scope-compliance verdict."
}
```

- `missing_requirements`: list any of AC1–AC5 not satisfied. Each entry is automatically CRITICAL.
- `verdict`: `pass` only if zero CRITICAL/HIGH/MEDIUM_FIXABLE findings AND `missing_requirements` is empty.
