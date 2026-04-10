#!/usr/bin/env bash
# =============================================================================
# IW AI Core — Worktree Commit & Squash-Merge Script
# =============================================================================
#
# 1. Commits any uncommitted changes in the worktree branch.
# 2. Verifies the branch is ahead of main.
# 3. Squash-merges the branch into main (from the main repo root).
# 4. Commits the squash merge on main.
#
# Called by merge_queue.py for completed work items.
# This runs OUTSIDE the LLM — deterministic bash only.
#
# Usage:
#   executor/worktree_commit.sh <item_id> <project_repo_root>
#
# Exit codes:
#   0 — success (squash-merged into main)
#   1 — failure (commit failed, merge conflict, or branch has no commits)
#   2 — worktree does not exist (may already be cleaned up — caller handles)
#
# =============================================================================

set -euo pipefail

ITEM_ID="${1:?Usage: worktree_commit.sh <item_id> <project_repo_root>}"
PROJECT_REPO_ROOT="${2:?project_repo_root is required}"

WORKTREE_DIR="$PROJECT_REPO_ROOT/.worktrees/$ITEM_ID"

# ---------------------------------------------------------------------------
# Exit trap: always restore main's stash if we pushed one, regardless of how
# the script exits (success, failure, or unexpected crash).
# ---------------------------------------------------------------------------
main_stashed=false

_restore_main_stash() {
    if [[ "$main_stashed" == true ]]; then
        echo "[worktree_commit] INFO: Restoring stashed changes on main (exit trap)" >&2
        cd "$PROJECT_REPO_ROOT"
        if git stash pop; then
            echo "[worktree_commit] OK: Stashed changes restored on main" >&2
        else
            echo "[worktree_commit] WARN: git stash pop had conflicts — run 'git stash list' to recover iw-pre-merge-stash($ITEM_ID)" >&2
        fi
    fi
}
trap '_restore_main_stash' EXIT

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
BRANCH_NAME=$(git rev-parse --abbrev-ref HEAD)

# ---------------------------------------------------------------------------
# Step 2: Commit any uncommitted changes in the worktree
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
git diff main..HEAD --name-status 2>/dev/null | head -30 || true >&2

# ---------------------------------------------------------------------------
# Step 5: Squash-merge into main
# ---------------------------------------------------------------------------
cd "$PROJECT_REPO_ROOT"

echo "[worktree_commit] Squash-merging branch $BRANCH_NAME into main..." >&2

# ---------------------------------------------------------------------------
# Step 5a: Protect uncommitted changes on main with git stash
# ---------------------------------------------------------------------------
main_uncommitted=$(git status --porcelain 2>/dev/null || echo "")
main_stashed=false

if [[ -n "$main_uncommitted" ]]; then
    echo "[worktree_commit] INFO: Found uncommitted changes on main — stashing before merge" >&2
    echo "$main_uncommitted" | head -20 >&2
    if git stash push --include-untracked -m "iw-pre-merge-stash($ITEM_ID)"; then
        main_stashed=true
        echo "[worktree_commit] OK: Uncommitted changes stashed on main" >&2
    else
        echo "[worktree_commit] ERROR: Failed to stash uncommitted changes on main — aborting merge" >&2
        exit 1
    fi
fi

# Git refuses to squash-merge when untracked files on main collide with files
# on the branch. These are typically design docs that were created on main
# before the worktree was set up. Move them out of the way temporarily.
STASH_DIR=$(mktemp -d "/tmp/iw-merge-stash-${ITEM_ID}-XXXXXX")
stashed_count=0

# Get the list of NEW files on the branch (Added relative to main)
while IFS=$'\t' read -r status fpath; do
    if [[ "$status" == "A" && -f "$fpath" ]]; then
        mkdir -p "$STASH_DIR/$(dirname "$fpath")"
        mv "$fpath" "$STASH_DIR/$fpath"
        stashed_count=$((stashed_count + 1))
    fi
done < <(git diff main..."$BRANCH_NAME" --name-status --diff-filter=A 2>/dev/null)

if [[ "$stashed_count" -gt 0 ]]; then
    echo "[worktree_commit] Moved $stashed_count conflicting untracked files to $STASH_DIR" >&2
fi

# Perform the squash merge
if ! git merge --squash "$BRANCH_NAME" 2>&1; then
    echo "[worktree_commit] ERROR: git merge --squash failed (possible conflict)" >&2
    # Restore file-level stash
    if [[ "$stashed_count" -gt 0 ]]; then
        cd "$STASH_DIR"
        find . -type f | while read -r f; do
            dest="$PROJECT_REPO_ROOT/${f#./}"
            mkdir -p "$(dirname "$dest")"
            mv "$f" "$dest"
        done
    fi
    rm -rf "$STASH_DIR"
    cd "$PROJECT_REPO_ROOT"
    git reset HEAD 2>/dev/null || true
    exit 1  # exit trap restores main stash
fi

# Verify merge produced changes
merge_status=$(git status --porcelain 2>/dev/null || echo "")
if [[ -z "$merge_status" ]]; then
    echo "[worktree_commit] ERROR: Squash-merge produced no changes — nothing to commit" >&2
    rm -rf "$STASH_DIR"
    exit 1  # exit trap restores main stash
fi

# Commit the squash merge
if git commit --no-verify -m "Merge $ITEM_ID: squash-merge from $BRANCH_NAME"; then
    echo "[worktree_commit] OK: Squash-merge committed on main" >&2
else
    echo "[worktree_commit] ERROR: Squash-merge commit failed" >&2
    git reset HEAD 2>/dev/null || true
    rm -rf "$STASH_DIR"
    exit 1  # exit trap restores main stash
fi

rm -rf "$STASH_DIR"
echo "[worktree_commit] OK: $ITEM_ID merged to main successfully" >&2
exit 0  # exit trap restores main stash
