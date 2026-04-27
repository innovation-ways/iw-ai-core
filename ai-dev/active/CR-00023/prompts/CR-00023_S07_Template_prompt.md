# CR-00023_S07_Template_prompt

**Work Item**: CR-00023 — Make iw item-status the runtime source of truth for step list and per-step runtime info
**Step**: S07
**Agent**: template-impl

---

## Input Files

- `ai-dev/active/CR-00023/CR-00023_CR_Design.md` — design (AC5)
- `templates/design/Implementation_Prompt_Template.md`
- `templates/design/CodeReview_Prompt_Template.md`
- `templates/design/CodeReview_Final_Prompt_Template.md`
- `templates/design/QualityValidation_Template.md`
- `ai-dev/templates/Implementation_Prompt_Template.md`
- `ai-dev/templates/CodeReview_Prompt_Template.md`
- `ai-dev/templates/CodeReview_Final_Prompt_Template.md`
- `ai-dev/templates/QualityValidation_Template.md`

## Output Files

- All 8 template files above — modified
- `ai-dev/active/CR-00023/reports/CR-00023_S07_Template_report.md`

## Context

After CR-00023, agents should prefer `iw item-status <ID> --json` over reading
`workflow-manifest.json` for runtime step state. Currently no template tells
agents this — they read the manifest opportunistically via Glob exploration.
This step adds an explicit "Input Files" hint in 8 templates.

The two directories MUST be kept in sync (`templates/design/` is the master
copy; `ai-dev/templates/` is synced via `iw skills sync` per
`feedback_skills_sync.md`). Edit BOTH copies of each template identically.

## Requirements

### 1. The hint text

Use this exact text (one line, in the "Input Files" section):

> **Runtime step state** — for the current step list, status, prompt paths, gate commands, etc., prefer `uv run iw item-status {ID} --json`. The `workflow-manifest.json` file is a design-time snapshot and may be out of date (CR-00023).

Replace `{ID}` with `<ID>` in the design templates (since the user-facing instance still has `{ID}` placeholders). For runtime template copies that the daemon hands to agents, the `{ID}` placeholder is substituted at launch — leave it as `{ID}` in templates.

### 2. Placement

Insert the hint as the FIRST bullet of the "## Input Files" section in each of the 8 templates. The Input Files section currently starts with bullets like:

```markdown
## Input Files

- `ai-dev/work/{ID}/{ID}_{Type}_Design.md` -- Design document
- ...
```

Change to:

```markdown
## Input Files

- **Runtime step state** — for the current step list, status, prompt paths, gate commands, etc., prefer `uv run iw item-status {ID} --json`. The `workflow-manifest.json` file is a design-time snapshot and may be out of date (CR-00023).
- `ai-dev/work/{ID}/{ID}_{Type}_Design.md` -- Design document
- ...
```

### 3. Files to edit (exhaustive list)

```
templates/design/Implementation_Prompt_Template.md
templates/design/CodeReview_Prompt_Template.md
templates/design/CodeReview_Final_Prompt_Template.md
templates/design/QualityValidation_Template.md
ai-dev/templates/Implementation_Prompt_Template.md
ai-dev/templates/CodeReview_Prompt_Template.md
ai-dev/templates/CodeReview_Final_Prompt_Template.md
ai-dev/templates/QualityValidation_Template.md
```

### 4. Files to NOT edit (in scope but explicitly excluded)

- `templates/design/QualityValidation_FIX_Prompt_Template.md`
- `templates/design/CodeReview_FIX_Prompt_Template.md`
- `templates/design/CodeReview_FIX_Final_Prompt_Template.md`
- `templates/design/QVBrowser_Prompt_Template.md`
- `ai-dev/templates/QualityValidation_FIX_Prompt_Template.md`
- `ai-dev/templates/CodeReview_FIX_Prompt_Template.md`
- `ai-dev/templates/CodeReview_FIX_Final_Prompt_Template.md`
- `ai-dev/templates/QVBrowser_Prompt_Template.md`
- All `*_Design_Template.md` files (they don't drive agent runtime — they drive design creation)

The QualityValidation_FIX templates intentionally read `scope.allowed_paths`
from the manifest, which is design-time and does not drift. Adding the hint
there would be confusing.

### 5. Sync verification

After edits, the two directories must be in lockstep. Run:

```bash
diff templates/design/Implementation_Prompt_Template.md ai-dev/templates/Implementation_Prompt_Template.md
diff templates/design/CodeReview_Prompt_Template.md ai-dev/templates/CodeReview_Prompt_Template.md
diff templates/design/CodeReview_Final_Prompt_Template.md ai-dev/templates/CodeReview_Final_Prompt_Template.md
diff templates/design/QualityValidation_Template.md ai-dev/templates/QualityValidation_Template.md
```

All four diffs must produce no output (files identical).

### 6. Hard Constraints

- Do NOT change any other line of the 7 templates listed in §3 — for those, the diff should be exactly +1 line each.
- The Implementation_Prompt_Template.md pair is the EXCEPTION (see §7 below): it gets the +1 line hint AND a new pre-flight section AND an updated Subagent Result Contract.
- Do NOT touch the FIX or BROWSER templates.
- Do NOT modify any `*.py` file in this step.

### 7. Add a pre-flight quality gates section to `Implementation_Prompt_Template.md` (CR-00023 fold-in for I-00041 finding [3])

This requirement applies ONLY to the Implementation template pair:
- `templates/design/Implementation_Prompt_Template.md`
- `ai-dev/templates/Implementation_Prompt_Template.md`

It does NOT apply to CodeReview, CodeReview_Final, or QualityValidation templates — those agents do not write code, so pre-flight gates don't apply. Adding the section to those templates would be wrong; S08's review will flag it as CRITICAL if you do.

#### 7.1 Insert the new section

The Implementation template currently has a `## Test Verification (NON-NEGOTIABLE)` section with content like:

```markdown
## Test Verification (NON-NEGOTIABLE)

After implementation:

1. Run the project's unit test command (check Makefile or `CLAUDE.md` for the exact command)
2. Run lint and type checking (check Makefile or `CLAUDE.md` for the exact command)
3. Do **NOT** report `tests_passed: true` unless ALL unit tests pass with zero failures
4. If tests fail, fix them before reporting completion
```

INSERT the following new section IMMEDIATELY BEFORE the existing `## Test Verification (NON-NEGOTIABLE)` heading:

```markdown
## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`, you MUST run these in order
and fix any issues they report. Skipping any of these wastes a fix-cycle slot
when the QV gate steps catch the same issue downstream — see I-00041 finding
[3] for the cost case (S05/S01 shipped unformatted code and an `object not
callable` mypy regression that S09 and S10 caught later, each burning a
fix-cycle).

1. **`make format`** — auto-fixes formatting drift. If it reformats files,
   inspect the diff and re-stage; do NOT skip.
2. **`make typecheck`** — must report zero errors involving the files you
   touched. Errors elsewhere are pre-existing — note them in your report but
   do not ignore your own.
3. **`make lint`** — must report zero errors.

If a tool isn't available in your worktree, STOP and raise a blocker — do not
silently skip.

In your Subagent Result Contract, populate the new `preflight` object recording
the result of each command:
- `"ok"` — ran cleanly, no changes / no errors
- `"fixed"` — applies to `format` only; the tool auto-fixed something
- `"skipped:<reason>"` — only if you raised a blocker explaining why
```

Then leave the existing `## Test Verification (NON-NEGOTIABLE)` heading and its body untouched (those instructions still apply AFTER pre-flight passes).

#### 7.2 Update the Subagent Result Contract in the same template

The template's Subagent Result Contract example currently has:

```json
{
  "step": "S{NN}",
  "agent": "{Agent}",
  "work_item": "{ID}",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "path/to/file1.py",
    "path/to/file2.py"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```

Add a `preflight` object immediately after `files_changed` and before `tests_passed`:

```json
{
  "step": "S{NN}",
  "agent": "{Agent}",
  "work_item": "{ID}",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "path/to/file1.py",
    "path/to/file2.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```

#### 7.3 Sync verification (still required)

After the §7 changes, the two Implementation template copies must remain
byte-identical:

```bash
diff templates/design/Implementation_Prompt_Template.md ai-dev/templates/Implementation_Prompt_Template.md
```

Must produce no output.

## Project Conventions

Per `feedback_skills_sync.md`: skill / template edits in this repo must also be
propagated to IW-AI-DEV and InnoForge. That cross-repo sync is OUT OF SCOPE for
this step — the user will handle it manually after this CR ships. Note this in
your report.

## TDD Requirement

Templates aren't unit-tested directly. S09 will add regression tests that
parse the templates and assert (a) the iw item-status hint string is present
in all 8 in-scope templates and (b) the new pre-flight section + `preflight`
contract field are present in BOTH copies of `Implementation_Prompt_Template.md`
and ABSENT from the other 7 in-scope templates and the FIX/Browser variants.

## Subagent Result Contract

```json
{
  "step": "S07",
  "agent": "template-impl",
  "work_item": "CR-00023",
  "completion_status": "complete",
  "files_changed": [
    "templates/design/Implementation_Prompt_Template.md",
    "templates/design/CodeReview_Prompt_Template.md",
    "templates/design/CodeReview_Final_Prompt_Template.md",
    "templates/design/QualityValidation_Template.md",
    "ai-dev/templates/Implementation_Prompt_Template.md",
    "ai-dev/templates/CodeReview_Prompt_Template.md",
    "ai-dev/templates/CodeReview_Final_Prompt_Template.md",
    "ai-dev/templates/QualityValidation_Template.md"
  ],
  "tests_passed": true,
  "test_summary": "All 4 directory pairs are byte-identical (diff returned no output)",
  "blockers": [],
  "notes": "Cross-repo template sync to IW-AI-DEV / InnoForge is out of scope; user will handle manually."
}
```
