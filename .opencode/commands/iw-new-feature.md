---
description: Create a new feature design package. Reserves an ID, discusses scope with user, creates design document, prompts, and workflow manifest, then registers in the database.
---

# Create New Feature

You are creating a new feature design package. Follow these steps exactly.

## Step 1: Reserve ID

```bash
iw next-id --type feature
```

Save the returned ID (e.g., F123) for use throughout this process.

## Step 2: Discuss with User (MANDATORY)

Before proceeding, you MUST discuss the feature with the user:

1. **Read CLAUDE.md** to understand the project's architecture, conventions, and constraints.
2. **Ask the user** to describe the feature in detail:
   - What problem does it solve?
   - What is the expected behavior?
   - What are the acceptance criteria?
   - Are there any dependencies or constraints?
3. **Clarify ambiguities** — ask follow-up questions until the scope is clear.
4. **Summarize** what you understood and confirm with the user.

Do NOT proceed until the user confirms the scope is correct.

## Step 3: GO/NO-GO Checkpoint

Present the following to the user and ask for explicit GO/NO-GO:

- **Feature ID**: {ID}
- **Title**: (one-line summary)
- **Scope summary**: (2-3 sentences)
- **Estimated complexity**: (low/medium/high)
- **Risk assessment**: (any concerns)
- **Dependencies**: (other items or systems)

Wait for user to say GO before proceeding.

## Step 4: Create Design Document

Create the design directory and document:

```
ai-dev/design/active/{ID}/
  design.md
```

The design document should include:
- **Title and ID**
- **Problem Statement**: What problem this solves
- **Proposed Solution**: How it will be implemented
- **Scope**: What is in scope and out of scope
- **Architecture**: How it fits into the existing system (reference CLAUDE.md)
- **Data Model Changes**: Any database changes needed
- **API Changes**: Any new or modified endpoints
- **UI Changes**: Any frontend changes
- **Error Handling**: How errors will be handled
- **Testing Strategy**: Unit tests, integration tests, edge cases
- **Acceptance Criteria**: Measurable criteria for completion

## Step 5: Generate Prompt Files

Create implementation prompt files for each workflow step:

```
ai-dev/design/active/{ID}/
  prompts/
    S01_{agent_type}.md
    S02_{agent_type}.md
    ...
```

Each prompt file should contain:
- Clear scope for that specific agent
- References to relevant sections of the design document
- Input/output expectations
- Constraints specific to that step

## Step 6: Generate Workflow Manifest

Create the manifest file:

```
ai-dev/design/active/{ID}/manifest.json
```

Structure:
```json
{
  "id": "{ID}",
  "type": "feature",
  "title": "...",
  "steps": [
    {
      "step": "S01",
      "agent": "database-impl",
      "prompt_file": "prompts/S01_database.md",
      "depends_on": []
    },
    {
      "step": "S02",
      "agent": "database-review",
      "prompt_file": "prompts/S01_database.md",
      "depends_on": ["S01"]
    }
  ]
}
```

Assign agents based on the scope:
- Database changes: `database-impl` + `database-review`
- Backend logic: `backend-impl` + `backend-review`
- API endpoints: `api-impl` + `api-review`
- Frontend/UI: `frontend-impl` + `frontend-review`
- Additional tests: `tests-impl` + `tests-review`
- Background processing: `pipeline-impl` + `pipeline-review`
- Templates: `template-impl` + `template-review`

Always include review steps after implementation steps.

## Step 7: Register in Database

```bash
iw register {ID} --title "..." --type feature --design-path ai-dev/design/active/{ID}/design.md
```

## Step 8: Present Summary

Show the user:
- Feature ID
- Design document path
- Number of workflow steps
- Agent assignments
- Next steps (approve for execution)
