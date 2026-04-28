# I-00048_S02_CodeReview_Backend_prompt

**Work Item**: I-00048 — Prompts and manifest not copied into worktree — agents thrash on orientation every step
**Step Being Reviewed**: S01 (Backend)
**Review Step**: S02

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Not applicable for this step.

---

## Input Files

- Design document: `ai-dev/active/I-00048/I-00048_Issue_Design.md`
- S01 report: `ai-dev/active/I-00048/reports/I-00048_S01_Backend_report.md`
- Modified file: `executor/worktree_setup.sh`
- Conventions: `CLAUDE.md`, `executor/CLAUDE.md`

## Output Files

- `ai-dev/active/I-00048/reports/I-00048_S02_CodeReview_Backend_report.md`

---

## Context

You are reviewing the changes made in S01 to `executor/worktree_setup.sh`. S01 added a new step that copies `ai-dev/active/<ID>/` context files into the worktree and writes per-worktree git exclude patterns to prevent them from being committed to the branch.

Read `executor/CLAUDE.md` before reviewing — it lists critical rules for executor scripts (no docker, no alembic).

---

## Review Checklist

### 1. Correctness of the copy step

- Is the copy conditional (`if [[ -d "$ACTIVE_SRC" ]]`) so it skips silently when the directory doesn't exist?
- Is `cp -r` used (not `rsync` or other tools)?
- Does the copy target the correct path: `$WORKTREE_DIR/ai-dev/active/$ITEM_ID`?
- Is the parent directory created before copying: `mkdir -p "$(dirname "$ACTIVE_DST")"`?

### 2. Correctness of the git exclude step

- Is `WORKTREE_GITDIR` resolved via `git -C "$WORKTREE_DIR" rev-parse --git-dir`?
- Is a relative path resolved to absolute before use (guard: `if [[ "${WORKTREE_GITDIR:0:1}" != "/" ]]`)?
- Does `mkdir -p "$WORKTREE_GITDIR/info"` run before writing to the exclude file?
- Are the patterns appended (`>>`) rather than overwriting (`>`)?
- Do the exclude patterns cover:
  - `ai-dev/active/$ITEM_ID/prompts/`
  - `ai-dev/active/$ITEM_ID/workflow-manifest.json`
  - `ai-dev/active/$ITEM_ID/*.md`
- Are reports (`ai-dev/active/$ITEM_ID/reports/`) intentionally NOT excluded (agents must be able to commit them)?

### 3. Stdout hygiene

- Are all informational messages sent to stderr (`>&2`)?
- Does the final `echo "$WORKTREE_DIR"` remain the last stdout line (daemon consumes it)?
- Is there any new stdout `echo` after the new step? There must not be.

### 4. Idempotency

- If `worktree_setup.sh` is run twice (Step 1 detects existing worktree and exits 0 before reaching Step 7), is there any risk of double-copying? (Acceptable — Step 1 short-circuits before Step 7 runs.)
- If `$ACTIVE_SRC` doesn't exist, does the script continue without error?

### 5. Shell safety (set -euo pipefail context)

- Are all variables quoted properly to handle spaces in paths?
- Does the `git rev-parse --git-dir` call work correctly when `cd "$WORKTREE_DIR"` was the last `cd`?
- Any use of unquoted `$()` that could fail under `set -e`?

### 6. Conventions

- Does the step follow the same comment and structure style as the other steps (numbered header, `echo ... >&2` logging, single responsibility)?

## Test Verification (NON-NEGOTIABLE)

Run before submitting review:

```bash
make test-unit
make lint
make typecheck
```

Report results accurately.

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "I-00048",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
