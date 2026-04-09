---
description: Create a new incident fix package. Reserves an ID, performs root cause analysis, creates design document with reproduction steps, prompts, and workflow manifest, then registers in the database.
---

# Create New Incident

You are creating an incident fix package. Follow these steps exactly.

## Step 1: Reserve ID

```bash
iw next-id --type incident
```

Save the returned ID (e.g., I045) for use throughout this process.

## Step 2: Discuss with User (MANDATORY)

Before proceeding, you MUST gather incident details from the user:

1. **Read CLAUDE.md** to understand the project's architecture and conventions.
2. **Ask the user** for incident details:
   - What is the observed behavior (the bug)?
   - What is the expected behavior?
   - How to reproduce the issue?
   - When did it start happening?
   - What is the impact/severity?
   - Any error messages or logs?
   - Any browser evidence or screenshots? (optional)
3. **Perform root cause analysis**:
   - Search the codebase for the affected code
   - Identify the root cause
   - Determine the scope of the fix
4. **Present your analysis** to the user and confirm.

Do NOT proceed until the user confirms the analysis is correct.

## Step 3: GO/NO-GO Checkpoint

Present the following to the user and ask for explicit GO/NO-GO:

- **Incident ID**: {ID}
- **Title**: (one-line summary of the bug)
- **Root cause**: (what is causing the issue)
- **Fix scope**: (what needs to change)
- **Risk assessment**: (regression risks, side effects)
- **Estimated complexity**: (low/medium/high)

Wait for user to say GO before proceeding.

## Step 4: Create Design Document

Create the design directory and document:

```
ai-dev/design/active/{ID}/
  design.md
```

The design document should include:
- **Title and ID**
- **Incident Description**: What is broken
- **Reproduction Steps**: Exact steps to reproduce
- **Root Cause Analysis**: What is causing the issue and why
- **Proposed Fix**: How it will be fixed
- **Scope**: What files/components will be modified
- **Testing Strategy**: How to verify the fix works
  - Unit tests for the specific fix
  - Regression tests to prevent recurrence
  - Integration tests if cross-layer
- **Rollback Plan**: How to revert if the fix causes issues
- **Acceptance Criteria**: How to verify the incident is resolved

## Step 5: Generate Prompt Files

Create implementation prompt files for each workflow step:

```
ai-dev/design/active/{ID}/
  prompts/
    S01_{agent_type}.md
    ...
```

Each prompt should clearly reference the root cause and expected fix.

## Step 6: Generate Workflow Manifest

Create the manifest file:

```
ai-dev/design/active/{ID}/manifest.json
```

Assign agents based on where the fix is needed. Incident workflows are typically shorter than feature workflows. Always include review steps.

## Step 7: Register in Database

```bash
iw register {ID} --title "..." --type incident --design-path ai-dev/design/active/{ID}/design.md
```

## Step 8: Present Summary

Show the user:
- Incident ID
- Root cause summary
- Design document path
- Number of workflow steps
- Next steps (approve for execution)
