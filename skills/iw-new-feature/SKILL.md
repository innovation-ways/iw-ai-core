---
name: iw-new-feature
version: "2.1.0"
description: Creates a new Feature design document with all implementation prompts following the IW development workflow. Use when starting a new feature, creating feature designs, planning feature implementation, or user says "new feature", "create feature", "design feature", "/iw-new-feature".
allowed-tools: Read, Grep, Glob, Edit, Write, Bash
argument-hint: <brief feature description>
---

# New Feature Creator

Create a complete feature design package for the current project.

**Feature request**: $ARGUMENTS

---

## Step 1: Reserve Feature ID

Reserve the next available Feature ID **immediately** to prevent concurrent agents from claiming the same number.

```bash
iw next-id --type feature
```

This atomically allocates the next ID (e.g., `F-00001`) using a database row-lock. Store the returned ID **exactly as printed** — you will use it verbatim throughout.

**CRITICAL**: The `iw next-id` call MUST happen before ANY other work.

**CRITICAL**: Use the ID **exactly as returned** (format: `F-NNNNN`). Do NOT look for tracking files, do NOT use a manually chosen number, do NOT override or "adjust" the returned value for any reason. The database is the sole source of truth for IDs.

## Step 2: Gather Requirements (MANDATORY INTERACTION)

**NEVER skip this step.** Even if `$ARGUMENTS` seems detailed, ALWAYS discuss with the user to ensure alignment.

Present what you understood from `$ARGUMENTS`, then ask the user to confirm or correct:

1. **What does this feature do?** (2-3 sentence description)
2. **Which layers are involved?** (Database / Backend / API / Frontend / Pipeline / Template)
3. **Priority**: Critical / High / Medium / Low
4. **Dependencies**: Does this depend on or block other work items?
5. **Key acceptance criteria** (at least 2 Given/When/Then scenarios)

**WAIT for user answers before proceeding.**

## Step 2b: Browser Evidence Capture (Frontend features only — MANDATORY before GO)

**When the feature affects what users see in the browser** (Frontend layer is in scope), you MUST capture the current UI state BEFORE presenting the GO/NO-GO checkpoint.

Evidence files are an exception to the "no files before GO" rule — they are investigation artifacts, not design documents.

1. Check dev environment health:
   ```bash
   ./innoforge.sh --health
   ```

2. If healthy, navigate to the affected area and screenshot the **current state** (before the feature exists):
   ```bash
   playwright-cli open http://localhost:5173
   # Navigate to the relevant page/section
   playwright-cli screenshot ai-dev/active/{ID}/evidences/pre/{ID}-before.png
   playwright-cli close
   ```

3. Store the evidence status for the GO/NO-GO checkpoint:
   - `Captured` — screenshot saved to `evidences/pre/`
   - `Deferred` — dev environment not running (note in design doc)
   - `N/A` — no frontend changes (backend-only feature)

**If the dev environment is not running**, skip browser capture and note it as "deferred — dev environment not available" in the design document.

## Step 3: Analyze Codebase

Before writing the design, examine relevant existing code:

1. Identify existing files that will be changed or extended
2. Understand current patterns and conventions in the codebase
3. Check for related tests to understand expected behavior
4. Identify potential integration points

Document findings with specific file paths and line references.

## Step 4: GO/NO-GO Checkpoint (MANDATORY)

**STOP. Do NOT create any files until the user gives explicit GO.**

Present a summary:

```markdown
### Feature Summary: {ID}

**Feature**: {1-2 sentence description}
**Layers affected**: {Database / Backend / API / Frontend / Pipeline / Template}
**Priority**: {Critical / High / Medium / Low}
**Browser Evidence**: {Captured / Deferred / N/A — backend-only}

### Proposed Implementation Plan
| Step | Agent | Description | Parallel With |
|------|-------|-------------|---------------|
| S01 | {Agent} | {What this step does} | — |
| ... | ... | ... | ... |

### Files to Create
- Design: `ai-dev/active/{ID}/{ID}_Feature_Design.md`
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
mkdir -p ai-dev/active/{ID}/evidences/pre/
mkdir -p ai-dev/active/{ID}/evidences/post/
```

Then create the design document at:
```
ai-dev/active/{ID}/{ID}_Feature_Design.md
```

Use the template from `ai-dev/templates/Feature_Design_Template.md`. Fill in ALL sections:

- **Description** — what this feature does (2-3 sentences)
- **Scope** — in scope / out of scope
- **Architecture References** — existing files/patterns this builds on
- **Acceptance Criteria** — Given/When/Then scenarios
- **Boundary Behavior** — edge cases table
- **Implementation Plan** — agent steps with parallelism
- **File Manifest** — all files to create/modify
- **TDD Approach** — testing strategy

### Agent Selection

| Layer | Agent |
|-------|-------|
| Database schema/migration | `Database` |
| Service/repository logic | `Backend` |
| API endpoints | `API` |
| UI components | `Frontend` |
| Pipeline/worker tasks | `Pipeline` |
| Template rendering | `Template` |
| Test coverage | `Tests` |

Use parallelism where possible (e.g., Backend + Frontend after Database completes).

### Implementation Plan Structure

```
S01: Database — Schema + migration (if needed)
S02: Backend — Service + repository
S03: CodeReview_Backend — Review S02
S04: API — Endpoints + serializers
S05: Frontend — UI components
[parallel: S04 and S05 can often run in parallel]
S06: Tests — Integration + unit tests
S07: CodeReview_Final — Global review
S08..S16: QV Gates
S17: QV Browser — Post-implementation screenshot (Frontend features only)
```

**QV Browser step** (include when `browser_verification: true`):
```json
{"step": "S{N}", "agent": "qv-browser", "description": "QV: Browser verification — verify feature end-to-end in isolated worktree stack", "prompt": "prompts/{ID}_S{N}_BrowserVerification_prompt.md"}
```

To create the prompt file, **copy `ai-dev/templates/QVBrowser_Prompt_Template.md`** (synced from `templates/design/` by `iw init-project` / `iw skills sync`) to `ai-dev/active/{ID}/prompts/{ID}_S{N}_BrowserVerification_prompt.md` and fill in ONLY the `{{ID}}`, `{{STEP}}`, `{{TITLE}}`, `{{TYPE}}`, input-files list, and V1..V(n) sections with concrete acceptance criteria from the feature design. Leave the Environment, Prerequisites, Pass Criteria, Report, and Result Contract sections untouched.

**Hard rules for the QV Browser prompt:**
- **NEVER** hardcode URLs, ports, or credentials. No `localhost:5173`, no `localhost:5174`, no literal passwords. The IW daemon spins up an isolated e2e stack built from the worktree's source and exports `$IW_BROWSER_BASE_URL`, `$IW_BROWSER_E2E_USER`, `$IW_BROWSER_E2E_PASSWORD`, `$IW_ITEM_ID`, and `$IW_STEP_ID` at runtime. Use those env vars (or the equivalent `{{IW_BROWSER_BASE_URL}}` placeholder, which the daemon substitutes at launch).
- **NEVER** instruct the agent to run `make dev`, `make e2e-up`, `docker compose`, or any install command — the stack is already up and will be torn down afterwards.
- Use `playwright-cli` exclusively (not `agent-browser`, not direct `chromium.launch()`).
- The V(n) section must include a **No Regressions** verification covering adjacent flows and console-error checks.

## Step 6: Generate ALL Prompt Files (only after GO)

Create all prompt files in `ai-dev/active/{ID}/prompts/`.

Use `ai-dev/templates/` as the base for each prompt type. Reports go in `ai-dev/active/{ID}/reports/`.

## Step 7: Generate Workflow Manifest (only after GO)

Create `ai-dev/active/{ID}/workflow-manifest.json` (step definitions — state lives in DB):

```json
{
  "id": "{ID}",
  "type": "Feature",
  "title": "{One-line feature title}",
  "browser_verification": true,
  // set to false for backend-only features (no Frontend step)
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

QV gate steps (add after CodeReview_Final):
```json
{"step": "S{N+1}", "agent": "qv-gate", "gate": "lint", "command": "make lint", "description": "QV: Linting"},
{"step": "S{N+2}", "agent": "qv-gate", "gate": "format", "command": "make format-check", "description": "QV: Formatting"},
{"step": "S{N+3}", "agent": "qv-gate", "gate": "typecheck", "command": "make type-check", "description": "QV: Type checking"},
{"step": "S{N+4}", "agent": "qv-gate", "gate": "frontend-tsc", "command": "cd frontend && npx tsc --noEmit", "description": "QV: Frontend types"},
{"step": "S{N+5}", "agent": "qv-gate", "gate": "arch-check", "command": "make arch-check", "description": "QV: Architecture"},
{"step": "S{N+6}", "agent": "qv-gate", "gate": "security-sast", "command": "make security-sast", "description": "QV: Security SAST"},
{"step": "S{N+7}", "agent": "qv-gate", "gate": "unit-tests", "command": "make test-unit", "description": "QV: Unit tests"},
{"step": "S{N+8}", "agent": "qv-gate", "gate": "frontend-tests", "command": "make test-frontend", "description": "QV: Frontend tests"},
{"step": "S{N+9}", "agent": "qv-gate", "gate": "integration-tests", "command": "make allure-integration", "description": "QV: Integration tests", "timeout": 900}
```

## Step 8: Register in Platform

After all files are created, register the item in the database:

```bash
iw register {ID} "{One-line feature title}" \
  --type feature \
  --design-doc ai-dev/active/{ID}/{ID}_Feature_Design.md \
  --steps-from ai-dev/active/{ID}/workflow-manifest.json
```

## Step 9: Present Package for Review

Display a summary showing all created files and the next steps:

```markdown
## Feature Package: {ID} — {Title}

### Design Document
- `ai-dev/active/{ID}/{ID}_Feature_Design.md`

### Next Steps
1. Review the design document and all prompts
2. When ready: `iw approve {ID}`
3. To execute: `iw batch-create {ID}` → `iw batch-approve BATCH-{NNN}`
4. Monitor: dashboard at http://localhost:9900
```

---

## Constraints

- **MUST** call `iw next-id --type feature` immediately (Step 1)
- **MUST** interact with the user in Step 2 — never skip the conversation
- **MUST** obtain explicit GO before creating any files
- **MUST** call `iw register` at the end to record in the database
- **MUST** create ALL files in a single session
- **NEVER** implement code — this skill only creates documentation
- **NEVER** skip CodeReview steps or QV gates
