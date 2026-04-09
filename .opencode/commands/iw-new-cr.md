---
description: Create a new change request package. Reserves an ID, performs impact analysis, creates design document with breaking change handling and rollback plan, then registers in the database.
---

# Create New Change Request

You are creating a change request package. Follow these steps exactly.

## Step 1: Reserve ID

```bash
iw next-id --type cr
```

Save the returned ID (e.g., CR007) for use throughout this process.

## Step 2: Discuss with User (MANDATORY)

Before proceeding, you MUST gather change request details from the user:

1. **Read CLAUDE.md** to understand the project's architecture and conventions.
2. **Ask the user** for change request details:
   - What change is being requested?
   - Why is this change needed? (motivation/business reason)
   - What is the current behavior?
   - What is the desired behavior?
   - Are there breaking changes?
   - What is the urgency?
3. **Perform impact analysis**:
   - Search the codebase for all affected code
   - Identify all components that will be impacted
   - Assess backward compatibility
   - Identify dependent systems or consumers
4. **Present your analysis** to the user and confirm.

Do NOT proceed until the user confirms the analysis is correct.

## Step 3: GO/NO-GO Checkpoint

Present the following to the user and ask for explicit GO/NO-GO:

- **Change Request ID**: {ID}
- **Title**: (one-line summary)
- **Impact analysis**: (what is affected)
- **Breaking changes**: (yes/no, details)
- **Risk assessment**: (migration risks, compatibility)
- **Estimated complexity**: (low/medium/high)
- **Rollback feasibility**: (easy/moderate/difficult)

Wait for user to say GO before proceeding.

## Step 4: Create Design Document

Create the design directory and document:

```
ai-dev/design/active/{ID}/
  design.md
```

The design document should include:
- **Title and ID**
- **Change Description**: What is changing and why
- **Current Behavior**: How the system works now
- **Desired Behavior**: How the system should work after the change
- **Impact Analysis**: All affected components, APIs, data, consumers
- **Breaking Changes**: Detailed list with migration path for each
- **Migration Plan**: Step-by-step migration for consumers/data
- **Rollback Plan**: How to revert the change safely
- **Scope**: What files/components will be modified
- **Testing Strategy**:
  - Unit tests for new behavior
  - Migration tests
  - Backward compatibility tests (if applicable)
  - Integration tests
- **Acceptance Criteria**: How to verify the change is complete and correct

## Step 5: Generate Prompt Files

Create implementation prompt files for each workflow step:

```
ai-dev/design/active/{ID}/
  prompts/
    S01_{agent_type}.md
    ...
```

Each prompt should clearly describe the change scope and any migration requirements.

## Step 6: Generate Workflow Manifest

Create the manifest file:

```
ai-dev/design/active/{ID}/manifest.json
```

Assign agents based on what needs to change. Include review steps after every implementation step. For breaking changes, consider adding extra review steps.

## Step 7: Register in Database

```bash
iw register {ID} --title "..." --type cr --design-path ai-dev/design/active/{ID}/design.md
```

## Step 8: Present Summary

Show the user:
- Change Request ID
- Impact summary
- Breaking changes summary
- Design document path
- Number of workflow steps
- Next steps (approve for execution)
