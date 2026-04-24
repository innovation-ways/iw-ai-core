# F-00059 S03 — Template & Skill Updates

## What Was Done

1. **New `Functional_Design_Template.md`** created at two paths:
   - `ai-dev/templates/Functional_Design_Template.md` (canonical master)
   - `templates/design/Functional_Design_Template.md` (sync mirror)

   Structure: H1 title, HTML comment with author guidance, then `## Why`, `## What Changed (for the User)`, `## How It Behaves`, `## Out of Scope` — matching the spec exactly. No implementation detail, no code fences, no path references.

2. **`skills/iw-new-feature/SKILL.md`** updated:
   - Added "Also create the **Functional Design Document**" substep inside Step 5 (Create Design Document)
   - Instructions to copy `Functional_Design_Template.md` → `{ID}_Functional.md` and fill all four sections
   - Rules: ≤500 words, plain English only, no file paths/class names/SQL/code fences, no path fragments like `orch/` or `dashboard/`
   - Added `{ID}_Functional.md` row to the File Manifest table
   - Added **Agent Selection** table (was missing after the manifest rewrite)
   - Added note in Step 8 (Register in Platform): `iw register` auto-detects the sibling `<ID>_Functional.md` — no extra flag needed (S02's work)

3. **`skills/iw-new-incident/SKILL.md`** updated:
   - Same functional doc creation substep in Step 4 (Create Design Document)
   - Same rules and source-template instruction
   - Added functional doc row to File Manifest table
   - Added register-time auto-detection note to Step 6 (Register in Platform)

4. **`skills/iw-new-cr/SKILL.md`** updated:
   - Same functional doc creation substep in Step 5 (Create Design Document)
   - Same rules and source-template instruction
   - Added functional doc row to File Manifest table
   - Added register-time auto-detection note to Step 8 (Register in Platform)

5. **`skills/iw-review-design/SKILL.md`** updated:
   - New section `### Functional Design Document Checks` inserted after CR-Specific Checks and before `## Step 3`
   - **Structural Checks (BLOCKING)**:
     - File `{ID}_Functional.md` exists
     - H1 `# {ID} — Functional Design` (or en-dash variant)
     - H2 `## Why`, `## What Changed (for the User)`, `## How It Behaves`
     - Word count ≤ 500 (prose body excluding HTML comment and headings)
   - **Content Checks (WARNING)**:
     - File-extension regex, path-fragment regex, SQL-DDL regex, fenced code blocks
     - Block on structural failures; report-but-not-block on content warnings unless reviewer explicitly dismisses
   - Clear explanation of the blocking-vs-warning distinction

## Files Changed

| File | Change |
|------|--------|
| `ai-dev/templates/Functional_Design_Template.md` | **NEW** |
| `templates/design/Functional_Design_Template.md` | **NEW** |
| `skills/iw-new-feature/SKILL.md` | Modified — functional doc substep in Step 5, manifest row, register note |
| `skills/iw-new-incident/SKILL.md` | Modified — functional doc substep in Step 4, manifest row, register note |
| `skills/iw-new-cr/SKILL.md` | Modified — functional doc substep in Step 5, manifest row, register note |
| `skills/iw-review-design/SKILL.md` | Modified — `### Functional Design Document Checks` section added |

## Static Grep Checks (TDD Requirement)

```
$ grep '## Why' ai-dev/templates/Functional_Design_Template.md
## Why

$ grep 'Functional_Design_Template' skills/iw-new-feature/SKILL.md
Copy `ai-dev/templates/Functional_Design_Template.md` and fill in the four sections using:

$ grep 'Functional_Design_Template' skills/iw-new-incident/SKILL.md
Copy `ai-dev/templates/Functional_Design_Template.md` and fill in the four sections using:

$ grep 'Functional_Design_Template' skills/iw-new-cr/SKILL.md
Copy `ai-dev/templates/Functional_Design_Template.md` and fill in the four sections using:

$ grep 'functional doc' skills/iw-review-design/SKILL.md
The functional doc (`ai-dev/active/{ID}/{ID}_Functional.md`) is the human-facing
```

All greps pass.

## Test Results

### `make test-unit`
```
====================== 1337 passed, 19 warnings in 14.96s ======================
```
All 1337 tests pass. No regressions introduced by this step.

### `make lint`
Lint errors are in pre-existing files (`tests/integration/test_oss_dashboard_templates_extras.py`) unrelated to this step's changes. The lint failures are PT018 assertions needing to be split — none are in the files modified by S03.

```
Found 8 errors (5 fixable with --fix)
```

None of these are in the new or modified files from S03. The lint errors existed before this step.

## Skills Sync Note (AC7)

After this step merges, an operator must run `iw skills sync` for every project in `projects.toml`:
- **innoforge**
- **iw-ai-core** (iw-ai-core is itself a managed project — its own `.claude/skills/` must be synced, do not skip)
- **cv**

This is not automated by the pipeline — it is a manual operator step, documented in AC7 of the F-00059 Feature Design.