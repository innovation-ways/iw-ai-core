#!/usr/bin/env bash
# =============================================================================
# IW AI Core — Worktree Commit Script
# =============================================================================
#
# Commits all changes in a worktree to its branch, then verifies the branch
# has commits ahead of main — the pre-flight gate before squash-merging.
# Called by the daemon immediately before squash-merging a completed work item.
#
# This runs OUTSIDE the LLM — deterministic bash only.
#
# Usage:
#   executor/worktree_commit.sh <item_id> <project_repo_root>
#
# Exit codes:
#   0 — success (committed, or working tree was already clean)
#   1 — failure (commit failed, or branch has no commits ahead of main)
#   2 — worktree does not exist (may already be cleaned up — caller handles)
#
# =============================================================================

set -euo pipefail

ITEM_ID="${1:?Usage: worktree_commit.sh <item_id> <project_repo_root>}"
PROJECT_REPO_ROOT="${2:?project_repo_root is required}"

WORKTREE_DIR="$PROJECT_REPO_ROOT/.worktrees/$ITEM_ID"

# ---------------------------------------------------------------------------
# Step 1: Check worktree exists
# ---------------------------------------------------------------------------
if [[ ! -d "$WORKTREE_DIR" ]]; then
    echo "[worktree_commit] INFO: Worktree not found at $WORKTREE_DIR — skipping" >&2
    exit 2
fi

if [[ ! -f "$WORKTREE_DIR/.git" ]]; then
    echo "[worktree_commit] ERROR: $WORKTREE_DIR exists but is not a git worktree" >&2
    exit 1
fi

cd "$WORKTREE_DIR"

# ---------------------------------------------------------------------------
# Step 2: Commit any uncommitted changes
# ---------------------------------------------------------------------------
uncommitted=$(git status --porcelain 2>/dev/null || echo "")

if [[ -z "$uncommitted" ]]; then
    echo "[worktree_commit] INFO: Working tree is clean — no changes to commit" >&2
else
    echo "[worktree_commit] INFO: Found uncommitted changes — committing to branch" >&2
    echo "$uncommitted" | head -20 >&2

    git add -A

    if git commit -m "wip($ITEM_ID): implementation complete — pending merge to main" --no-verify; then
        echo "[worktree_commit] OK: Committed changes to branch" >&2
    else
        echo "[worktree_commit] ERROR: git commit failed" >&2
        exit 1
    fi
fi

# ---------------------------------------------------------------------------
# Step 3: Verify branch has commits ahead of main
# ---------------------------------------------------------------------------
# This is the critical merge gate: if the branch has no commits ahead of main,
# the squash merge produces an empty commit — meaning the agent did nothing.
# Block the merge so the user can investigate.
# ---------------------------------------------------------------------------
ahead=$(git log main..HEAD --oneline 2>/dev/null | wc -l | tr -d ' ')

if [[ "$ahead" -eq 0 ]]; then
    echo "[worktree_commit] ERROR: Branch has NO commits ahead of main." >&2
    echo "[worktree_commit]        The worktree is clean but no implementation work was committed." >&2
    echo "[worktree_commit]        This means the agent completed without writing any code." >&2
    echo "[worktree_commit]        Manual investigation required for $ITEM_ID." >&2
    exit 1
fi

echo "[worktree_commit] OK: Branch is $ahead commit(s) ahead of main — safe to merge" >&2

# ---------------------------------------------------------------------------
# Step 4: Show what will be merged (summary for logs)
# ---------------------------------------------------------------------------
echo "[worktree_commit] Files on branch vs main:" >&2
git diff main..HEAD --name-status 2>/dev/null | head -30 >&2

exit 0
