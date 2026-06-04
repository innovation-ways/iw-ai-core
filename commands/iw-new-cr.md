---
description: Create a new change request package. Reserves an ID, performs impact analysis, creates design document with breaking change handling and rollback plan, prompts, and workflow manifest, then registers in the database.
---

# Create New Change Request

Create a complete change request package for the current project.

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

Ask the user to confirm or correct:

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
- Manifest: `ai-dev/active/{ID}/workflow-manifest.json`
```

Ask: **Ready to proceed? Please confirm GO or tell me what needs to change.**

Only "GO" (or clear equivalent) means proceed. Address any feedback and re-present the summary.

### Migration Lock Check (if Database step planned)

```bash
iw migration-lock status
```

If the lock is held by another item, warn the user before proceeding.

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

Use `ai-dev/templates/` as the base for each prompt type. Reports go in `ai-dev/active/{ID}/reports/`.

Every prompt MUST include `Input Files` and `Output Files` sections with paths using the `ai-dev/active/{ID}/` prefix.

Name each file: `{ID}_S{NN}_{Agent}_prompt.md`

## Step 7: Generate Workflow Manifest (only after GO)

Create `ai-dev/active/{ID}/workflow-manifest.json`:

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

Agent slug mapping:
- Database → `database-impl`
- Backend → `backend-impl`
- API → `api-impl`
- Frontend → `frontend-impl`
- Tests → `tests-impl`
- Pipeline → `pipeline-impl`
- Template → `template-impl`
- CodeReview_{X} → `code-review-impl`
- CodeReview_Final → `code-review-final-impl`
- CodeReview_FIX_{X} → `code-review-fix-impl`
- CodeReview_FIX_Final → `code-review-fix-final-impl`
- QV gates → `qv-gate` (with `"gate"` and `"command"` fields — no prompt needed)
- QV browser → `qv-browser` (only when `browser_verification: true`, with `"prompt"` field)

**QV gate steps** (add after CodeReview_Final) — **IMPORTANT: Only include gates whose commands exist in the project.**

Before writing the manifest, verify each command:
- Run `grep -n "^<target>:" Makefile` to confirm a Makefile target exists.
- Run `ls frontend/` to confirm a frontend directory exists before including `frontend-tsc` or `frontend-tests`.
- **NEVER include a gate whose command will exit non-zero unconditionally** (missing dir, missing Makefile target). A phantom gate will exhaust all fix cycles and stall the item permanently.

Full menu (select only applicable ones):
```json
{"step": "S{N+1}", "agent": "qv-gate", "gate": "lint", "command": "make lint", "description": "QV: Linting"},
{"step": "S{N+2}", "agent": "qv-gate", "gate": "format", "command": "make format-check", "description": "QV: Formatting"},
{"step": "S{N+3}", "agent": "qv-gate", "gate": "typecheck", "command": "make type-check", "description": "QV: Type checking"},
{"step": "S{N+4}", "agent": "qv-gate", "gate": "frontend-tsc", "command": "cd frontend && npx tsc --noEmit", "description": "QV: Frontend types"},
{"step": "S{N+5}", "agent": "qv-gate", "gate": "arch-check", "command": "make arch-check", "description": "QV: Architecture"},
{"step": "S{N+6}", "agent": "qv-gate", "gate": "security-sast", "command": "make security-sast", "description": "QV: Security SAST"},
{"step": "S{N+7}", "agent": "qv-gate", "gate": "unit-tests", "command": "make test-unit", "description": "QV: Unit tests"},
{"step": "S{N+8}", "agent": "qv-gate", "gate": "frontend-tests", "command": "make test-frontend", "description": "QV: Frontend tests"},
{"step": "S{N+9}", "agent": "qv-gate", "gate": "integration-tests", "command": "make allure-integration", "description": "QV: Integration tests", "timeout": 1800}
```

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

### Design Document
- `ai-dev/active/{ID}/{ID}_CR_Design.md`

### Workflow Manifest
- `ai-dev/active/{ID}/workflow-manifest.json`

### Execution Plan
| Step | File | Type |
|------|------|------|
| S01 | `{ID}_S01_{Agent}_prompt.md` | Implementation |
| ... | ... | ... |

### Next Steps
1. Review the design document and all prompts
2. Run `/iw-review-design {ID}` to validate the package
3. When ready: `iw approve {ID}`
4. To execute: `iw batch-create {ID}` → `iw batch-approve BATCH-{NNN}`
5. Monitor: dashboard at http://localhost:9900 or `iw item-status {ID}`
```

---

## Constraints

- **MUST** call `iw next-id --type cr` immediately (Step 1)
- **MUST** interact with the user in Step 2 — never skip the conversation
- **MUST** obtain explicit GO before creating any files
- **MUST** call `iw register` at the end to record in the database
- **MUST** create ALL files (design + all prompts) in a single session
- **MUST** use the exact file naming convention: `{ID}_S{NN}_{Agent}_prompt.md`
- **NEVER** implement code — this command only creates documentation
- **NEVER** skip CodeReview steps or QV gates
- **NEVER** place files in `done/` — all new files go in `ai-dev/active/`
