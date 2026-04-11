---
name: iw-new-incident
version: "2.1.0"
description: Creates a new Incident (bug fix) design document with all fix prompts following the IW development workflow. Use when reporting a bug, creating incident reports, planning bug fixes, or user says "new incident", "new bug", "create incident", "report bug", "fix bug", "/iw-new-incident".
allowed-tools: Read, Grep, Glob, Edit, Write, Bash
argument-hint: <brief description of the bug or issue>
---

# New Incident Creator

Create a complete incident fix package for the current project.

**Issue description**: $ARGUMENTS

---

## Step 1: Reserve Incident ID

Reserve the next available Incident ID **immediately** to prevent concurrent agents from claiming the same number.

```bash
iw next-id --type incident
```

This atomically allocates the next ID (e.g., `I-00005`) using a database row-lock — no file reading needed, no race conditions possible. Store the returned ID **exactly as printed** — you will use it verbatim throughout.

**CRITICAL**: The `iw next-id` call MUST happen before ANY other work. The ID is reserved the moment the call returns.

**CRITICAL**: Use the ID **exactly as returned** (format: `I-NNNNN`). Do NOT look for tracking files, do NOT use a manually chosen number, do NOT override or "adjust" the returned value for any reason. The database is the sole source of truth for IDs.

## Step 2: Investigate the Issue

### 2a: Gather Bug Details (MANDATORY INTERACTION)

**NEVER skip this step.** Even if `$ARGUMENTS` seems detailed, ALWAYS discuss with the user to ensure alignment. Use `$ARGUMENTS` as a starting point for the conversation, not as final input.

Present what you understood from `$ARGUMENTS`, then ask the user to confirm or correct:

1. **What is broken?** (expected vs actual behavior)
2. **Steps to reproduce** (numbered sequence)
3. **Severity**: Critical / High / Medium / Low
4. **Where was it discovered?** (user report, CI failure, code review, testing, etc.)
5. **Any error messages or logs?**

**WAIT for user answers before proceeding.** Do NOT move to Step 2b until the user has confirmed the bug details.

### 2b: Determine UI Visibility

Classify whether the bug is **UI-visible** (affects what the user sees in the browser) or **backend-only** (API response error, data corruption, pipeline failure, etc.):

| UI-Visible Examples | Backend-Only Examples |
|---------------------|----------------------|
| Page redirects incorrectly | Incorrect DB query results |
| Component doesn't render | Service raises wrong exception |
| Form submission fails silently | Pipeline task fails |
| Navigation broken | API returns wrong status code |
| Visual styling broken | Data not persisted correctly |
| Permission gate blocks access | Worker crashes |

**If UI-visible**: Mark `browser_verification: true` — Steps 2c and the QualityValidation will include Playwright CLI verification.
**If backend-only**: Mark `browser_verification: false` — Skip browser steps, rely on API/unit/integration tests.

### 2c: Browser Evidence Capture (UI-visible bugs only — MANDATORY before GO)

**STOP. When `browser_verification: true`, you MUST capture browser evidence BEFORE presenting the GO/NO-GO checkpoint.** Evidence files are an exception to the "no files before GO" rule — they are investigation artifacts, not design documents.

**When `browser_verification: true`**, use playwright-cli to reproduce and document the bug:

1. Check dev environment health:
   ```bash
   ./innoforge.sh --health
   ```

2. If healthy, **fully reproduce the bug** in the browser — do NOT just screenshot the initial page state:
   - Login if needed
   - Navigate to the affected area
   - **Perform the exact steps that trigger the bug**
   - Only screenshot **after the bug is visible on screen**
   ```bash
   playwright-cli open http://localhost:5173
   # Login, navigate, and perform ALL steps to reproduce the bug
   playwright-cli screenshot ai-dev/active/{ID}/evidences/pre/{ID}-bug-evidence.png
   playwright-cli close
   ```

3. Record the exact commands used to reproduce — these become the **Browser Verification Script** in the design document.

4. Store the evidence status for the GO/NO-GO checkpoint:
   - `Captured` — screenshot saved to `evidences/pre/`
   - `Deferred` — dev environment not running (note in design doc)

**If the dev environment is not running**, skip browser capture and note it as "deferred — dev environment not available" in the design document.

**NEVER proceed to Step 3 (GO/NO-GO) without either capturing evidence or explicitly noting it as deferred.**

### 2d: Root Cause Analysis

Based on the bug description (and browser evidence if captured):

1. Search the codebase for the affected functionality
2. Trace the execution path to identify the root cause
3. Identify the specific file(s) and line(s) where the bug originates
4. Determine which layers are affected (Database / Backend / API / Frontend / Pipeline)
5. Check if related tests exist and why they didn't catch this

Document findings with file paths and line references.

## Step 3: GO/NO-GO Checkpoint (MANDATORY)

**STOP. Do NOT create any files until the user gives explicit GO.**

Present the following summary to the user and ask for approval:

```markdown
### Incident Summary: {ID}

**Bug**: {1-2 sentence description of what is broken}
**Root Cause**: {Brief root cause with file:line reference}
**Severity**: {Critical / High / Medium / Low}
**UI Visibility**: {UI-visible / Backend-only} — Browser verification: {Yes / No}
**Browser Evidence**: {Captured / Deferred / N/A — backend-only}
**Affected Layers**: {Database / Backend / API / Frontend / Pipeline}

### Proposed Fix Plan
| Step | Agent | Description |
|------|-------|-------------|
| S01 | {Agent} | {What this step does} |
| S02 | CodeReview_{Agent} | Review S01 |
| ... | ... | ... |

### Files to Create
- Design: `ai-dev/active/{ID}/{ID}_Issue_Design.md`
- Prompts: {count} files in `ai-dev/active/{ID}/prompts/`
- Manifest: `ai-dev/active/{ID}/workflow-manifest.json`

### Questions / Concerns
{List any open questions or things you're unsure about}
```

Then ask:

> **Ready to proceed? Please confirm GO to create all documentation, or tell me what needs to change.**

**Rules:**
- Only "GO" (or clear equivalent like "yes", "proceed", "approved") means proceed
- Any feedback, questions, or changes → address them and present the updated summary again
- Do NOT interpret silence or ambiguous responses as GO
- Once GO is received, proceed to Step 4 (Create Design Document)

### Migration Lock Check (if Database step planned)

If the proposed fix plan includes a `Database` agent step:

```bash
iw migration-lock status
```

If the lock is held by another item, warn the user:
> **Migration lock active**: Work item {holder} currently holds the Alembic migration lock. Running two work items with Database steps in parallel will cause migration chain conflicts. Consider: (a) waiting for {holder} to merge first, or (b) removing the Database step if possible.

The lock is acquired at execution time by the orchestrator, not at design time. This is an advisory warning only.

## Step 4: Create Design Document (only after GO)

Create the folder structure:

```bash
mkdir -p ai-dev/active/{ID}/prompts/
mkdir -p ai-dev/active/{ID}/evidences/pre/
```

Then create the design document at:
```
ai-dev/active/{ID}/{ID}_Issue_Design.md
```

Use the template from `ai-dev/templates/Issue_Design_Template.md`. Fill in ALL sections:

- **Description**: What is broken and expected behavior (2-3 sentences)
- **Severity**: Based on impact assessment
- **Reported By**: Source of the bug report
- **Browser Evidence** (UI-visible only): Reference screenshot and snapshot files from `ai-dev/active/{ID}/evidences/pre/`
- **Steps to Reproduce**: Numbered sequence with Expected/Actual
- **Browser Verification Script** (UI-visible only): Exact Playwright CLI commands to reproduce the bug
- **Root Cause Analysis**: Why this is happening, with file:line references
- **Affected Components**: Table of components, files, and impact
- **Fix Plan**: Agent execution order with step numbers
- **Changes Required**: Specific file changes needed
- **Test to Reproduce**: A failing test proving the bug exists (TDD RED phase)
- **Browser Verification Test** (UI-visible only): Playwright CLI commands to verify the fix works
- **Regression Prevention**: What tests ensure this bug cannot recur

### Test Semantic Correctness Requirement (LESSON FROM I003)

**CRITICAL**: Tests must verify **semantic correctness**, not just **response shape**.

- BAD: `assert "permissions" in data` (only checks key exists)
- BAD: `assert len(data["permissions"]) > 0` (only checks non-empty)
- GOOD: `assert "brands:manage" in data["permissions"]` (checks specific expected value)
- GOOD: `assert "*" not in data["permissions"]` (checks unwanted value is absent)

Every test prompt MUST include a warning about this distinction.

### Agent Selection for Fixes

Incidents are typically simpler than features. Choose the minimum agents needed:

| Root Cause Location | Primary Agent | Notes |
|---------------------|---------------|-------|
| Database schema/query | `Database` | Migration fix or query correction |
| Service/repository logic | `Backend` | Business logic fix |
| API route/wiring | `API` | Endpoint fix |
| Frontend component | `Frontend` | UI fix |
| Pipeline/worker | `Pipeline` | Task processing fix |
| Template rendering | `Template` | Rendering fix |
| Test gap only | `Tests` | Add missing test coverage |

Most incidents need only **1-2 implementation agents**. Don't over-scope.

### Fix Plan Structure

**MANDATORY**: Every incident MUST include a `Tests` agent step that writes:
1. A **reproduction test** — a unit or integration test that fails before the fix and passes after
2. **Regression tests** — tests that ensure this specific bug cannot recur

Typical incident fix plan:

```
S01: {Primary Agent} — Fix the root cause
S02: CodeReview_{Agent} — Review the fix
S03: Tests — Write reproduction test + regression tests
S04: CodeReview_Tests — Review test coverage
S05: CodeReview_Final — Global review
S06..S14: QV Gates — lint, format, typecheck, frontend-tsc, arch-check, security-sast, unit-tests, frontend-tests, integration-tests
S15: QV Browser — Browser verification (only if UI-visible)
```

## Step 5: Generate ALL Prompt Files (only after GO)

Create all prompt files in `ai-dev/active/{ID}/prompts/`.

**IMPORTANT**: Every generated prompt MUST include `Input Files` and `Output Files` sections with paths using the `ai-dev/active/{ID}/` prefix. Reports go in `ai-dev/active/{ID}/reports/`.

### 5a: Implementation Prompts

For each fix agent, create:
```
ai-dev/active/{ID}/prompts/{ID}_S{NN}_{Agent}_prompt.md
```

Using `ai-dev/templates/Implementation_Prompt_Template.md` as the base. **Key differences for incidents**:

- The **Context** section must reference the bug, not a feature
- **Requirements** section describes the FIX, not new functionality
- **TDD Requirement** emphasizes: write the failing test FIRST (proving the bug), then fix it
- Include the **reproduction test** from the design document
- If `browser_verification: true`, reference the browser evidence files

### 5b: Tests Prompt (MANDATORY)

Create the `Tests` prompt. The Tests prompt MUST require:

1. **Reproduction test** — A unit or integration test that:
   - Would FAIL against the pre-fix code
   - PASSES against the current (fixed) code
2. **Regression tests** — Additional tests covering the root cause path and edge cases
3. **Semantic correctness** — assert specific expected values, not just response shape

**MANDATORY WARNING in Tests prompt** (include verbatim):
```
### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed.
But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert "permissions" in data` (shape only)
- GOOD: `assert "brands:manage" in permissions` (semantic — verifies specific expected value)
- GOOD: `assert "*" not in permissions` (semantic — verifies unwanted value is absent)
```

### 5c: Per-Agent Code Review Prompts

After each fix step AND the Tests step, create `CodeReview_{Agent}_prompt.md` files.

### 5d: Global Code Review Prompt

Create `CodeReview_Final_prompt.md`. The global review MUST verify:
- Reproduction test exists and correctly targets the bug scenario
- Tests verify semantic correctness, not just shape

### 5e: Quality Validation Steps

QV gates are **script-driven** — no QV prompt file needed for gate steps.

**If `browser_verification: true`**, create a browser verification prompt.

## Step 5b: Generate Workflow Manifest (only after GO)

Create `ai-dev/active/{ID}/workflow-manifest.json` (step definitions only — state lives in DB):

```json
{
  "id": "{ID}",
  "type": "Issue",
  "title": "{One-line summary of the bug}",
  "browser_verification": true,
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

**QV gate steps**:
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

## Step 6: Register in Platform

After all files are created, register the item in the database:

```bash
iw register {ID} "{One-line summary of the bug}" \
  --type incident \
  --design-doc ai-dev/active/{ID}/{ID}_Issue_Design.md \
  --steps-from ai-dev/active/{ID}/workflow-manifest.json
```

This records the item and all its workflow steps in the database. The item starts in `draft` status.

## Step 7: Present Package for Review

Display a summary of everything created:

```markdown
## Incident Package: {ID} — {Title}

### UI Visibility
{UI-visible / Backend-only} — Browser verification: {Yes / No}

### Root Cause
{Brief root cause summary with file:line reference}

### Design Document
- `ai-dev/active/{ID}/{ID}_Issue_Design.md`

### Workflow Manifest
- `ai-dev/active/{ID}/workflow-manifest.json`

### Execution Plan
| Step | File | Type |
|------|------|------|
| S01 | `{ID}_S01_{Agent}_prompt.md` | Fix Implementation |
| ... | ... | ... |

### Next Steps
1. Review the design document and all prompts
2. When ready: `iw approve {ID}`
3. To execute: `iw batch-create {ID}` → `iw batch-approve BATCH-{NNN}`
4. Monitor: dashboard at http://localhost:9900 or `iw item-status {ID}`
```

---

## Constraints

- **MUST** ALWAYS interact with the user in Step 2a — NEVER skip the conversation
- **MUST** obtain explicit GO from the user in Step 3 before creating ANY files
- **MUST** NOT create, write, or modify any files until after the GO/NO-GO checkpoint is passed
- **MUST** NEVER implement code — this skill ONLY creates documentation
- **MUST** perform root cause analysis before writing the design document
- **MUST** classify bugs as UI-visible or backend-only before creating prompts
- **MUST** include a reproduction test in the design document
- **MUST** include a `Tests` agent step in every incident execution plan
- **MUST** require the Tests prompt to produce both a reproduction test AND regression tests
- **MUST** call `iw register` at the end (Step 6) to record in the database
- **MUST** create ALL files (design + all prompts) in a single session
- **MUST** use the exact file naming convention: `{ID}_S{NN}_{Agent}_prompt.md`
- **MUST** keep the fix scope minimal — fix the bug, don't refactor
- **NEVER** skip CodeReview steps
- **NEVER** skip CodeReview_Final or QV gate steps
- **NEVER** skip Browser Verification for UI-visible bugs
- **NEVER** place files in `done/` — all new files go in `ai-dev/active/`
- **NEVER** start implementation — this skill only creates the fix package
- **NEVER** write tests that only check response shape — always verify semantic correctness
