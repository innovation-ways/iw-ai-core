---
name: iw-new-cr
version: "2.3.0"
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

If the change affects what users see in the browser (Frontend layer affected), mark `browser_verification: true` and capture browser evidence of the **current state** before proposing changes.

**When `browser_verification: true`** — MANDATORY before GO:

1. Check dev environment health:
   ```bash
   ./innoforge.sh --health
   ```

2. Navigate to the affected area and screenshot the current behavior:
   ```bash
   playwright-cli open http://localhost:5173
   # Navigate to the affected page/component
   playwright-cli screenshot ai-dev/active/{ID}/evidences/pre/{ID}-before.png
   playwright-cli close
   ```

3. Record the evidence status for the GO/NO-GO checkpoint:
   - `Captured` — screenshot saved to `evidences/pre/`
   - `Deferred` — dev environment not running (note in design doc)
   - `N/A` — no frontend changes (backend-only CR)

**If the dev environment is not running**, skip browser capture and note it as "deferred" in the design document.

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
**Browser Evidence**: {Captured / Deferred / N/A — backend-only}

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
mkdir -p ai-dev/active/{ID}/evidences/pre/
mkdir -p ai-dev/active/{ID}/evidences/post/
```

Then create the design document at:
```
ai-dev/active/{ID}/{ID}_CR_Design.md
```

Use the template from `ai-dev/templates/CR_Design_Template.md`. Fill in ALL sections (every one below is required):

- **Metadata block** — Type, Priority, Reason, Created, Status
- **Description** — what is being changed and why (2-3 sentences)
- **Project Context** — one-liner pointing to the project's `CLAUDE.md` (architecture, conventions, hard rules)
- **Current Behavior** — how the system works today in the area being changed (separate section — do NOT collapse with Desired Behavior)
- **Desired Behavior** — how the system should work after the change (separate section)
- **Impact Analysis** — Affected Components table, Breaking Changes, Data Migration (including reversibility)
- **Implementation Plan** — agent steps table with parallelism + Database/API/Frontend change summaries
- **File Manifest** — table of every file to create/modify (design, manifest, prompts). The batch planner uses these paths for overlap analysis
- **Acceptance Criteria** — one Given/When/Then block per criterion (AC1, AC2, …)
- **Rollback Plan** — how to revert: Database (reverse migration / manual SQL / N/A), Code (revert commit / feature flag), Data (no loss / backup restore)
- **Dependencies** — Depends on / Blocks (F/I/CR numbers or "None")
- **TDD Approach** — unit tests, integration tests, existing tests that need updating
- **Notes** — additional context, risks, or decisions (use "None" if truly empty)

Also create the **Functional Design Document** at the same time (substep within this step):

```
ai-dev/active/{ID}/{ID}_Functional.md
```

Copy `ai-dev/templates/Functional_Design_Template.md` and fill in the four sections using:
- **Why** — drafted from the user's intake conversation and the technical design's Description.
- **What Changed (for the User)** — drafted from Current Behavior → Desired Behavior and Acceptance Criteria.
- **How It Behaves** — drafted from the change's expected behaviour and edge cases.
- **Out of Scope** — drafted from the Out of Scope section (omit if obvious).

**Rules for the functional doc**:
- Keep the body at most 500 words (the review skill blocks >500 as a blocking error).
- Use plain English — no file paths, class names, SQL, or code fences.
- Focus on observable behaviour, not implementation mechanics.
- Do NOT use fenced code blocks (```) — they trigger a review warning.
- Do NOT mention specific paths like `orch/`, `dashboard/`, `scripts/` — they trigger a review warning.

Add the functional doc to the **File Manifest** table (add a row after CR_Design.md):

| File | Type | Purpose |
|------|------|---------|
| `{ID}_CR_Design.md` | Design | This document |
| `{ID}_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions |
| `prompts/{ID}_S01_{Agent}_prompt.md` | Prompt | S01 implementation instructions |
| ... | ... | ... (one per step) |

## Step 6: Generate ALL Prompt Files (only after GO)

Create all prompt files in `ai-dev/active/{ID}/prompts/`.

### Step-Size Guidance

Follow the **canonical step-granularity rule** in `skills/iw-workflow/SKILL.md`: each implementation step targets **one cohesive concern** (roughly one module or one closely-related file group); multi-concern work is split across multiple steps. Many small steps are preferred over one large step — a single step bundling unrelated work is the primary failure mode.

Apply this checklist to every step you propose in the manifest:

- Does this step touch more than one unrelated area / module? → **split it**.
- Would the step's description need more than a handful of unrelated numbered sub-deliverables? → **split it**.
- Do docs, skill, or plan updates ride along with code changes in this step? → **give them their own step**.
- Would one agent run have to read + edit + test across several modules? → **split it**.

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
  "type": "ChangeRequest",
  "title": "{One-line CR title}",
  "browser_verification": true,
  // set to false for backend-only CRs (no Frontend step)
  "scope": {
    "allowed_paths": [
      "path/to/file_the_cr_modifies.py",
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

`scope.allowed_paths` declares every file the CR is permitted to touch, as globs. The executor's `worktree_commit.sh` Step 2.25 enforces this at merge time — any modified file outside the list (plus the implicit `ai-dev/active/{ID}/**` and `ai-dev/archive/{ID}/**`) blocks the merge. Derive the list from the CR Design's **Files Changed** section. Patterns: exact path, `dir/**` for a whole subtree, `dir/*.py` for fnmatch. If a QV fix-cycle legitimately needs a new file, the operator amends this list and re-triggers the merge — silent scope expansion is no longer possible.

Add QV gate steps after CodeReview_Final (same as iw-new-incident pattern).

> **Migration generation convention (CR-00091)**: database-impl agents MUST call
> `make migration-pending MSG="describe change"` to generate the migration file.
> This sets `down_revision = "PENDING"` as a sentinel; `migration_rebase.py` resolves
> it to the real chain head at merge time, and `make migration-check` resolves it
> before running the round-trip test. Do NOT call `alembic revision --autogenerate`
> directly — it bakes in a revision ID that may be stale by merge time.

### Migration validation (when the CR touches database schema)

If the CR involves a new alembic migration (any change under `orch/db/migrations/versions/**`), insert a `migration-check` qv-gate step **immediately after the Database step** so a broken migration is caught before downstream agents inherit the wrong schema:

```json
{"step": "S{N}", "agent": "qv-gate", "gate": "migration-check", "command": "make migration-check", "description": "QV: Alembic migration round-trip + drift check"}
```

This runs `tests/integration/test_migrations_round_trip.py` against a fresh testcontainer: upgrade-from-base, schema parity vs `Base.metadata.create_all()`, and downgrade-then-upgrade round-trip. Missing this gate means model↔migration drift is only caught at `make test-integration` or at the merge-queue dry-run.

When `browser_verification: true`, add a QV Browser step after all QV gates:
```json
{"step": "S{N}", "agent": "qv-browser", "description": "QV: Browser verification — verify change end-to-end in isolated worktree stack", "prompt": "prompts/{ID}_S{N}_BrowserVerification_prompt.md"}
```

To create the prompt file, **copy `ai-dev/templates/QVBrowser_Prompt_Template.md`** (synced from `templates/design/` by `iw init-project` / `iw sync-templates`) to `ai-dev/active/{ID}/prompts/{ID}_S{N}_BrowserVerification_prompt.md` and fill in ONLY the `{{ID}}`, `{{STEP}}`, `{{TITLE}}`, `{{TYPE}}`, input-files list, and V1..V(n) sections with concrete acceptance criteria for the change. Leave the Environment, Prerequisites, Pass Criteria, Report, and Result Contract sections untouched.

**Hard rules for the QV Browser prompt:**
- **NEVER** hardcode URLs, ports, or credentials. No `localhost:5173`, no `localhost:5174`, no literal passwords. The IW daemon spins up an isolated e2e stack built from the worktree's source and exports `$IW_BROWSER_BASE_URL`, `$IW_BROWSER_E2E_USER`, `$IW_BROWSER_E2E_PASSWORD`, `$IW_ITEM_ID`, and `$IW_STEP_ID` at runtime. Use those env vars (or the equivalent `{{IW_BROWSER_BASE_URL}}` placeholder, which the daemon substitutes at launch).
- **NEVER** instruct the agent to run `make dev`, `make e2e-up`, `docker compose up/down/restart/build`, or any install command — the stack is already up. `docker compose exec app` is allowed and required when re-running the seed after writing a fixture file.
- Use `playwright-cli` exclusively (not `agent-browser`, not direct `chromium.launch()`).
- Include a **No Regressions** verification (V(n)) covering adjacent flows and console-error checks.

## Step 8: Register in Platform

After all files are created, register the item in the database:

```bash
iw register {ID} "{One-line CR title}" \
  --type cr \
  --design-doc ai-dev/active/{ID}/{ID}_CR_Design.md \
  --steps-from ai-dev/active/{ID}/workflow-manifest.json
```

**Note**: The `iw register` command auto-detects a sibling `<ID>_Functional.md` file next to the technical design doc and loads its content into the `functional_doc_content` column (S02's work). No extra `--functional-doc` flag is needed when the functional doc lives alongside the technical design doc.

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
- **MUST** inject the self_assess step iff the project's `projects.toml` has `self_assess = true`. Determinism is required (Invariant 6 in F-00078).
