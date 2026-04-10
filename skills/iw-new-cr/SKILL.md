---
name: iw-new-cr
version: "2.1.0"
description: Creates a new Change Request design document with all implementation prompts following the IW development workflow. Use when modifying existing functionality, requesting changes to current behavior, refactoring, or user says "new change request", "new CR", "create CR", "change request", "modify existing", "/iw-new-cr".
allowed-tools: Read, Grep, Glob, Edit, Write, Bash
argument-hint: <brief description of the change needed>
---

# New Change Request Creator

Create a complete change request package for the current project.

**Change description**: $ARGUMENTS

---

## Step 1: Reserve CR ID

Reserve the next available CR ID **immediately** to prevent concurrent agents from claiming the same number.

```bash
iw next-id --type cr
```

This atomically allocates the next ID (e.g., `CR-00001`) using a database row-lock. Store the returned ID **exactly as printed** — you will use it verbatim throughout.

**CRITICAL**: The `iw next-id` call MUST happen before ANY other work.

**CRITICAL**: Use the ID **exactly as returned** (format: `CR-NNNNN`). Do NOT look for tracking files, do NOT use a manually chosen number, do NOT override or "adjust" the returned value for any reason. The database is the sole source of truth for IDs.

## Step 2: Understand the Change (MANDATORY INTERACTION)

**NEVER skip this step.** Discuss with the user to ensure alignment.

Present what you understood from `$ARGUMENTS`, then ask the user to confirm or correct:

1. **What needs to change?** (current behavior → desired behavior)
2. **Why is this change needed?** (requirement change, optimization, refactor, tech debt, etc.)
3. **Priority**: Critical / High / Medium / Low
4. **Which layers are affected?** (Database / Backend / API / Frontend / Pipeline / Template)
5. **Are there breaking changes?** (API contracts, database schema, integrations)
6. **Is data migration needed?**

**WAIT for user answers before proceeding.**

### Determine UI Visibility

If the change affects what users see in the browser, mark `browser_verification: true` and capture browser evidence of the current state before proposing changes.

## Step 3: Analyze Current Implementation

Before writing the design:

1. Read the existing code in the affected area
2. Understand current behavior and why it works the way it does
3. Identify all files that will change
4. Check for tests that cover current behavior (these may need updating)
5. Assess risk of regression

Document findings with specific file paths and line references.

## Step 4: GO/NO-GO Checkpoint (MANDATORY)

**STOP. Do NOT create any files until the user gives explicit GO.**

Present a summary:

```markdown
### Change Request Summary: {ID}

**Change**: {1-2 sentence description of current → desired behavior}
**Reason**: {Why this change is needed}
**Priority**: {Critical / High / Medium / Low}
**Breaking changes**: {Yes / No — describe if yes}
**Data migration**: {Required / Not required}

### Proposed Change Plan
| Step | Agent | Description |
|------|-------|-------------|
| S01 | {Agent} | {What this step does} |
| ... | ... | ... |

### Files to Create
- Design: `ai-dev/active/{ID}/{ID}_CR_Design.md`
- Prompts: {count} files in `ai-dev/active/{ID}/prompts/`
```

Ask: **Ready to proceed? Please confirm GO or tell me what needs to change.**

### Migration Lock Check (if Database step planned)

```bash
iw migration-lock status
```

If the lock is held by another item, warn the user.

## Step 5: Create Design Document (only after GO)

Create the folder structure:

```bash
mkdir -p ai-dev/active/{ID}/prompts/
```

Then create the design document at:
```
ai-dev/active/{ID}/{ID}_CR_Design.md
```

Use the template from `ai-dev/templates/CR_Design_Template.md`. Fill in ALL sections including:

- **Description** — current behavior → desired behavior
- **Reason** — why this change is needed
- **Impact Assessment** — breaking changes, migration needs
- **Change Plan** — agent steps
- **Rollback Plan** — how to revert if needed
- **Test Strategy** — updating existing tests + new coverage

## Step 6: Generate ALL Prompt Files (only after GO)

Create all prompt files in `ai-dev/active/{ID}/prompts/`.

## Step 7: Generate Workflow Manifest (only after GO)

Create `ai-dev/active/{ID}/workflow-manifest.json` (step definitions — state lives in DB):

```json
{
  "id": "{ID}",
  "type": "ChangeRequest",
  "title": "{One-line CR title}",
  "browser_verification": false,
  "steps": [
    {
      "step": "S01",
      "agent": "{agent-slug}",
      "description": "{What this step does}",
      "prompt": "prompts/{ID}_S01_{Agent}_prompt.md"
    }
  ]
}
```

Add QV gate steps after CodeReview_Final (same as iw-new-incident pattern).

## Step 8: Register in Platform

After all files are created, register the item in the database:

```bash
iw register {ID} "{One-line CR title}" \
  --type cr \
  --design-doc ai-dev/active/{ID}/{ID}_CR_Design.md \
  --steps-from ai-dev/active/{ID}/workflow-manifest.json
```

## Step 9: Present Package for Review

```markdown
## Change Request Package: {ID} — {Title}

### Next Steps
1. Review the design document and all prompts
2. When ready: `iw approve {ID}`
3. To execute: `iw batch-create {ID}` → `iw batch-approve BATCH-{NNN}`
4. Monitor: dashboard at http://localhost:9900
```

---

## Constraints

- **MUST** call `iw next-id --type cr` immediately (Step 1)
- **MUST** interact with the user in Step 2 — never skip the conversation
- **MUST** obtain explicit GO before creating any files
- **MUST** call `iw register` at the end to record in the database
- **NEVER** implement code — this skill only creates documentation
- **NEVER** skip CodeReview steps or QV gates
