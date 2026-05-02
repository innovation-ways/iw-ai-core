#!/usr/bin/env bash
# =============================================================================
# IW AI Core — Worktree Commit & Squash-Merge Script
# =============================================================================
#
# 1. Commits any uncommitted changes in the worktree branch.
# 2. Rebases the branch onto the current tip of main so divergent parallel
#    batch items are reconciled on the branch — never on main.
# 3. Verifies the branch is ahead of main.
# 4. Squash-merges the branch into main (from the main repo root).
# 5. Commits the squash merge on main.
#
# Called by merge_queue.py for completed work items.
# This runs OUTSIDE the LLM — deterministic bash only.
#
# Guarantees:
#   - If the pre-merge rebase fails, main is NEVER touched.
#   - If the squash-merge fails partway, main's worktree is restored to a
#     clean HEAD (git reset --hard + git clean -fd) before returning, so no
#     branch content leaks onto main as modified tracked files or untracked
#     files.
#
# Usage:
#   executor/worktree_commit.sh <item_id> <project_repo_root>
#
# Exit codes:
#   0 — success (squash-merged into main)
#   1 — failure (commit failed, rebase conflict, merge conflict, or empty branch)
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
        if git stash pop >&2; then
            echo "[worktree_commit] OK: Stashed changes restored on main" >&2
        else
            # git stash pop can fail when the merge committed a file that also
            # existed as an untracked file in the stash (e.g. local_notes.md
            # written by the user before the worktree was created). Git refuses
            # to overwrite the tracked version with the stashed untracked copy.
            # Solution: extract the colliding files manually, save them with a
            # .iw-collision suffix, then drop the stash so the repo is clean.
            echo "[worktree_commit] INFO: Stash pop had conflicts — checking for untracked collisions" >&2
            local _stash_tmp
            _stash_tmp=$(mktemp -d)
            # Export the stash as a tar to access its untracked files safely
            if git stash show -p stash@{0} >/dev/null 2>&1; then
                # List files in the stash's untracked-file tree (stash^3 is the
                # untracked-files pseudo-commit that --include-untracked records)
                local _untracked_tree
                _untracked_tree=$(git rev-parse stash@{0}^3 2>/dev/null || true)
                if [[ -n "$_untracked_tree" ]]; then
                    git ls-tree -r --name-only "$_untracked_tree" 2>/dev/null | while IFS= read -r _f; do
                        _dest="$PROJECT_REPO_ROOT/$_f"
                        if [[ -e "$_dest" ]]; then
                            # Collision: tracked file exists from the merge.
                            # Save the stashed user copy with .iw-collision suffix.
                            git show "${_untracked_tree}:${_f}" 2>/dev/null > "${_dest}.iw-collision" || true
                            echo "[worktree_commit] WARN: Collision on $_f — user copy saved as ${_dest}.iw-collision" >&2
                        else
                            mkdir -p "$(dirname "$_dest")"
                            git show "${_untracked_tree}:${_f}" 2>/dev/null > "$_dest" || true
                        fi
                    done
                fi
            fi
            rm -rf "$_stash_tmp"
            # Drop the stash so the repo is in a clean state
            git stash drop stash@{0} >/dev/null 2>&1 || true
            echo "[worktree_commit] OK: Stash conflicts resolved (any collisions saved with .iw-collision suffix)" >&2
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
    # Print a count, not the file list. Piping a large status into `head -N`
    # under `set -euo pipefail` is unsafe: head closes the pipe early and the
    # producer is killed with SIGPIPE, which pipefail propagates as a non-zero
    # pipeline exit and set -e then aborts the script before `git add -A`.
    # The full diff lands in `git commit`'s output a few lines below anyway.
    n_uncommitted=$(echo "$uncommitted" | wc -l | tr -d ' ')
    echo "[worktree_commit] INFO: Found $n_uncommitted uncommitted line(s) — committing to branch" >&2

    git add -A

    if git commit -m "wip($ITEM_ID): implementation complete — pending merge to main" --no-verify; then
        echo "[worktree_commit] OK: Committed changes to branch" >&2
    else
        echo "[worktree_commit] ERROR: git commit failed" >&2
        exit 1
    fi
fi

# ---------------------------------------------------------------------------
# Step 2.25: Scope gate — refuse to merge files outside the declared scope
# ---------------------------------------------------------------------------
# The workflow-manifest.json declares scope.allowed_paths (list of globs). This
# gate diffs the branch against its merge-base with main and blocks the merge
# if any modified file falls outside the allow-list. Runs entirely on the
# branch — main is never touched.
#
# Why: the 2026-04-22 I-00034 retrospective found QV gate fix-cycles (S06, S10)
# silently expanded scope by "fixing" pre-existing lint/test failures in files
# the work item had no business touching. The Final Review (S05) ran BEFORE
# those fix-cycles, so it didn't catch the drift. This gate is the mechanical
# fail-safe that runs after all agent work is complete.
#
# Legacy items (manifest without scope.allowed_paths) pass through unchecked —
# scope_gate.py treats an empty list as "gate disabled".
#
# Per-project toggle: the daemon sets IW_SCOPE_GATE_ENABLED based on the
# project's .iw-orch.json {"scope_gate_enabled": true}. Default is "false" —
# the gate is opt-in. Projects without the config (or with it set to false)
# skip the gate entirely. CR-00030 will replace this with a finer-grained
# mechanism (per-step file-allowlist enforcement).

MANIFEST_FILE="$WORKTREE_DIR/ai-dev/active/$ITEM_ID/workflow-manifest.json"
if [[ ! -f "$MANIFEST_FILE" ]]; then
    MANIFEST_FILE="$WORKTREE_DIR/ai-dev/archive/$ITEM_ID/workflow-manifest.json"
fi

if [[ "${IW_SCOPE_GATE_ENABLED:-false}" != "true" ]]; then
    echo "[worktree_commit] INFO: Scope gate disabled by project config — skipping" >&2
elif [[ -f "$MANIFEST_FILE" ]]; then
    # Resolve executor dir (same directory as this script) for the helper.
    EXECUTOR_DIR="$(cd "$(dirname "$0")" && pwd)"
    MERGE_BASE=$(git merge-base HEAD main)
    set +e
    VIOLATIONS=$(
        git diff "$MERGE_BASE"..HEAD --name-only 2>/dev/null \
            | python3 "$EXECUTOR_DIR/scope_gate.py" "$MANIFEST_FILE" "$ITEM_ID" 2>/dev/null
    )
    SCOPE_RC=$?
    set -e
    if [[ $SCOPE_RC -eq 2 ]]; then
        echo "[worktree_commit] ERROR: Scope gate — could not evaluate manifest at $MANIFEST_FILE" >&2
        exit 1
    fi
    if [[ -n "$VIOLATIONS" ]]; then
        echo "[worktree_commit] ERROR: Scope gate — files modified outside declared scope:" >&2
        while IFS= read -r bad; do
            [[ -z "$bad" ]] || echo "[worktree_commit]   - $bad" >&2
        done <<<"$VIOLATIONS"
        echo "[worktree_commit]        Either revert these changes on the branch or, if legitimate," >&2
        echo "[worktree_commit]        add them to scope.allowed_paths in" >&2
        echo "[worktree_commit]        $MANIFEST_FILE" >&2
        echo "[worktree_commit]        and re-trigger the merge. Main has not been touched." >&2
        exit 1
    fi
    echo "[worktree_commit] OK: Scope gate passed" >&2
else
    echo "[worktree_commit] INFO: No workflow-manifest.json for $ITEM_ID — scope gate skipped" >&2
fi

# ---------------------------------------------------------------------------
# Step 2.5: Rebase branch onto the latest main
# ---------------------------------------------------------------------------
# This runs ENTIRELY in the branch's worktree and never touches main. If any
# other batch item merged to main between when this branch was created and now,
# we replay our commit(s) on top so the squash-merge in Step 5 is a trivial
# fast-forward that cannot conflict.
#
# Auto-resolution of recurring infrastructure conflicts:
#   uv.lock  — always conflicts when multiple items add dependencies; resolved
#              by taking main's version (--ours during rebase = main's tip).
#              After squash-merge, uv lock --no-upgrade regenerates it from the
#              merged pyproject.toml so no dependency is lost.
#   Makefile — build-target lines often touched by multiple items; resolved by
#              preferring the branch's version (--theirs = this item's changes,
#              which are typically a superset of concurrent Makefile edits).
#
# On conflict in any other file we abort the rebase and report the file list.
# Main is never touched on failure.

# Files resolved by taking main's version (--ours in rebase context = main's tip).
# These are auto-generated files that will be regenerated post-merge.
_REBASE_TAKE_OURS="uv.lock"

# Files resolved by taking the branch's version (--theirs = commits being replayed).
# Used for build/config files where concurrent edits are typically additive.
_REBASE_TAKE_THEIRS="Makefile"

# Auto-generated files to regenerate after squash-merge (space-separated).
_REGEN_AFTER_MERGE="uv.lock"

MAIN_SHA=$(git rev-parse main 2>/dev/null || echo "")
BRANCH_SHA=$(git rev-parse HEAD 2>/dev/null || echo "")

if [[ -z "$MAIN_SHA" ]]; then
    echo "[worktree_commit] ERROR: Could not resolve 'main' from worktree" >&2
    exit 1
fi

if [[ "$(git merge-base HEAD main)" == "$MAIN_SHA" ]]; then
    echo "[worktree_commit] INFO: Branch already contains main tip ($MAIN_SHA) — no rebase needed" >&2
else
    echo "[worktree_commit] INFO: Rebasing $BRANCH_NAME onto main ($MAIN_SHA)" >&2

    if git rebase main 2>&1; then
        NEW_BRANCH_SHA=$(git rev-parse HEAD)
        echo "[worktree_commit] OK: Rebased $BRANCH_NAME: $BRANCH_SHA → $NEW_BRANCH_SHA" >&2
    else
        # Rebase failed — identify conflicting files and auto-resolve where safe.
        conflicting=$(git diff --name-only --diff-filter=U 2>/dev/null || echo "")

        if [[ -z "$conflicting" ]]; then
            echo "[worktree_commit] ERROR: Rebase failed (no conflict markers — unexpected state)" >&2
            git rebase --abort 2>/dev/null || true
            exit 1
        fi

        echo "[worktree_commit] INFO: Rebase conflicts detected:" >&2
        while IFS= read -r _cf; do
            [[ -z "$_cf" ]] && continue
            echo "[worktree_commit]   - $_cf" >&2
        done <<< "$conflicting"

        # Separate into auto-resolvable and blocking conflicts.
        _blocking=""
        while IFS= read -r _cf; do
            [[ -z "$_cf" ]] && continue
            if echo " $_REBASE_TAKE_OURS " | grep -qF " $_cf "; then
                git checkout --ours "$_cf" 2>/dev/null && git add "$_cf"
                echo "[worktree_commit] INFO: Auto-resolved $_cf (--ours = main's version; will regenerate post-merge)" >&2
            elif echo " $_REBASE_TAKE_THEIRS " | grep -qF " $_cf "; then
                git checkout --theirs "$_cf" 2>/dev/null && git add "$_cf"
                echo "[worktree_commit] INFO: Auto-resolved $_cf (--theirs = branch's version)" >&2
            else
                _blocking="$_blocking $_cf"
            fi
        done <<< "$conflicting"

        if [[ -n "$_blocking" ]]; then
            echo "[worktree_commit] ERROR: Rebase conflict in implementation files — manual resolution required:" >&2
            for _bf in $_blocking; do
                echo "[worktree_commit]   - $_bf" >&2
            done
            echo "[worktree_commit]        Another batch item modified the same files before this one merged." >&2
            echo "[worktree_commit]        Conflicts must be resolved manually in $WORKTREE_DIR" >&2
            echo "[worktree_commit]        Then run: iw merge-queue retry-merge $ITEM_ID" >&2
            git rebase --abort 2>/dev/null || true
            exit 1
        fi

        # All conflicts auto-resolved — continue the rebase.
        if GIT_EDITOR=true git rebase --continue 2>&1; then
            NEW_BRANCH_SHA=$(git rev-parse HEAD)
            echo "[worktree_commit] OK: Rebased $BRANCH_NAME (auto-resolved conflicts): $BRANCH_SHA → $NEW_BRANCH_SHA" >&2
        else
            echo "[worktree_commit] ERROR: Rebase --continue failed after auto-resolution" >&2
            git rebase --abort 2>/dev/null || true
            exit 1
        fi
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
git diff main..HEAD --name-status 2>/dev/null | head -30 >&2 || true

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
    n_main_uncommitted=$(echo "$main_uncommitted" | wc -l | tr -d ' ')
    echo "[worktree_commit] INFO: Found $n_main_uncommitted uncommitted line(s) on main — stashing before merge" >&2
    if git stash push --include-untracked -m "iw-pre-merge-stash($ITEM_ID)" >&2; then
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
# Note: the main stash above with --include-untracked should cover most of
# these, but we keep this belt-and-braces for files that fall outside the stash
# (ignored files, files in nested worktrees, etc.).
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

# ---------------------------------------------------------------------------
# Restore helper: moves files from $STASH_DIR back to their original locations
# under $PROJECT_REPO_ROOT after a SUCCESSFUL merge. On the failure path the
# inline restore block does the same thing.
#
# If the merge added a file at the same path (a legitimate collision), the
# merged version wins — the user's original is preserved with a .iw-collision
# suffix so they can recover it manually.
# ---------------------------------------------------------------------------
_restore_stash_dir_files() {
    if [[ "$stashed_count" -eq 0 ]]; then
        return
    fi
    cd "$STASH_DIR"
    find . -type f | while IFS= read -r f; do
        dest="$PROJECT_REPO_ROOT/${f#./}"
        mkdir -p "$(dirname "$dest")"
        if [[ -e "$dest" ]]; then
            # Merge wrote a file here — save the user's original as a .iw-collision
            mv "$f" "${dest}.iw-collision"
            echo "[worktree_commit] WARN: Collision on $dest — user copy saved as ${dest}.iw-collision" >&2
        else
            mv "$f" "$dest"
        fi
    done
    cd "$PROJECT_REPO_ROOT"
}

# ---------------------------------------------------------------------------
# Cleanup helper: restores main's worktree to a clean HEAD state after a
# failed merge. `git merge --squash` can leave partial changes in both the
# index and the working tree even on failure; a plain `git reset HEAD` only
# clears the index, leaving branch content smeared across main as modified
# tracked files and untracked files (which is exactly what happened on
# F-00004). This function wipes all of that.
# ---------------------------------------------------------------------------
_cleanup_main_after_failed_merge() {
    cd "$PROJECT_REPO_ROOT"
    # Discard any staged/unstaged modifications to tracked files from the
    # merge attempt.
    git reset --hard HEAD 2>/dev/null || true
    # Remove any untracked files the merge attempt wrote to the working tree.
    # Respects .gitignore (so nested worktrees / build artifacts are safe)
    # and only removes files that appeared as a result of the failed merge,
    # because all pre-existing untracked files were stashed above.
    git clean -fd 2>/dev/null || true
}

# Perform the squash merge
if ! git merge --squash "$BRANCH_NAME" >&2; then
    echo "[worktree_commit] ERROR: git merge --squash failed (possible conflict)" >&2
    _cleanup_main_after_failed_merge
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
    exit 1  # exit trap restores main stash
fi

# Verify merge produced changes
merge_status=$(git status --porcelain 2>/dev/null || echo "")
if [[ -z "$merge_status" ]]; then
    echo "[worktree_commit] ERROR: Squash-merge produced no changes — nothing to commit" >&2
    _cleanup_main_after_failed_merge
    rm -rf "$STASH_DIR"
    exit 1  # exit trap restores main stash
fi

# Commit the squash merge — build a descriptive body
ITEM_TITLE="(title unavailable)"
if command -v iw >/dev/null 2>&1 && command -v jq >/dev/null 2>&1; then
    _title_json=$(iw item-status "$ITEM_ID" --json 2>/dev/null || true)
    if [[ -n "$_title_json" ]]; then
        _fetched=$(echo "$_title_json" | jq -r '.title // empty' 2>/dev/null || true)
        [[ -n "$_fetched" ]] && ITEM_TITLE="$_fetched"
    fi
fi
FILES_CHANGED=$(git diff --cached --name-only 2>/dev/null | wc -l | tr -d ' ')
SOURCE_COMMITS=$(git log main..HEAD --oneline 2>/dev/null | wc -l | tr -d ' ')

if git commit --no-verify -m "$(cat <<COMMIT_EOF
Merge $ITEM_ID: $ITEM_TITLE

Branch: $BRANCH_NAME
Files changed: $FILES_CHANGED
Source commits: $SOURCE_COMMITS
COMMIT_EOF
)" >&2; then
    echo "[worktree_commit] OK: Squash-merge committed on main" >&2
else
    echo "[worktree_commit] ERROR: Squash-merge commit failed" >&2
    _cleanup_main_after_failed_merge
    rm -rf "$STASH_DIR"
    exit 1  # exit trap restores main stash
fi

_restore_stash_dir_files
rm -rf "$STASH_DIR"

# ---------------------------------------------------------------------------
# Step 6: Regenerate auto-generated files from merged sources (if needed)
# ---------------------------------------------------------------------------
# uv.lock is auto-generated from pyproject.toml. When the rebase resolved a
# uv.lock conflict by taking main's version, the lock may not reflect this
# item's new dependencies. Regenerate so the merge commit includes a correct
# combined lock that covers both main's and this item's dependency changes.
if echo " $_REGEN_AFTER_MERGE " | grep -qF " uv.lock "; then
    if command -v uv >/dev/null 2>&1; then
        echo "[worktree_commit] INFO: Regenerating uv.lock from merged pyproject.toml" >&2
        if uv lock --no-upgrade 2>/dev/null; then
            _lock_diff=$(git status --porcelain uv.lock 2>/dev/null || echo "")
            if [[ -n "$_lock_diff" ]]; then
                git add uv.lock
                if git commit --no-verify --amend --no-edit 2>/dev/null; then
                    echo "[worktree_commit] OK: uv.lock regenerated and included in merge commit" >&2
                else
                    echo "[worktree_commit] WARN: Failed to amend merge commit with regenerated uv.lock" >&2
                fi
            else
                echo "[worktree_commit] INFO: uv.lock unchanged after regeneration — no amend needed" >&2
            fi
        else
            echo "[worktree_commit] WARN: uv lock --no-upgrade failed — uv.lock may be stale" >&2
        fi
    fi
fi

echo "[worktree_commit] OK: $ITEM_ID merged to main successfully" >&2
exit 0  # exit trap restores main stash
