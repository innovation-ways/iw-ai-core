#!/usr/bin/env bash
# =============================================================================
# IW AI Core — Worktree Setup Script
# =============================================================================
#
# Creates and configures a git worktree for a work item.
# Called by the daemon before launching an agent, or manually for testing.
#
# Usage:
#   executor/worktree_setup.sh <item_id> <project_repo_root> [<iw_core_root>]
#
# Arguments:
#   item_id           Work item ID (e.g. I001, F042, CR015)
#   project_repo_root Absolute path to the project repository
#   iw_core_root      Optional: path to iw-ai-core repo (defaults to parent of script dir)
#
# The script is idempotent — if the worktree already exists, it exits 0.
# Outputs the absolute worktree path on success (last line of stdout).
#
# All state goes through the iw CLI — no manifest files are read or written.
# =============================================================================

set -euo pipefail

ITEM_ID="${1:?Usage: worktree_setup.sh <item_id> <project_repo_root> [<iw_core_root>]}"
PROJECT_REPO_ROOT="${2:?project_repo_root is required}"
IW_CORE_ROOT="${3:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

WORKTREE_DIR="${PROJECT_REPO_ROOT}/.worktrees/${ITEM_ID}"

# ---------------------------------------------------------------------------
# Step 1: Check if worktree already exists (idempotent)
# ---------------------------------------------------------------------------
if [[ -d "$WORKTREE_DIR" ]]; then
    if [[ -f "$WORKTREE_DIR/.git" ]]; then
        EXISTING_BRANCH=$(cd "$WORKTREE_DIR" && git branch --show-current 2>/dev/null || echo "unknown")
        echo "Worktree already exists: $WORKTREE_DIR (branch: $EXISTING_BRANCH)" >&2
        echo "$WORKTREE_DIR"
        exit 0
    else
        # Directory exists but is not a valid git worktree — clean up and recreate
        echo "Cleaning up invalid worktree directory: $WORKTREE_DIR" >&2
        rm -rf "$WORKTREE_DIR"
        cd "$PROJECT_REPO_ROOT" && git worktree prune 2>/dev/null || true
    fi
fi

# ---------------------------------------------------------------------------
# Step 2: Get item info from DB via iw CLI
# ---------------------------------------------------------------------------
cd "$PROJECT_REPO_ROOT"

IW_STDERR=$(mktemp)
ITEM_JSON=$(iw item-status "$ITEM_ID" --json 2>"$IW_STDERR") || {
    ERR_MSG=$(cat "$IW_STDERR")
    rm -f "$IW_STDERR"
    echo "ERROR: iw item-status failed for $ITEM_ID: $ERR_MSG" >&2
    exit 1
}
rm -f "$IW_STDERR"

if [[ -z "$ITEM_JSON" ]] || echo "$ITEM_JSON" | jq -e '.error' >/dev/null 2>&1; then
    echo "ERROR: iw item-status returned an error for $ITEM_ID" >&2
    echo "$ITEM_JSON" >&2
    exit 1
fi

# Derive a short description for the branch name from the item title
TITLE=$(echo "$ITEM_JSON" | jq -r '.title // "work"')
DESC=$(echo "$TITLE" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g' | sed 's/--*/-/g' | sed 's/^-//' | sed 's/-$//' | cut -c1-30)
BRANCH="agent/${ITEM_ID}-${DESC}"

# ---------------------------------------------------------------------------
# Step 3: Create worktree (delete stale branch if needed)
# ---------------------------------------------------------------------------
cd "$PROJECT_REPO_ROOT"

if git branch --list "$BRANCH" 2>/dev/null | grep -q .; then
    echo "Deleting stale branch: $BRANCH" >&2
    git branch -D "$BRANCH" 2>/dev/null || true
fi

BASE_BRANCH=$(git rev-parse --abbrev-ref HEAD)
echo "Creating worktree: $WORKTREE_DIR (branch: $BRANCH, base: $BASE_BRANCH)" >&2
git worktree add -b "$BRANCH" "$WORKTREE_DIR" HEAD >&2

# I-00084: Sync origin/main ref to local main so diff-cover, scope_gate,
# and any other compare-vs-origin tools see the right base. This setup is
# local-only — origin/main never advances on its own.
git -C "$WORKTREE_DIR" fetch . main:refs/remotes/origin/main 2>/dev/null || true

# ---------------------------------------------------------------------------
# Step 4: Install Python dependencies
# ---------------------------------------------------------------------------
echo "Installing Python dependencies..." >&2
cd "$WORKTREE_DIR"

if [[ -f "pyproject.toml" ]] || [[ -f "setup.py" ]] || [[ -f "requirements.txt" ]]; then
    if command -v uv >/dev/null 2>&1; then
        uv sync --quiet >&2
    else
        python3 -m venv .venv >&2
        if [[ -f "pyproject.toml" ]]; then
            .venv/bin/pip install --cache-dir ~/.cache/pip -q -e ".[dev]" >&2
        elif [[ -f "requirements.txt" ]]; then
            .venv/bin/pip install --cache-dir ~/.cache/pip -q -r requirements.txt >&2
        fi
    fi
fi

# ---------------------------------------------------------------------------
# Step 4b: Install frontend dependencies (if present)
# ---------------------------------------------------------------------------
# Gate on package.json, not just the directory: some projects (e.g. a Chainlit
# Python frontend) have a frontend/ dir with no Node project, and `npm install`
# aborts with ENOENT (exit 254), failing worktree setup. Keep npm's output
# visible so a real install failure isn't swallowed by --silent.
if [[ -f "$WORKTREE_DIR/frontend/package.json" ]]; then
    echo "Installing frontend dependencies..." >&2
    cd "$WORKTREE_DIR/frontend"
    npm install --no-audit --no-fund >&2
fi

# ---------------------------------------------------------------------------
# Step 5: Generate .env with expanded values for the worktree
# ---------------------------------------------------------------------------
# Project repos may have ${VAR} references in .env that must be expanded
# before python-dotenv loads them. Copy the main .env and expand all
# $VAR / ${VAR} references using the current shell environment.
if [[ -f "$PROJECT_REPO_ROOT/.env" ]]; then
    echo "Generating worktree .env with expanded values..." >&2
    # Parse the project .env file line-by-line, expanding ${VAR} references
    # using the daemon's environment. Only keys declared in the project .env
    # are written — daemon process vars are never added.
    # Unresolved ${UNSET_VAR} references are preserved verbatim.
    while IFS= read -r line; do
        # Preserve blank lines and comment lines as-is
        if [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]]; then
            printf "%s\n" "$line"
            continue
        fi
        # Extract key from KEY=VALUE or KEY='VALUE' or KEY="VALUE"
        if [[ "$line" =~ ^([A-Za-z_][A-Za-z0-9_]*)= ]]; then
            key="${BASH_REMATCH[1]}"
            raw_value="${line#*=}"
            # Strip surrounding quotes if present
            if [[ "$raw_value" =~ ^\"(.*)\"$ ]]; then
                raw_value="${BASH_REMATCH[1]}"
            elif [[ "$raw_value" =~ ^\'(.*)\'$ ]]; then
                raw_value="${BASH_REMATCH[1]}"
            fi
            # Expand ${VAR} and $VAR references using the daemon env.
            # Walk through the value and replace references one at a time.
            expanded=""
            remaining="$raw_value"
            while [[ "$remaining" =~ (.*)\$\{([A-Za-z_][A-Za-z0-9_]*)\}(.*) ]]; do
                prefix="${BASH_REMATCH[1]}"
                var_name="${BASH_REMATCH[2]}"
                suffix="${BASH_REMATCH[3]}"
                if [[ -v "$var_name" ]]; then
                    remaining="${prefix}${!var_name}${suffix}"
                else
                    # Variable not set — preserve the literal ${VAR} token.
                    # Replace with a sentinel, process the rest, then restore.
                    # Use a unique placeholder to avoid infinite loops.
                    sentinel="__IW_SENTINEL_${var_name}__"
                    remaining="${prefix}${sentinel}${suffix}"
                fi
            done
            # Restore any sentinels back to ${VAR} form
            while [[ "$remaining" =~ __IW_SENTINEL_([A-Za-z_][A-Za-z0-9_]*)__ ]]; do
                var_name="${BASH_REMATCH[1]}"
                remaining="${remaining/__IW_SENTINEL_${var_name}__/\${${var_name}\}}"
            done
            expanded="$remaining"
            printf "%s=%s\n" "$key" "$expanded"
        else
            # Not a KEY=VALUE line — write it as-is
            printf "%s\n" "$line"
        fi
    done < "$PROJECT_REPO_ROOT/.env" > "$WORKTREE_DIR/.env"
fi

# ---------------------------------------------------------------------------
# Step 6: Sync skills from iw-ai-core
# ---------------------------------------------------------------------------
SKILLS_SRC="$IW_CORE_ROOT/skills"
SKILLS_DST="$WORKTREE_DIR/.claude/skills"

if [[ -d "$SKILLS_SRC" ]]; then
    echo "Syncing skills from $IW_CORE_ROOT/skills/ ..." >&2
    mkdir -p "$SKILLS_DST"

    # Prefer iw sync-skills (respects overrides and lock files)
    if command -v iw >/dev/null 2>&1 && cd "$WORKTREE_DIR" && iw sync-skills >/dev/null 2>&1; then
        echo "Skills synced via iw sync-skills" >&2
    else
        # Fallback: direct copy (overwrites existing, project overrides preserved by not deleting)
        echo "iw sync-skills not available, copying skills directly" >&2
        rsync -a --ignore-existing "$SKILLS_SRC/" "$SKILLS_DST/" 2>/dev/null || \
            cp -r "$SKILLS_SRC/." "$SKILLS_DST/" 2>/dev/null || true
    fi
fi

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

    WORKTREE_GITDIR=$(git -C "$WORKTREE_DIR" rev-parse --git-dir)
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

# ---------------------------------------------------------------------------
# Done — output the worktree path (consumed by the daemon)
# ---------------------------------------------------------------------------
cd "$PROJECT_REPO_ROOT"
echo "Worktree ready: $WORKTREE_DIR" >&2
echo "$WORKTREE_DIR"
