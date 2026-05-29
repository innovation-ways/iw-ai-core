---
name: iw-new-feature
version: "2.3.0"
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

Use the template from `ai-dev/templates/Feature_Design_Template.md`. Fill in ALL sections (every one below is required):

- **Metadata block** — Type, Priority, Created, Status
- **Description** — what this feature does (2-3 sentences)
- **Project Context** — one-liner pointing reviewers/agents to the project's `CLAUDE.md` (architecture, conventions, hard rules)
- **Scope** — in scope / out of scope (concrete deliverables, not prose)
- **Implementation Plan** — agent steps table with parallelism + Database/API/Frontend change summaries
- **File Manifest** — table of every file to create/modify (design doc, manifest, each prompt). The batch planner uses these paths for conflict detection — a doc with zero file paths is invisible to overlap analysis
- **Acceptance Criteria** — one Given/When/Then block per criterion (AC1, AC2, …)
- **Boundary Behavior** — edge cases table; every row becomes a mandatory test case
- **Invariants** — numbered list of conditions that must hold true after implementation; each maps to a test
- **Dependencies** — Depends on / Blocks (F/I/CR numbers or "None")
- **TDD Approach** — unit / integration / edge-case test strategy
- **Notes** — additional context, risks, or decisions (never leave blank; use "None" if truly empty)

Also create the **Functional Design Document** at the same time (substep within this step):

```
ai-dev/active/{ID}/{ID}_Functional.md
```

Copy `ai-dev/templates/Functional_Design_Template.md` and fill in the four sections using:
- **Why** — drafted from the user's intake conversation and the technical design's Description.
- **What Changed (for the User)** — drafted from the Scope / Acceptance Criteria sections of the technical design.
- **How It Behaves** — drafted from Boundary Behavior and functional acceptance criteria.
- **Out of Scope** — drafted from the Out of Scope section of the technical design (omit entirely if scope is obvious).

**Rules for the functional doc**:
- Keep the body at most 500 words (the review skill blocks >500 as a blocking error).
- Use plain English — no file paths, class names, SQL, or code fences.
- Focus on observable behaviour, not implementation mechanics.
- Do NOT use fenced code blocks (```) — they trigger a review warning.
- Do NOT mention specific paths like `orch/`, `dashboard/`, `scripts/` — they trigger a review warning.

Add the functional doc to the **File Manifest** table (after the Feature_Design.md row):

| File | Type | Purpose |
|------|------|---------|
| `{ID}_Feature_Design.md` | Design | This document |
| `{ID}_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/{ID}_S01_{Agent}_prompt.md` | Prompt | S01 implementation instructions |
| ... | ... | ... (one per step) |

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

### Step-Size Guidance

Follow the **canonical step-granularity rule** in `skills/iw-workflow/SKILL.md`: each implementation step targets **one cohesive concern** (roughly one module or one closely-related file group); multi-concern work is split across multiple steps. Many small steps are preferred over one large step — a single step bundling unrelated work is the primary failure mode.

Also follow the **canonical Verification Placement Rule** in `skills/iw-workflow/SKILL.md`: never make a full test suite or aggregate quality gate (`make quality`, `make check`, `make test-*`) a completion gate or acceptance criterion of an **implementation** step. Test execution belongs to a dedicated `tests-impl` step; full-suite/aggregate-gate verification belongs to the `qv-gate` steps. When the feature's deliverable *is* a gate or a verification behavior, the demonstration is its **own** `tests-impl`/`qv-gate` step — not a clause inside the implementation step. Map each Acceptance Criterion that asserts "gate/suite passes" to a `tests-impl`/`qv-gate` step, never to a `*-impl` implementation step. (See CR-00092 / I-00117.)

Apply this checklist to every step you propose in the manifest:

- Does this step touch more than one unrelated area / module? → **split it**.
- Would the step's description need more than a handful of unrelated numbered sub-deliverables? → **split it**.
- Do docs, skill, or plan updates ride along with code changes in this step? → **give them their own step**.
- Would one agent run have to read + edit + test across several modules? → **split it**.

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

To create the prompt file, **copy `ai-dev/templates/QVBrowser_Prompt_Template.md`** (synced from `templates/design/` by `iw init-project` / `iw sync-templates`) to `ai-dev/active/{ID}/prompts/{ID}_S{N}_BrowserVerification_prompt.md` and fill in ONLY the `{{ID}}`, `{{STEP}}`, `{{TITLE}}`, `{{TYPE}}`, input-files list, and V1..V(n) sections with concrete acceptance criteria from the feature design. Leave the Environment, Prerequisites, Pass Criteria, Report, and Result Contract sections untouched.

**Hard rules for the QV Browser prompt:**
- **NEVER** hardcode URLs, ports, or credentials. No `localhost:5173`, no `localhost:5174`, no literal passwords. The IW daemon spins up an isolated e2e stack built from the worktree's source and exports `$IW_BROWSER_BASE_URL`, `$IW_BROWSER_E2E_USER`, `$IW_BROWSER_E2E_PASSWORD`, `$IW_ITEM_ID`, and `$IW_STEP_ID` at runtime. Use those env vars (or the equivalent `{{IW_BROWSER_BASE_URL}}` placeholder, which the daemon substitutes at launch).
- **NEVER** instruct the agent to run `make dev`, `make e2e-up`, `docker compose up/down/restart/build`, or any install command — the stack is already up. `docker compose exec app` is allowed and required when re-running the seed after writing a fixture file.
- Use `playwright-cli` exclusively (not `agent-browser`, not direct `chromium.launch()`).
- The V(n) section must include a **No Regressions** verification covering adjacent flows and console-error checks.

## Step 6: Generate ALL Prompt Files (only after GO)

Create all prompt files in `ai-dev/active/{ID}/prompts/`.

Use `ai-dev/templates/` as the base for each prompt type. Reports go in `ai-dev/active/{ID}/reports/`.

## Step 7: Generate Workflow Manifest (only after GO)

Create `ai-dev/active/{ID}/workflow-manifest.json` (step definitions — state lives in DB):

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

```json
{
  "id": "{ID}",
  "type": "Feature",
  "title": "{One-line feature title}",
  "browser_verification": true,
  // set to false for backend-only features (no Frontend step)
  "scope": {
    "allowed_paths": [
      "path/to/file_the_feature_touches.py",
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

`scope.allowed_paths` declares every file the feature is permitted to touch, as globs. The executor's `worktree_commit.sh` Step 2.25 enforces this at merge time — any modified file outside the list (plus the implicit `ai-dev/active/{ID}/**` and `ai-dev/archive/{ID}/**`) blocks the merge. Derive the list from the Feature Design's **Files Changed** section. Patterns: exact path, `dir/**` for a whole subtree, `dir/*.py` for fnmatch. If a QV fix-cycle legitimately needs a new file, the operator amends this list and re-triggers the merge — silent scope expansion is no longer possible.

QV gate steps (add after CodeReview_Final) — **IMPORTANT: Only include gates whose commands exist in the project.**

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

> **Migration generation convention (CR-00091)**: database-impl agents MUST call
> `make migration-pending MSG="describe change"` to generate the migration file.
> This sets `down_revision = "PENDING"` as a sentinel; `migration_rebase.py` resolves
> it to the real chain head at merge time, and `make migration-check` resolves it
> before running the round-trip test. Do NOT call `alembic revision --autogenerate`
> directly — it bakes in a revision ID that may be stale by merge time.

### Migration validation (when the feature has a Database step)

If the feature changes database schema (a `Database` agent step writing to `orch/db/migrations/versions/**`), insert a `migration-check` qv-gate step **immediately after the Database step (and after any `CodeReview_Database` step)** so a broken migration is caught before downstream agents inherit the wrong schema.

```json
{"step": "S{N}", "agent": "qv-gate", "gate": "migration-check", "command": "make migration-check", "description": "QV: Alembic migration round-trip + drift check"}
```

This runs `tests/integration/test_migrations_round_trip.py` against a fresh testcontainer and asserts:
- `alembic upgrade head` from base succeeds (catches missing revision ids, broken `down_revision`, runtime DDL errors).
- The alembic-built schema matches `Base.metadata.create_all()` (catches model↔migration drift — the F-00079 / S19 root cause).
- `downgrade base` then `upgrade head` succeeds (catches broken `downgrade()` bodies that would freeze the merge queue on Phase-3 rollback).

Putting this gate early shortens the feedback loop by ≈90% of the work item's compute — without it, drift is only caught at S18 (`make test-integration`) or, worse, at the merge-queue dry-run.

## Step 8: Register in Platform

After all files are created, register the item in the database:

```bash
iw register {ID} "{One-line feature title}" \
  --type feature \
  --design-doc ai-dev/active/{ID}/{ID}_Feature_Design.md \
  --steps-from ai-dev/active/{ID}/workflow-manifest.json
```

**Note**: The `iw register` command auto-detects a sibling `<ID>_Functional.md` file next to the technical design doc and loads its content into the `functional_doc_content` column (S02's work). No extra `--functional-doc` flag is needed when the functional doc lives alongside the technical design doc.

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
- **MUST** inject the self_assess step iff the project's `projects.toml` has `self_assess = true`. Determinism is required (Invariant 6 in F-00078).
