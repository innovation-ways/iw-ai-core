# Post-Merge Quality Gate & AI Fix Cycle — Implementation Plan

**Date**: 2026-03-30
**Status**: Draft
**Research**: `docs/research/41-AI_GIT_MERGE_AUTOMATION.md`

---

## Problem Statement

The batch dispatcher (`scripts/batch_dispatcher.sh`) currently squash-merges completed
worktrees to main immediately after `git merge --squash` succeeds. No post-merge validation
runs. When parallel agents modify overlapping files, merges either fail outright (textual
conflicts) or succeed but break tests (semantic conflicts). BATCH-054 is a concrete example:
F140 and I120 both had `merge.status: "failed"`, requiring manual intervention on all 5 items.

## Solution Overview

Replace the current "merge and hope" flow with a **sequential merge queue** that validates
every merge through the full quality gate pipeline, using an AI agent to fix failures
automatically (up to 5 retries).

### Current Flow (what exists today)

```
Item completes → squash merge → commit → cleanup worktree → done
                 (no tests)     (no validation)
```

### New Flow

```
Item completes → status = "completed"
                      ↓
              MERGE JOB (sequential, one at a time)
                      ↓
              a. Squash merge to main
                 → if textual conflict: invoke LLM to resolve
                 → if LLM fails: status = "conflict_needs_human", BLOCK queue
                      ↓
              b. Alembic heads check
                 → if multi-head: invoke LLM to fix revision chain
                      ↓
              c. Gate 1: make quality (ruff, mypy, bandit, import-linter, docs-check)
                 → fail: invoke LLM fix agent (up to 5 retries)
                      ↓
              d. Gate 2: make test (pytest unit + integration + coverage)
                 → fail: invoke LLM fix agent (up to 5 retries)
                      ↓
              e. Gate 3: frontend checks (lint, typecheck, build)
                 → fail: invoke LLM fix agent (up to 5 retries)
                      ↓
              f. Commit all fixes + status = "merged"
                      ↓
              g. Cleanup worktree + branch
                      ↓
              Next item in queue proceeds
```

If any gate exhausts its 5 fix retries:
- Status = `needs_human`
- Merge stays on main (dirty state)
- Queue is **blocked** — no further merges until human intervenes

---

## Batch Manifest Schema Changes

### New Fields

```json
{
  "merge_agent": "claude",           // NEW — independent from cli_tool
  "items": [
    {
      "merge": {
        "status": "in_progress|completed|failed|conflict_needs_human|needs_human",
        "fix_cycles": 0,             // NEW — count of AI fix attempts
        "fix_log": "...merge_fix.log", // NEW — log of fix agent output
        "gates": {                   // NEW — per-gate tracking
          "alembic": { "status": "passed|failed|fixed|skipped", "attempts": 0 },
          "quality": { "status": "passed|failed|fixed", "attempts": 0 },
          "test":    { "status": "passed|failed|fixed", "attempts": 0 },
          "frontend":{ "status": "passed|failed|fixed", "attempts": 0 }
        },
        "conflict_resolution": {     // NEW — only present if conflicts occurred
          "method": "llm",
          "files_resolved": [],
          "model": "claude-sonnet-4-6"
        }
      }
    }
  ]
}
```

### New Item Statuses

| Status | Meaning |
|--------|---------|
| `completed` | Agent finished work in worktree, awaiting merge |
| `merging` | Merge job in progress (exists today) |
| `merged` | All gates passed, committed to main (exists today) |
| `conflict_needs_human` | NEW — textual conflict that LLM could not resolve |
| `needs_human` | NEW — gate fix cycles exhausted (5 retries) |
| `blocked` | NEW — waiting for a needs_human item ahead in queue |

---

## Implementation Phases

### Phase 1: Core Merge Job Script (`scripts/merge_job.sh`)

**What**: Extract merge logic from `batch_dispatcher.sh` into a standalone, testable script
that implements the full merge-validate-fix pipeline.

**Files to create**:
- `scripts/merge_job.sh` — the main merge job script

**Files to modify**:
- `scripts/batch_dispatcher.sh` — replace `merge_item()` with a call to `merge_job.sh`

**Detailed requirements**:

The `merge_job.sh` script receives these arguments:
- `$1` — item_id (e.g., `I120`)
- `$2` — repo root path
- `$3` — batch manifest path
- `$4` — merge agent (`claude` or `opencode`)

It performs these steps in order:

#### Step a: Squash Merge

1. Read branch name using the same multi-source fallback as current `merge_item()` (worktree
   manifest → main manifest → done/ → naming convention)
2. Run `scripts/worktree_commit.sh` to commit any uncommitted worktree changes
3. Run `scripts/worktree_verify.sh` for health check
4. `git checkout main`
5. Verify branch exists (`git rev-parse --verify`)
6. Check for conflicts: `git merge-tree "$merge_base" main "$branch"`
7. If no conflicts: `git merge --squash "$branch"` — proceed to step b
8. If conflicts detected: attempt LLM resolution (see Step a.1)
9. If merge command itself fails (unexpected): status = `failed`, return 1

#### Step a.1: LLM Conflict Resolution

When `git merge --squash` fails due to conflicts:

1. Collect all conflicted files: `git diff --name-only --diff-filter=U`
2. For each conflicted file, extract the full file content (it contains `<<<<<<<` markers)
3. Get the merge base version of each file: `git show $merge_base:$file`
4. Construct a prompt (written to a temp file):

```
You are resolving git merge conflicts on the InnoForge project.
Work item: {item_id}
Design document: ai-dev/work/{item_id}/{item_id}_*_Design.md

The following files have merge conflicts after squash-merging branch {branch} into main.
For each file, I provide the current conflicted content (with <<<<<<< markers) and the
merge base version (the common ancestor).

YOUR TASK: For each file, output the fully resolved content. Both sides' intent must be
preserved — combine the changes, do not discard either side's work.

RULES:
- Output ONLY the resolved file content, no explanations
- Do NOT include any <<<<<<< , =======, or >>>>>>> markers
- Do NOT add new features or refactor code
- Do NOT modify files that are not listed here
- After resolving, run: git add <each resolved file>

## Conflicted Files

### File: {path}
#### Current (conflicted):
```
{conflicted content}
```
#### Merge base (ancestor):
```
{ancestor content}
```

(repeat for each conflicted file)
```

5. Invoke the configured merge agent:
   - `claude -p "$(cat $prompt_file)" --permission-mode bypassPermissions`
   - `opencode run "$(cat $prompt_file)"`
6. After agent runs, check if conflicts remain: `git diff --name-only --diff-filter=U`
7. If conflicts remain: `git merge --abort`, status = `conflict_needs_human`, BLOCK queue
8. If resolved: `git add -A`, proceed to step b

**Important**: The LLM works directly on main. The conflicted files are already in the
working tree. The agent's edits resolve the markers in place. We then `git add` the
resolved files and continue the squash merge.

#### Step b: Alembic Heads Check

1. Run: `alembic heads --resolve-dependencies 2>&1`
2. Count the number of heads (lines of output)
3. If exactly 1 head: pass — proceed to step c
4. If multiple heads detected:
   - Identify which migration files were added by this merge:
     `git diff HEAD~1 --name-only -- migrations/versions/`
   - Construct a fix prompt:

```
You are fixing an Alembic migration multi-head issue on the InnoForge project.
Work item: {item_id}

After merging, Alembic has multiple heads:
{output of alembic heads}

The migration file(s) added by this merge:
{list of new migration files}

The current head on main before this merge was:
{previous alembic head revision}

YOUR TASK:
1. Update the `down_revision` in the newly added migration file(s) to point to the
   current head, creating a linear chain
2. Run `alembic heads` to verify only 1 head remains
Verification is now automatic: the daemon's merge pipeline dry-runs the
migration against a testcontainer before merging. If dry-run fails, the
batch is marked MIGRATION_INVALID and the fix-cycle is triggered.
See docs/IW_AI_Core_Migration_Checklist.md and
docs/IW_AI_Core_Agent_Constraints.md (R2).

RULES:
- Only modify the `down_revision` field in the new migration file(s)
- Do NOT modify existing migrations that were already on main
- Do NOT modify any application code
```

   - Invoke merge agent with this prompt
   - Re-check: `alembic heads --resolve-dependencies`
   - If still multiple heads: status = `needs_human`, BLOCK queue
   - If fixed: proceed to step c

#### Step c: Gate 1 — Quality Checks

1. Run: `make quality 2>&1` (captures output)
2. If exit code 0: pass — record `gates.quality.status = "passed"`, proceed to step d
3. If exit code != 0:
   - Increment `gates.quality.attempts`
   - If attempts > 5: status = `needs_human`, BLOCK queue
   - Construct fix prompt:

```
You are fixing post-merge quality gate failures on the InnoForge project main branch.
Work item: {item_id}
Design document: ai-dev/work/{item_id}/{item_id}_*_Design.md
(Read it to understand WHY this code was changed.)

The squash merge from branch {branch} was applied successfully but quality checks failed.

## Failure Output
{stderr/stdout from make quality}

## Files Changed in This Merge
{output of git diff HEAD~1 --stat}

## Instructions
Fix ONLY the issues shown in the failure output. Do not refactor, do not add features,
do not modify unrelated code. After fixing, run `make quality` to verify.
```

   - Invoke merge agent
   - Re-run `make quality`
   - Loop until pass or attempts exhausted

#### Step d: Gate 2 — Tests

1. Run: `make test 2>&1` (unit + integration + coverage)
2. Same retry logic as Gate 1 but with test-specific prompt:

```
You are fixing post-merge test failures on the InnoForge project main branch.
Work item: {item_id}
Design document: ai-dev/work/{item_id}/{item_id}_*_Design.md
(Read it to understand WHY this code was changed.)

## Failure Output
{stderr/stdout from make test}

## Files Changed in This Merge
{output of git diff HEAD~1 --stat}

## Instructions
Fix ONLY the failing tests or the code causing test failures.
- If a test is wrong (testing outdated behavior), fix the test
- If the code is wrong (broke existing behavior), fix the code
- Do NOT skip or delete tests
- Do NOT modify unrelated tests
After fixing, run `make test` to verify.
```

3. Max 5 attempts. On exhaustion: `needs_human`, BLOCK queue.

#### Step e: Gate 3 — Frontend Checks

1. Run: `make frontend-check 2>&1` (lint + typecheck + build)
2. Same retry logic as Gates 1-2 but with frontend-specific prompt:

```
You are fixing post-merge frontend check failures on the InnoForge project main branch.
Work item: {item_id}
Design document: ai-dev/work/{item_id}/{item_id}_*_Design.md
(Read it to understand WHY this code was changed.)

## Failure Output
{stderr/stdout from make frontend-check}

## Files Changed in This Merge
{output of git diff HEAD~1 --stat}

## Instructions
Fix ONLY the frontend issues shown in the failure output.
- TypeScript errors: fix type mismatches, missing imports, etc.
- ESLint errors: fix lint violations
- Build errors: fix compilation issues
Do NOT modify backend code. Do NOT refactor. After fixing, run `make frontend-check` to verify.
```

3. Max 5 attempts. On exhaustion: `needs_human`, BLOCK queue.

#### Step f: Commit All Fixes

After all gates pass:

1. Stage any files modified by fix agents: `git add -A`
2. Check if there are staged changes (fix agents may have modified files):
   - If changes: `git commit -m "fix({item_id}): post-merge quality fixes"`
3. The original squash merge commit is already on main from step a.
   The fix commit is a separate commit on top.

#### Step g: Cleanup

1. Copy worktree manifest to main (preserve step progress for dashboard)
2. Update workflow manifest status to `"merged"`
3. Commit manifest preservation
4. Remove worktree: `git worktree remove .worktrees/{item_id} --force`
5. Delete branch: `git branch -D {branch}`
6. Release migration lock if held
7. Update batch manifest: `merge.status = "completed"`, `merged_at = now`

#### Logging

All output goes to `ai-dev/work/BATCH-{N}/logs/{item_id}_merge.log`.
Fix agent output goes to `ai-dev/work/BATCH-{N}/logs/{item_id}_merge_fix.log`.
Each fix attempt is appended with a separator:

```
=== FIX ATTEMPT 1/5 — Gate: quality — 2026-03-30T14:22:00 ===
{agent output}
=== END FIX ATTEMPT 1/5 — Exit: 0 ===
```

#### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Merge + all gates passed |
| 1 | Merge failed (no branch, empty branch, unexpected git error) |
| 2 | Conflict that LLM could not resolve (`conflict_needs_human`) |
| 3 | Gate fix cycles exhausted (`needs_human`) |

---

### Phase 2: Dispatcher Integration

**What**: Modify `batch_dispatcher.sh` to use `merge_job.sh` and handle the new statuses.

**Files to modify**:
- `scripts/batch_dispatcher.sh`

**Detailed requirements**:

1. **Replace `merge_item()` body**: Instead of the current 237-line function, call:
   ```bash
   bash "$REPO_ROOT/scripts/merge_job.sh" "$item_id" "$REPO_ROOT" "$MANIFEST" "$MERGE_AGENT"
   ```
   Keep the function wrapper for status updates and logging.

2. **Read `merge_agent` from manifest**: At dispatcher startup (alongside `cli_tool`):
   ```bash
   MERGE_AGENT=$(jq -r '.merge_agent // "claude"' "$MANIFEST")
   ```
   Default to `"claude"` if not set.

3. **Handle new exit codes from merge_job.sh**:
   - Exit 0: set item status `"merged"`, proceed
   - Exit 1: set item status `"failed"`, proceed to next item (non-blocking failure)
   - Exit 2: set item status `"conflict_needs_human"`, BLOCK queue (break main loop)
   - Exit 3: set item status `"needs_human"`, BLOCK queue (break main loop)

4. **Queue blocking logic**: When an item returns exit 2 or 3:
   - Set batch status to `"blocked"`
   - Log the blocking item and reason
   - Stop processing further merges
   - Do NOT stop executing agents in worktrees (they can continue working)
   - The dispatcher continues polling but skips merge processing until the block is cleared

5. **Block clearing**: When the human resolves the issue (manually fixes main, runs tests,
   updates the batch manifest to clear the `needs_human` status), the dispatcher detects the
   status change and resumes merge processing on the next poll cycle.

6. **Group transition**: No change to the existing group logic. Groups already depend on
   all items being `"merged"`. Since the new merge job validates before marking `"merged"`,
   this naturally ensures the next group only starts when the previous group is fully
   validated.

---

### Phase 3: Batch Manifest & Planner Updates

**What**: Add `merge_agent` field to batch creation and manifest schema.

**Files to modify**:
- `scripts/ai_dev_daemon/batch_planner.py` — add `merge_agent` to manifest generation
- `scripts/ai_dev_daemon/batch_manager.py` — read `merge_agent`, pass to merge logic

**Detailed requirements**:

1. **batch_planner.py**: In `generate_batch_manifest()` (around line 334), add:
   ```python
   "merge_agent": "claude",  # default; overridable via dashboard
   ```

2. **batch_manager.py**: In `merge_item()`, read `merge_agent` from batch manifest and
   pass it to the subprocess call (if batch_manager.py also calls merge_job.sh).
   Alternatively, if batch_manager.py keeps its own Python merge logic, add the same
   gate + fix cycle logic in Python. **Recommendation**: have batch_manager.py delegate
   to `merge_job.sh` as well, so there's a single implementation.

3. **Dashboard API** (`scripts/ai_dashboard/server.py`): Add an endpoint to update
   `merge_agent`:
   ```
   POST /api/batch/{batch_id}/merge-agent
   Body: { "merge_agent": "claude" | "opencode" }
   ```
   This writes to the batch manifest JSON.

---

### Phase 4: Dashboard UI Changes

**What**: Add merge agent selector to the dashboard and display merge gate status.

**Files to modify**:
- `scripts/ai_dashboard/templates/agents.html` — add merge agent dropdown to "New Batch" modal
- `scripts/ai_dashboard/templates/batch_detail.html` — show merge agent + gate status per item
- `scripts/ai_dashboard/templates/item_detail.html` — show detailed merge gate info
- `scripts/ai_dashboard/server.py` — add API endpoint for merge agent update
- `scripts/ai_dashboard/scanner.py` — extract merge gate data from manifests

**Detailed requirements**:

#### 4a: New Batch Modal — Merge Agent Selector

In `agents.html`, add a dropdown next to the "Max parallel" selector in the batch creation
modal footer:

```html
<div class="batch-modal-option">
  <label for="merge-agent-input">Merge agent</label>
  <select id="merge-agent-input">
    <option value="claude" selected>Claude Code</option>
    <option value="opencode">OpenCode</option>
  </select>
</div>
```

Update the `createBatch()` JavaScript function to include `merge_agent` in the POST body:
```javascript
var mergeAgent = document.getElementById('merge-agent-input').value;
body: JSON.stringify({ items: ids, max_parallel: maxP, merge_agent: mergeAgent })
```

Update the `/api/batch/create` endpoint in `server.py` to accept and store `merge_agent`.

#### 4b: Batch Detail — Merge Agent Display + Gate Status

In `batch_detail.html`, add merge agent field alongside cli_tool:
```html
<div class="batch-detail-field">
  <label>Merge Agent</label>
  <select onchange="updateMergeAgent('{{ batch.id }}', this.value)">
    <option value="claude" {{ 'selected' if batch.merge_agent == 'claude' }}>Claude Code</option>
    <option value="opencode" {{ 'selected' if batch.merge_agent == 'opencode' }}>OpenCode</option>
  </select>
</div>
```

This is a live dropdown — changing it updates the batch manifest via the API endpoint.
The merge agent can be changed mid-batch (takes effect on the next merge job).

For each item in the items table, show merge gate status:
```html
<td class="merge-gates">
  {% if item.merge and item.merge.gates %}
    {% for gate_name, gate in item.merge.gates.items() %}
      <span class="gate-badge gate-{{ gate.status }}" title="{{ gate_name }}: {{ gate.attempts }} attempts">
        {{ gate_name[0]|upper }}
      </span>
    {% endfor %}
  {% endif %}
</td>
```

Gate badges are single-letter indicators (A=alembic, Q=quality, T=test, F=frontend) with
color coding: green=passed, red=failed, yellow=fixed (passed after fix), gray=skipped.

#### 4c: Item Detail — Merge Fix Log Viewer

In `item_detail.html`, add a collapsible section showing the merge fix log when the merge
involved fix cycles:

```html
{% if item.merge and item.merge.fix_cycles > 0 %}
<div class="collapsible" data-open="false">
  <div class="collapsible-header">
    Merge Fix Log ({{ item.merge.fix_cycles }} fix cycles)
  </div>
  <div class="collapsible-body">
    <div class="log-viewer">
      <pre>{{ item.merge_fix_log_content }}</pre>
    </div>
  </div>
</div>
{% endif %}
```

#### 4d: Scanner Updates

In `scanner.py`, when reading batch manifests, extract the new merge fields:
- `merge_agent` from batch level
- `merge.gates`, `merge.fix_cycles`, `merge.conflict_resolution` from item level
- Read merge fix log content for item detail pages

---

### Phase 5: Python Daemon Alignment

**What**: Update `batch_manager.py` to delegate merge to `merge_job.sh` instead of
duplicating the logic in Python.

**Files to modify**:
- `scripts/ai_dev_daemon/batch_manager.py`

**Detailed requirements**:

1. Replace the `merge_item()` method (lines 478–729) with a subprocess call to
   `merge_job.sh`, passing the same 4 arguments.

2. Read `merge_agent` from the batch manifest.

3. Handle the exit codes (0, 1, 2, 3) and update item/batch status accordingly.

4. The Python daemon's `process_merge_queue()` method already processes one merge at a time
   (line 456–476). This sequential behavior is preserved — no changes needed.

5. Add queue blocking logic: when merge_job.sh returns 2 or 3, set a `_merge_blocked` flag.
   Skip `process_merge_queue()` while blocked. Clear the flag when the human updates the
   item status.

---

## Implementation Order

```
Phase 1: merge_job.sh               ← core logic, can be tested standalone
Phase 2: dispatcher integration      ← depends on Phase 1
Phase 3: manifest & planner updates  ← depends on Phase 1 (schema)
Phase 4: dashboard UI                ← depends on Phase 3 (new fields)
Phase 5: daemon alignment            ← depends on Phase 1
```

Phases 3, 4, and 5 are independent of each other and can run in parallel after Phase 2.

```
Phase 1 ──→ Phase 2 ──→ Phase 3 ──┐
                    ├──→ Phase 4 ──┤
                    └──→ Phase 5 ──┘
```

---

## Files Summary

### New Files

| File | Purpose |
|------|---------|
| `scripts/merge_job.sh` | Main merge job: squash merge + conflict resolution + quality gates + fix cycles |

### Modified Files

| File | Changes |
|------|---------|
| `scripts/batch_dispatcher.sh` | Replace `merge_item()` body with call to `merge_job.sh`; add queue blocking logic; read `merge_agent` |
| `scripts/ai_dev_daemon/batch_planner.py` | Add `merge_agent` field to manifest generation |
| `scripts/ai_dev_daemon/batch_manager.py` | Delegate merge to `merge_job.sh`; handle new exit codes; add queue blocking |
| `scripts/ai_dashboard/server.py` | Add `/api/batch/{id}/merge-agent` endpoint; pass `merge_agent` in batch creation |
| `scripts/ai_dashboard/scanner.py` | Extract merge gate data from manifests |
| `scripts/ai_dashboard/templates/agents.html` | Add merge agent dropdown to New Batch modal |
| `scripts/ai_dashboard/templates/batch_detail.html` | Show merge agent selector + per-item gate status badges |
| `scripts/ai_dashboard/templates/item_detail.html` | Show merge fix log viewer |

---

## Testing Strategy

This is infrastructure/tooling code (bash scripts + dashboard), not InnoForge application
code. Testing approach:

1. **Manual dry run**: Create a test batch with 2 items that modify overlapping files.
   Verify the merge job detects conflicts, invokes the LLM, and resolves them.

2. **Gate failure simulation**: Introduce a deliberate lint error in a worktree branch.
   Verify the merge job catches it, invokes the fix agent, and the fix succeeds.

3. **Exhaustion simulation**: Set max retries to 1 temporarily. Verify the queue blocks
   correctly and the dashboard shows `needs_human`.

4. **Alembic multi-head**: Create two branches with independent migrations. Merge the first,
   then verify the merge job detects multiple heads on the second and fixes the revision chain.

5. **Dashboard verification**: Verify the merge agent dropdown works, gate badges render
   correctly, and fix logs are viewable.

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| LLM produces bad conflict resolution | Post-merge quality gates catch it; fix cycle corrects it |
| Fix agent modifies unrelated code | Prompt explicitly constrains scope; diff review in log |
| Main stays broken after needs_human | Acceptable per decision; human intervenes |
| merge_job.sh is slow (5 retries × 3 gates) | Each gate runs only if previous passes; typical case: 0 retries |
| Prompt injection via conflict markers | Structured prompt treats code as data; SAST runs post-merge |
| Concurrent dispatcher instances | Existing flock mechanism in dispatcher prevents this |
