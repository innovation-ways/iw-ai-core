---
name: iw-new-incident
version: "2.2.0"
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

Use the template from `ai-dev/templates/Issue_Design_Template.md`. Fill in ALL sections (every one below is required — mark optional browser sub-sections N/A when backend-only):

- **Metadata block** — Type, Severity, Created, Reported By, Status
- **Description** — what is broken and user-visible impact (2-3 sentences)
- **Project Context** — one-liner pointing to the project's `CLAUDE.md` (architecture, conventions, hard rules)
- **Browser Evidence** (UI-visible only) — reference screenshot and snapshot files from `ai-dev/active/{ID}/evidences/pre/`
- **Steps to Reproduce** — numbered sequence, plus explicit **Expected** / **Actual** lines
- **Browser Verification Script** (UI-visible only) — exact Playwright CLI commands to reproduce the bug
- **Root Cause Analysis** — why the bug occurs, with concrete `file:line` references
- **Affected Components** — table of components, files, and impact
- **Fix Plan** — agent execution order table (must include a `tests-impl` step; see Fix Plan Structure below)
- **File Manifest** — table of every file to create/modify (design, manifest, prompts). The batch planner uses these paths for overlap analysis
- **Test to Reproduce** — a failing test that proves the bug exists (TDD RED phase)
- **Browser Verification Test** (UI-visible only) — Playwright CLI commands that verify the fix
- **Acceptance Criteria** — Given/When/Then blocks. Every incident must have at least: AC1 "Bug is fixed" and AC2 "Regression test exists"
- **Regression Prevention** — what structural changes, validations, or tests prevent this class of bug from recurring
- **Dependencies** — Depends on / Blocks (F/I/CR numbers or "None")
- **TDD Approach** — reproducing test, unit tests, integration tests
- **Notes** — additional context, risks, or decisions (use "None" if truly empty)

Also create the **Functional Design Document** at the same time (substep within this step):

```
ai-dev/active/{ID}/{ID}_Functional.md
```

Copy `ai-dev/templates/Functional_Design_Template.md` and fill in the four sections using:
- **Why** — drafted from the user's intake conversation and the technical design's Description / Bug Description.
- **What Changed (for the User)** — drafted from the Steps to Reproduce and Acceptance Criteria sections.
- **How It Behaves** — drafted from the fix's expected behaviour and edge cases.
- **Out of Scope** — drafted from the Regression Prevention or any explicitly out-of-scope items (omit if obvious).

**Rules for the functional doc**:
- Keep the body at most 500 words (the review skill blocks >500 as a blocking error).
- Use plain English — no file paths, class names, SQL, or code fences.
- Focus on observable behaviour, not implementation mechanics.
- Do NOT use fenced code blocks (```) — they trigger a review warning.
- Do NOT mention specific paths like `orch/`, `dashboard/`, `scripts/` — they trigger a review warning.

Add the functional doc to the **File Manifest** table (add a row after Issue_Design.md):

| File | Type | Purpose |
|------|------|---------|
| `{ID}_Issue_Design.md` | Design | This document |
| `{ID}_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions |
| `prompts/{ID}_S01_{Agent}_prompt.md` | Prompt | S01 fix implementation |
| ... | ... | ... (one per step) |

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
4. **Targeted verification only** — the Tests prompt's "Test Verification"
   section MUST run only the new test file the agent created
   (`uv run pytest path/to/new_test_file.py -v`). It MUST NOT call
   `make test-integration` or `make test-unit` — full-suite execution is
   owned by the downstream QV gates (`unit-tests`, `integration-tests`).
   Duplicating it inside the Tests step routinely blows the step's
   timeout budget (see I-00073/S03 post-mortem, 2026-05-08).
5. **No manual revert RED-check inside this step** — if you want to verify
   the suite would have caught the bug pre-fix, that is a *design-time*
   exercise (the human authoring the design proves the bug existed by
   running the failing test against pre-fix HEAD before writing the
   prompt). Do not instruct the agent to `git checkout HEAD~1 -- ...`,
   `git stash`, or otherwise revert source files at runtime — that is a
   thrash-prone operation, not a verification.

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

**If `browser_verification: true`**, create a browser verification prompt at `ai-dev/active/{ID}/prompts/{ID}_S{N}_BrowserVerification_prompt.md` and reference it from the workflow manifest:

```json
{"step": "S{N}", "agent": "qv-browser", "description": "QV: Browser verification — verify fix end-to-end in isolated worktree stack", "prompt": "prompts/{ID}_S{N}_BrowserVerification_prompt.md"}
```

To create the prompt file, **copy `ai-dev/templates/QVBrowser_Prompt_Template.md`** (synced from `templates/design/` by `iw init-project` / `iw sync-templates`) and fill in ONLY the `{{ID}}`, `{{STEP}}`, `{{TITLE}}`, `{{TYPE}}`, input-files list, and V1..V(n) sections. The V(n) verifications must cover:

1. **The reproduction case** — navigate to the exact URL/interaction that triggered the bug and verify it now behaves correctly.
2. **Adjacent flows (No Regressions)** — confirm the fix didn't break neighboring functionality, and no new console errors appeared.

Leave the Environment, Prerequisites, Pass Criteria, Report, and Result Contract sections of the template untouched.

**Hard rules for the QV Browser prompt:**
- **NEVER** hardcode URLs, ports, or credentials. No `localhost:5173`, no `localhost:5174`, no literal passwords. The IW daemon spins up an isolated e2e stack built from the worktree's source and exports `$IW_BROWSER_BASE_URL`, `$IW_BROWSER_E2E_USER`, `$IW_BROWSER_E2E_PASSWORD`, `$IW_ITEM_ID`, and `$IW_STEP_ID` at runtime. Use those env vars (or the equivalent `{{IW_BROWSER_BASE_URL}}` placeholder, which the daemon substitutes at launch).
- **NEVER** instruct the agent to run `make dev`, `make e2e-up`, `docker compose up/down/restart/build`, or any install command — the stack is already up. `docker compose exec app` is allowed and required when re-running the seed after writing a fixture file.
- Use `playwright-cli` exclusively (not `agent-browser`, not direct `chromium.launch()`).

## Step 5b: Generate Workflow Manifest (only after GO)

Create `ai-dev/active/{ID}/workflow-manifest.json` (step definitions only — state lives in DB):

### Sub-step: Check project self_assess flag

Read the project's `projects.toml` entry to see if `self_assess = true`:

```bash
project_id=$(uv run iw current-project)
self_assess=$(python3 -c "import tomllib, sys; data = tomllib.loads(open('projects.toml').read()); print(data.get('projects', {}).get('$project_id', {}).get('self_assess', False))")
```

If `self_assess` is `True`, you MUST inject the following step into `workflow-manifest.json` as the **LAST step** — after the final `qv-gate` step AND after any `qv-browser` step:

```json
{
  "step": "S{NN}",
  "agent": "self-assess-impl",
  "step_type": "self_assess",
  "description": "Self-assessment of the just-completed item via the iw-item-analyze skill",
  "prompt": "prompts/{ID}_S{NN}_SelfAssess_prompt.md"
}
```

Why last: self_assess analyzes the item's full execution history (retries, fix cycles, agent thrash). If it runs before qv-gate / qv-browser, every retry caused by lint, format, type-check, security-sast, unit-tests, integration-tests, or browser verification is invisible to it — producing misleading "ran cleanly" reports for items that actually had multiple gate failures.

The agent slug is `self-assess-impl` — registered in `skills/iw-workflow/SKILL.md`'s canonical agent table and in `executor/step_executor_lib.sh`. Do NOT use `self-assess` or `self_assess` as the agent slug — those will fail orchestrator validation.

And generate the corresponding prompt file at `prompts/{ID}_S{NN}_SelfAssess_prompt.md` by copying `ai-dev/templates/SelfAssess_Prompt_Template.md` and substituting `{ID}` and `{NN}`.

No renumbering is needed when self_assess is the final step.

---

Then create the manifest:
  "browser_verification": true,
  "scope": {
    "allowed_paths": [
      "path/to/file_the_fix_modifies.py",
      "tests/integration/path/to/new_test_file.py"
    ]
  },
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

`scope.allowed_paths` declares the exact set of files the fix is permitted to touch, as globs. The executor's `worktree_commit.sh` Step 2.25 enforces this at merge time — any modified file outside the list (plus the implicit `ai-dev/active/{ID}/**` and `ai-dev/archive/{ID}/**`) blocks the merge. Derive the list from the Incident Design's **Files Changed** section. Patterns:

- `"path/to/file.py"` — exact match
- `"dir/**"` — the directory and everything below it
- `"dir/*.py"` — single-level wildcard (fnmatch)

If a QV fix-cycle legitimately needs to touch a new file (e.g. the fix can't avoid it), the operator amends this list and re-triggers the merge — don't silently expand.

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

**QV gate steps — IMPORTANT: Only include gates whose commands exist in the project.**

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

### Migration validation (when the incident touches database schema)

If the fix involves a new alembic migration (any change under `orch/db/migrations/versions/**`), insert a `migration-check` qv-gate step **immediately after the Database step** so a broken migration is caught before downstream agents inherit the wrong schema:

```json
{"step": "S{N}", "agent": "qv-gate", "gate": "migration-check", "command": "make migration-check", "description": "QV: Alembic migration round-trip + drift check"}
```

This runs `tests/integration/test_migrations_round_trip.py` against a fresh testcontainer and asserts: upgrade-from-base succeeds, alembic schema == `Base.metadata.create_all()` schema, and downgrade-then-upgrade round-trips. Missing this gate means model↔migration drift is only caught at `make test-integration` or at the merge-queue dry-run.

## Step 6: Register in Platform

After all files are created, register the item in the database:

```bash
iw register {ID} "{One-line summary of the bug}" \
  --type incident \
  --design-doc ai-dev/active/{ID}/{ID}_Issue_Design.md \
  --steps-from ai-dev/active/{ID}/workflow-manifest.json
```

This records the item and all its workflow steps in the database. The item starts in `draft` status.

**Note**: The `iw register` command auto-detects a sibling `<ID>_Functional.md` file next to the technical design doc and loads its content into the `functional_doc_content` column (S02's work). No extra `--functional-doc` flag is needed when the functional doc lives alongside the technical design doc.

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
- **MUST** inject the self_assess step iff the project's `projects.toml` has `self_assess = true`. Determinism is required (Invariant 6 in F-00078).
