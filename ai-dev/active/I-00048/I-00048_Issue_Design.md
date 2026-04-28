# I-00048: Prompts and manifest not copied into worktree — agents thrash on orientation every step

**Type**: Issue
**Severity**: Medium
**Created**: 2026-04-28
**Reported By**: iw-item-analyze (I-00045 retrospective)
**Status**: Draft

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (see the 2026-04-22 incident in
docs/IW_AI_Core_DB_Setup.md).

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Not applicable for this step (no DB changes).

---

## Description

When the daemon creates a git worktree for a work item, the context files that agents need — prompts, `workflow-manifest.json`, and the design doc — exist only in the main repo's working tree under `ai-dev/active/<ID>/`, never in the worktree's checkout. Every agent starts by running `Glob "ai-dev/active/<ID>/**/*"` and gets 0 matches (or only finds reports already written by prior steps), then falls back to a sequence of orientation commands — including invalid `iw` subcommands, self-reads of the current run log, and unrelated directory exploration — before finding what it needs. In I-00045 this affected at least 4 steps (S01, S02, S03, S11), wasting 30–90 seconds per step and causing the S11 browser agent to drift into the unrelated `ai-dev/work/CR-00006/` directory.

## Project Context

Read `CLAUDE.md` for architecture, conventions, and hard rules. Key relevant sections:
- **Executor scripts**: `executor/worktree_setup.sh` creates the worktree and prepares the environment
- **`worktree_commit.sh`**: squash-merges the branch; Step 2 runs `git add -A` which commits all untracked files
- **Critical**: copied files must be excluded from git tracking in the worktree to avoid merge collisions

## Steps to Reproduce

1. Daemon creates a worktree for any work item via `executor/worktree_setup.sh`
2. Agent launches for S01 — `ai-dev/active/<ID>/prompts/` does not exist in the worktree
3. Agent runs `Glob "ai-dev/active/<ID>/**/*"` → 0 matches
4. Agent runs a series of fallback orientation commands before finding the item context
5. In later steps (e.g., S11), agent tries `Glob "ai-dev/active/<ID>/*.md"` → 0 matches, then explores unrelated directories

**Expected**: Agent immediately finds prompts, manifest, and design doc via `Glob "ai-dev/active/<ID>/**/*"` on its first try.

**Actual**: Glob returns 0 matches (or only already-written reports); agent spends 30–90s on fallback orientation commands. In late steps, agents visit unrelated directories.

## Root Cause Analysis

`executor/worktree_setup.sh` creates the worktree branch from the current HEAD of main (Step 3), installs dependencies (Step 4), generates `.env` (Step 5), and syncs skills (Step 6). It never copies the orchestration artifacts (`ai-dev/active/<ID>/`) into the worktree.

The daemon writes those artifacts into the main repo's working tree before creating the worktree — they are untracked files in the main repo. The worktree's git checkout starts from HEAD and inherits none of these untracked files.

A naive copy would cause a second problem: `worktree_commit.sh` Step 2 runs `git add -A`, which would commit the copied files into the branch. At squash-merge time, those files already exist in the main repo as untracked files, so Step 5a would detect them as collisions (files Added on the branch that already exist on main's working tree), save the originals with `.iw-collision` suffixes, and the merge would produce spurious collision artifacts on every item.

The fix requires two steps:
1. Copy the context files into the worktree after creation
2. Write their paths into the worktree-specific `.git/worktrees/<name>/info/exclude` file so `git add -A` ignores them

Each git worktree has its own gitdir (resolvable via `git -C "$WORKTREE_DIR" rev-parse --git-dir`). Writing to `$WORKTREE_GITDIR/info/exclude` creates a per-worktree gitignore that does not affect the main repo or other worktrees.

Evidence from I-00045 analysis:
- `S01 run1 log:5` — `Glob "ai-dev/active/I-00045/**/*" 0 matches` → invalid iw commands
- `S03 run1 log:34` — `Glob "ai-dev/active/I-00045/prompts/*" 0 matches`
- `S11 run1 log:12` — `Glob "ai-dev/active/I-00045/*.md" 0 matches` → drifted to `ai-dev/work/CR-00006/`

## Affected Components

| Component | File | Impact |
|-----------|------|--------|
| Worktree setup | `executor/worktree_setup.sh` | Missing Step 7: copy context + write exclude |
| Per-worktree exclude | `$WORKTREE_GITDIR/info/exclude` | Written at setup time; does not exist today |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | Backend | Add Step 7 to `worktree_setup.sh`: copy `ai-dev/active/<ID>/` into worktree, write per-worktree `info/exclude` | — |
| S02 | CodeReview | Review S01 changes | — |
| S03 | Tests | Write unit + integration tests verifying copy and git exclusion behavior | — |
| S04 | CodeReview | Review S03 test coverage | — |
| S05 | CodeReview_Final | Global review of all work | — |
| S06 | QvGate | lint | — |
| S07 | QvGate | format-check | — |
| S08 | QvGate | typecheck | — |
| S09 | QvGate | unit-tests | — |
| S10 | QvGate | integration-tests | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None

### Code Changes

- **Files to modify**: `executor/worktree_setup.sh`
- **Nature of change**: Add a new step after skills sync that copies `ai-dev/active/<ID>/` context files into the worktree and writes their paths to the per-worktree `info/exclude` file

The new step must:
1. Locate the source context directory: `$PROJECT_REPO_ROOT/ai-dev/active/$ITEM_ID/`
2. If it exists, copy it into the worktree: `cp -r "$PROJECT_REPO_ROOT/ai-dev/active/$ITEM_ID" "$WORKTREE_DIR/ai-dev/active/"`
   - Create `$WORKTREE_DIR/ai-dev/active/` if needed
   - Copy is preferred over symlink to prevent agents writing back through a link
3. Resolve the worktree gitdir: `WORKTREE_GITDIR=$(git -C "$WORKTREE_DIR" rev-parse --git-dir)`
4. Write exclude patterns to `$WORKTREE_GITDIR/info/exclude`:
   ```
   ai-dev/active/<ID>/prompts/
   ai-dev/active/<ID>/workflow-manifest.json
   ai-dev/active/<ID>/<ID>_*.md
   ```
   This prevents `git add -A` from staging these files. Agent-written reports (`ai-dev/active/<ID>/reports/`) are intentionally NOT excluded — they continue to be committed to the branch and merged to main as today.

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `ai-dev/active/I-00048/I-00048_Issue_Design.md` | Design | This document |
| `ai-dev/active/I-00048/workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `ai-dev/active/I-00048/prompts/I-00048_S01_Backend_prompt.md` | Prompt | S01 fix instructions |
| `ai-dev/active/I-00048/prompts/I-00048_S02_CodeReview_Backend_prompt.md` | Prompt | S02 review |
| `ai-dev/active/I-00048/prompts/I-00048_S03_Tests_prompt.md` | Prompt | S03 test writing |
| `ai-dev/active/I-00048/prompts/I-00048_S04_CodeReview_Tests_prompt.md` | Prompt | S04 review |
| `ai-dev/active/I-00048/prompts/I-00048_S05_CodeReview_Final_prompt.md` | Prompt | S05 global review |

## Test to Reproduce

```python
def test_worktree_setup_copies_active_dir_into_worktree(tmp_path):
    """After worktree_setup.sh runs, ai-dev/active/<ID>/ must exist in the worktree.
    This test FAILS before the fix and PASSES after.
    """
    import subprocess, os

    # Arrange: bare git repo with a main branch + an active/<ID>/ dir on main's working tree
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main", str(repo)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "commit", "--allow-empty", "-m", "init"], check=True, capture_output=True)

    active_dir = repo / "ai-dev" / "active" / "I-00048"
    prompts_dir = active_dir / "prompts"
    prompts_dir.mkdir(parents=True)
    (prompts_dir / "I-00048_S01_Backend_prompt.md").write_text("# prompt")
    (active_dir / "workflow-manifest.json").write_text('{"id": "I-00048"}')
    (active_dir / "I-00048_Issue_Design.md").write_text("# design")

    # Act: run worktree_setup.sh
    # (requires a DB-registered item in tests — use a subprocess integration fixture)
    worktree = repo / ".worktrees" / "I-00048"

    # Assert: the context files must exist in the worktree
    assert (worktree / "ai-dev" / "active" / "I-00048" / "prompts" / "I-00048_S01_Backend_prompt.md").exists()
    assert (worktree / "ai-dev" / "active" / "I-00048" / "workflow-manifest.json").exists()
```

## Acceptance Criteria

### AC1: Context files are discoverable in the worktree

```
Given a work item with ai-dev/active/<ID>/ existing in the main repo
When the daemon creates a worktree via worktree_setup.sh
Then ai-dev/active/<ID>/prompts/ exists inside the worktree
And ai-dev/active/<ID>/workflow-manifest.json exists inside the worktree
And the design doc exists inside the worktree
```

### AC2: Copied files are excluded from git tracking

```
Given the worktree has been set up with the context files copied in
When git status --porcelain is run inside the worktree
Then the copied prompt files, manifest, and design doc do NOT appear as untracked
And agent-written reports (ai-dev/active/<ID>/reports/) continue to appear as untracked
```

### AC3: Merge produces no collision artifacts

```
Given a worktree where context files were copied in
When worktree_commit.sh merges the branch to main
Then no .iw-collision files appear in the repo
And the original prompts/manifest/design doc on main are intact
```

### AC4: Regression test exists

```
Given the fix is applied
When the test suite runs
Then tests for copy behavior and git exclusion pass
```

## Regression Prevention

The per-worktree `info/exclude` mechanism is the structural guard that prevents merge collisions for all future worktrees. The new integration test verifying `git status` in the worktree ensures the behavior cannot silently regress if the exclude step is removed or the pattern syntax changes.

## Dependencies

- **Depends on**: None
- **Blocks**: None

## TDD Approach

- Reproducing test: integration test that creates a real git repo, runs `worktree_setup.sh` (or the Python helper that calls it), and asserts the files exist in the worktree
- Unit tests: test `info/exclude` file content for correct patterns; test behavior when `ai-dev/active/<ID>/` does not exist (idempotent — no error)
- Integration tests: test that `git status --porcelain` in the worktree does not list the copied files; test that `git add -A` + `git status` does not stage them

## Notes

- The exclude patterns must NOT cover `ai-dev/active/<ID>/reports/` — agent reports are intentionally committed to the branch and merged to main.
- If `ai-dev/active/<ID>/` does not exist on main (e.g., for manually registered items without prompts), the copy step must silently skip — no error.
- The copy must use `cp -r`, not `rsync`, to avoid adding an external dependency.
- The worktree gitdir path (from `git -C "$WORKTREE_DIR" rev-parse --git-dir`) may be relative; resolve it to absolute before appending `info/exclude`.
