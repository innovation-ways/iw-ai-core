---
name: iw-review-design
version: "2.0.0"
description: Reviews and validates a design package (Feature, Incident, or Change Request) for completeness, consistency, and compliance with IW workflow conventions. Then performs a substantive design critique. Fixes issues found. Use after creating a design package and before approving it. Triggers on "review design", "validate design", "check design", "/iw-review-design".
allowed-tools: Read, Grep, Glob, Edit, Write, Bash
argument-hint: <work item ID, e.g. I006, F124, CR002>
---

# Design Package Reviewer

Validate, critique, and fix the design package for work item **$ARGUMENTS**.

This review has two phases:
1. **Compliance Review** (Steps 1-5) — structural completeness, format, consistency
2. **Substantive Design Critique** (Step 6) — is the analysis correct and the solution sound?

---

## Step 1: Locate and Load the Package

1. Determine the work item ID from `$ARGUMENTS` (e.g., `I006`, `F124`, `CR002`)
2. Read all files in `ai-dev/active/{ID}/`:
   - Design document: `{ID}_*_Design.md`
   - Manifest: `workflow-manifest.json`
   - All prompts in `prompts/`
   - Evidence files in `evidences/pre/` (if any)
3. Also check current platform status:
   ```bash
   iw item-status $ARGUMENTS 2>/dev/null || echo "Not registered yet"
   ```
4. Determine the work item type from the ID prefix:
   - `F` → Feature, `I` → Issue/Incident, `CR` → Change Request
5. Read the corresponding template for the type:
   - Feature: `ai-dev/templates/Feature_Design_Template.md`
   - Issue: `ai-dev/templates/Issue_Design_Template.md`
   - CR: `ai-dev/templates/CR_Design_Template.md`

## Step 2: Validate the Design Document

Check the design document against its template. Every required section must be present and non-empty.

### Common Checks (all types)

- [ ] **Metadata block** present (Type, Created, Status; plus type-specific fields: Priority/Severity/Reason, Reported By for Issues)
- [ ] **Description** section is non-empty (at least 2 sentences)
- [ ] **Project Context** section present (points to the project's `CLAUDE.md`)
- [ ] **Implementation Plan / Fix Plan** table present
- [ ] **File Manifest** section present with file listing table
- [ ] **File Manifest** lists at least one concrete file path — if zero file paths are found anywhere in the design doc, flag as a WARNING (the batch planner uses these paths for conflict detection; a doc with no paths will be invisible to the overlap analysis)
- [ ] **Acceptance Criteria** — at least one `Given/When/Then` block (all types)
- [ ] **Dependencies** section present (Depends on / Blocks, even if "None")
- [ ] **TDD Approach** section present (all types)
- [ ] **Notes** section present

### Incident-Specific Checks

- [ ] **Bug Description** — what is broken and expected behavior
- [ ] **Steps to Reproduce** — numbered sequence with Expected/Actual
- [ ] **Root Cause Analysis** with file:line references
- [ ] **Affected Components** table
- [ ] **Test to Reproduce** — failing test proving the bug exists
- [ ] **Regression Prevention** section
- [ ] **Acceptance Criteria** includes at least AC1 "Bug is fixed" and AC2 "Regression test exists"
- [ ] **Tests agent step** — in the Fix Plan (mandatory)
- [ ] **Semantic Correctness Warning** in the Tests prompt (I003 lesson)
- [ ] If UI-visible: **Browser Evidence** and **Browser Verification Script** sections present

### Feature-Specific Checks

- [ ] **Scope** section with in scope / out of scope
- [ ] **Boundary Behavior** table — edge cases covered (every row should be a mandatory test case)
- [ ] **Invariants** numbered list (each maps to a test)

### CR-Specific Checks

- [ ] **Current Behavior** and **Desired Behavior** as **separate** sections (flag as FAIL if collapsed into a single paragraph)
- [ ] **Impact Analysis** — Affected Components table, Breaking Changes, Data Migration
- [ ] **Rollback Plan** — Database / Code / Data all addressed

### Functional Design Document Checks

The functional doc (`ai-dev/active/{ID}/{ID}_Functional.md`) is the human-facing
summary alongside the technical design. It is validated in two phases:

#### Structural Checks (BLOCKING — must fail the review if any check fails)

These checks verify the file exists and has the correct structure. A blocking
failure prevents approval — the reviewer must fix the issue before proceeding.

- [ ] File `ai-dev/active/{ID}/{ID}_Functional.md` exists
- [ ] File body contains H1 `# {ID} — Functional Design` (or variant using en-dash `—`)
- [ ] File body contains H2 `## Why`
- [ ] File body contains H2 `## What Changed (for the User)`
- [ ] File body contains H2 `## How It Behaves`
- [ ] Word count of prose body (excluding the HTML comment at the top and all headings) is **at most 500** — ≤500 passes; >500 is a **blocking error**

#### Content Checks (WARNING — reported but non-blocking unless reviewer explicitly dismisses)

These checks detect implementation detail that should not appear in a human-facing
summary. Warnings may be dismissed by the reviewer if the offending term is
genuinely appropriate in context (e.g. "the dashboard" is fine; "dashboard/routers"
is a path fragment and is not). To dismiss, note the dismissal in the review output.

- [ ] **File-extension regex**: `\b[A-Za-z0-9_./-]+\.(py|md|js|ts|tsx|sql|html|json|toml|yaml|yml)\b` — any match triggers a warning (e.g. `orch/foo.py`, `test_issue.md` are not allowed)
- [ ] **Path-fragment regex**: `\b(orch|dashboard|scripts|ai-dev|tests|skills|templates|executor)/` — any match triggers a warning (e.g. `dashboard/routers` is not allowed, but "the dashboard" alone is fine)
- [ ] **SQL-DDL regex** (case-insensitive): `\b(ALTER\s+TABLE|CREATE\s+TABLE|DROP\s+TABLE|INSERT\s+INTO|SELECT\s+\*)\b` — any match triggers a warning
- [ ] **Fenced code block**: three backticks (` ``` `) anywhere in the body — triggers a warning

**Blocking vs Warning distinction**: Structural checks are enforced by the skill
automatically and block approval. Content checks produce warnings that the reviewer
may dismiss with justification — the skill does not block on warnings alone.

## Step 3: Validate the Workflow Manifest

Check `ai-dev/active/{ID}/workflow-manifest.json`:

- [ ] Required top-level fields: `id`, `type`, `title`, `browser_verification`, `steps`
- [ ] `id` matches the work item ID
- [ ] `type` is one of `Feature` | `Issue` | `ChangeRequest` (matches the ID prefix)
- [ ] `browser_verification` is a boolean (not omitted, not a string)
- [ ] All steps use the canonical shape `{step, agent, description, ...}` — **FAIL** if any step uses legacy fields like `work_item_id`, `step_number`, `agent_label`, `opencode_agent`, or an aggregate `gates[]` array
- [ ] Step IDs are `S01`, `S02`, … sequential and zero-padded
- [ ] Agent slugs are from the canonical set: `database-impl`, `backend-impl`, `api-impl`, `frontend-impl`, `tests-impl`, `pipeline-impl`, `template-impl`, `code-review-impl`, `code-review-final-impl`, `code-review-fix-impl`, `code-review-fix-final-impl`, `qv-gate`, `qv-browser`
- [ ] QV gate steps present after `code-review-final-impl` (one step per gate — NOT a single aggregate step)
- [ ] QV gate steps have `gate` and `command` fields (no `prompt` field)
- [ ] All non-QV-gate steps have a `prompt` field pointing to a file that exists under `prompts/`
- [ ] If `browser_verification: true`, a `qv-browser` step exists (with `prompt` field) at the end of the QV sequence
- [ ] If `browser_verification: false`, no `qv-browser` step is present

## Step 4: Validate Prompt Files

For each step in the manifest with a `prompt` field:

1. Verify the file exists at `ai-dev/active/{ID}/prompts/{filename}`
2. Check it has Input Files and Output Files sections
3. Verify it has a clear task description

### For Tests prompts specifically:

- [ ] **Reproduction test** requirement is explicit
- [ ] **Regression tests** requirement is explicit
- [ ] **I003 Semantic Correctness Warning** is included verbatim

## Step 5: Cross-Reference Consistency

- [ ] Step count in manifest matches prompt files count (excluding QV gates)
- [ ] Agent in manifest matches agent in prompt filename
- [ ] Step numbers are sequential and consistent

## Step 6: Substantive Design Critique

Go beyond compliance — evaluate whether the design is **correct and sound**:

1. **Root Cause / Architecture Analysis**: Is the proposed change at the right level? Does it fix the root cause (not symptoms)?
2. **Completeness**: Are there edge cases missing from the plan?
3. **Risk Assessment**: What could go wrong? Are the risks addressed?
4. **Test Coverage**: Are the tests meaningful? Do they cover the important scenarios?
5. **Scope**: Is this too large (should be split)? Too narrow (misses related issues)?

### For incidents specifically:
- Is the root cause correctly identified?
- Does the fix approach actually solve it?
- Are the reproduction tests meaningful?
- Are there related issues that should be fixed at the same time?

## Step 7: Fix Issues Found

Fix any issues found in Steps 2-6:

- Missing sections → add them
- Incorrect manifest → fix it
- Missing prompt files → create them
- Inconsistent cross-references → align them
- Wrong approach → propose corrections and discuss with user before changing

## Step 8: Final Summary

Report findings and what was fixed:

```markdown
### Design Review: {ID}

**Compliance**: PASS / FAIL (N issues found, N fixed)
**Manifest**: PASS / FAIL
**Prompts**: PASS / FAIL (N/N files valid)
**Substantive**: {Summary of design quality}

### Issues Fixed
- {Issue 1} → Fixed
- {Issue 2} → Fixed

### Remaining Issues (requires user decision)
- {Issue 1} — Recommendation: ...

### Next Steps
- When ready to proceed: `iw approve $ARGUMENTS`
- Or request further changes and re-run /iw-review-design $ARGUMENTS
```

---

## Constraints

- **DO** fix compliance issues automatically (missing sections, format problems)
- **DO** discuss substantive design issues with the user before changing the approach
- **NEVER** change the scope without user approval
- **NEVER** modify prompt files in ways that change the implementation approach without user approval
