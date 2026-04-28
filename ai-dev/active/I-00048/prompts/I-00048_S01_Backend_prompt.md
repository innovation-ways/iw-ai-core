# I-00048_S01_Backend_prompt

**Work Item**: I-00048 — Prompts and manifest not copied into worktree — agents thrash on orientation every step
**Step**: S01
**Agent**: backend-impl

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

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Not applicable for this step (no DB changes).

---

## Input Files

- Design document: `ai-dev/active/I-00048/I-00048_Issue_Design.md`
- File to modify: `executor/worktree_setup.sh`
- Conventions: `CLAUDE.md`, `executor/CLAUDE.md`

## Output Files

- `executor/worktree_setup.sh` (modified)
- `ai-dev/active/I-00048/reports/I-00048_S01_Backend_report.md`

---

## Context

You are fixing a process inefficiency in the worktree setup script. When the daemon creates a git worktree for a work item, the orchestration context files — prompts, `workflow-manifest.json`, and the design doc — live in the main repo under `ai-dev/active/<ID>/` but are never copied into the worktree's checkout. Every agent starts its step by running `Glob "ai-dev/active/<ID>/**/*"` and gets 0 matches, falling back to a sequence of wasted orientation commands.

Read the design document before starting. The fix is a new step in `executor/worktree_setup.sh` that copies the context files and writes git exclude patterns to prevent them from being committed to the worktree branch.

Read `executor/CLAUDE.md` before editing — it lists critical rules for executor scripts.

---

## Requirements

### 1. Add Step 7 to `executor/worktree_setup.sh`: copy context files into the worktree

After the existing Step 6 (skills sync, ending around line 194 of `executor/worktree_setup.sh`), add a new numbered step that:

**a) Copies `ai-dev/active/<ID>/` into the worktree:**

```bash
# ---------------------------------------------------------------------------
# Step 7: Copy work item context (prompts, manifest, design doc) into the
# worktree so agents can discover them via Glob immediately.
# ---------------------------------------------------------------------------
ACTIVE_SRC="$PROJECT_REPO_ROOT/ai-dev/active/$ITEM_ID"
ACTIVE_DST="$WORKTREE_DIR/ai-dev/active/$ITEM_ID"

if [[ -d "$ACTIVE_SRC" ]]; then
    echo "Copying work item context into worktree..." >&2
    mkdir -p "$(dirname "$ACTIVE_DST")"
    cp -r "$ACTIVE_SRC" "$ACTIVE_DST"
    echo "Context copied: $ACTIVE_DST" >&2
fi
```

Use `cp -r`, not `rsync`. If `$ACTIVE_SRC` does not exist (e.g., manually registered item), skip silently — no error, no exit.

**b) Write per-worktree git exclude patterns immediately after the copy:**

```bash
if [[ -d "$ACTIVE_SRC" ]]; then
    # Resolve the worktree's own gitdir (differs per-worktree from the shared .git/)
    WORKTREE_GITDIR=$(git -C "$WORKTREE_DIR" rev-parse --git-dir)
    # Resolve to absolute path in case rev-parse returns a relative one
    if [[ "${WORKTREE_GITDIR:0:1}" != "/" ]]; then
        WORKTREE_GITDIR="$WORKTREE_DIR/$WORKTREE_GITDIR"
    fi
    mkdir -p "$WORKTREE_GITDIR/info"
    {
        echo "# iw: read-only context copied from main repo — must not be committed to the branch"
        echo "ai-dev/active/$ITEM_ID/prompts/"
        echo "ai-dev/active/$ITEM_ID/workflow-manifest.json"
        echo "ai-dev/active/$ITEM_ID/*.md"
    } >> "$WORKTREE_GITDIR/info/exclude"
    echo "Per-worktree git exclude written: $WORKTREE_GITDIR/info/exclude" >&2
fi
```

**Key constraints:**
- The `info/exclude` file is per-worktree (lives under `.git/worktrees/<name>/info/`) — it does NOT affect the main repo or other worktrees.
- The exclude patterns must NOT cover `ai-dev/active/$ITEM_ID/reports/` — agent reports must still be committed.
- `git rev-parse --git-dir` from inside a git worktree returns the worktree-specific path (e.g., `../.git/worktrees/<branch-name>`), which may be relative; always resolve to absolute before use.
- Append (`>>`) to `info/exclude`, never overwrite — the file may have existing content from git.

### 2. Preserve the final `echo "$WORKTREE_DIR"` output line

The last line of stdout from `worktree_setup.sh` is the worktree path consumed by the daemon. Do NOT insert any `echo` to stdout after the new step — only use `echo ... >&2` for informational messages. The final `echo "$WORKTREE_DIR"` line must remain last on stdout.

---

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`, run in order:

1. `make format` — auto-fixes formatting drift
2. `make typecheck` — zero errors on files you touched
3. `make lint` — zero errors (project-wide, not file-scoped)

## Test Verification (NON-NEGOTIABLE)

After implementation:

```bash
make test-unit
```

Do NOT report `tests_passed: true` unless all unit tests pass with zero failures.

---

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "I-00048",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "executor/worktree_setup.sh"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
