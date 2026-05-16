# F-00084_S01_Pipeline_prompt

**Work Item**: F-00084 — LLM-Assisted Merge Conflict Resolution (Phase 0 + Phase 1 dry-run)
**Step**: S01
**Agent**: pipeline-impl

---

## ⛔ Docker is off-limits

Standard policy — do not run any docker commands. The merge-queue flow in this Feature does not touch docker at all.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This step adds **no migrations**.

## Input Files

- Runtime step state: `uv run iw item-status F-00084 --json`
- Design doc: `ai-dev/active/F-00084/F-00084_Feature_Design.md`
- Canonical reference: `docs/research/R-00076-llm-automated-merge-resolution.md` — **sections §5.2 (decision tree), §5.3 (integration point in worktree_commit.sh), §5.7 (event types)** are mandatory reading
- Existing logic to match-and-extend: `executor/worktree_commit.sh` (especially lines 280–360 — the existing auto-resolver for uv.lock / Makefile and the abort branch)

## Output Files

- `ai-dev/active/F-00084/reports/F-00084_S01_Pipeline_report.md` — Step report

## Context

You are implementing the Pipeline-layer plumbing for LLM-assisted merge conflict resolution. This step delivers TWO concrete artifacts:

1. A new operator-facing config file `executor/auto_merge.toml` (defaults to phase=0 — fully no-op behaviour).
2. Edits to `executor/worktree_commit.sh` that classify each conflict file against refuse-list / allowlist and emit a new `AUTO_RESOLVE_REQUESTED=<json>` stdout marker (consumed by the Backend step S03 in `merge_queue.py`).

You do NOT call any LLM in this step. You do NOT invoke any Python module. Your only job is to extend the bash conflict-detection branch so the daemon can take over.

## Requirements

### 1. Create `executor/auto_merge.toml`

Use this exact content. Comments are mandatory — operators will read this file.

```toml
# IW AI Core — Auto Merge Resolution Configuration
#
# Reference: docs/research/R-00076-llm-automated-merge-resolution.md §5
# Owner: orch/daemon/auto_merge.py (loads this file via tomllib)
#
# Phase ladder:
#   0 = plumbing only — decision tree runs, NO LLM call, NO state change.
#       Default. Safe to ship without operator action.
#   1 = dry-run — LLM is invoked for allowlisted conflicts; proposed
#       resolutions captured in DaemonEvent metadata; worktree is NEVER
#       modified; rebase is ALWAYS aborted. Operator UX unchanged.
#   2 = tests-only auto-apply — RESERVED for follow-up CR. Refuse if set.
#   3 = broader allowlist — RESERVED for follow-up CR. Refuse if set.

phase = 0

# runtime_option_id picks WHICH cli_tool + model the resolver invokes.
# This is an integer FK into agent_runtime_options.id (see F-00081).
# If null OR points to a missing/disabled row, fall back to the project's
# default agent_runtime_options row (is_default = true).
# Operators: list available options with `uv run iw projects show <project>`.
runtime_option_id = null

[allowlist]
# Conflicts whose ALL files match these globs are eligible for LLM resolution.
# Phase 1 starts narrow: test files, design-doc reports, and project docs.
patterns = [
  "tests/**/*.py",
  "docs/**/*.md",
  "ai-dev/active/**/reports/**",
  "ai-dev/active/**/I-*/reports/**",
  "ai-dev/active/**/F-*/reports/**",
  "ai-dev/active/**/CR-*/reports/**",
]

[refuselist]
# Conflicts touching ANY of these globs ALWAYS skip the LLM (defence in depth).
# Refuse-list always wins over allowlist.
patterns = [
  "orch/db/migrations/versions/*.py",
  ".gitleaks.toml",
  ".env",
  ".env.*",
  ".gitignore",
  "orch/db/identity.py",
  "orch/config.py",
  "executor/worktree_commit.sh",
  "executor/worktree_setup.sh",
  "executor/step_executor.sh",
  "executor/step_executor_lib.sh",
  "executor/scope_gate.py",
  "executor/auto_merge.toml",
  "uv.lock",
  "*.png",
  "*.jpg",
  "*.jpeg",
  "*.gif",
  "*.zst",
  "*.tar.gz",
  "*.db",
  "*.sqlite",
  "*.parquet",
]

[limits]
# Conflicts exceeding any of these are skipped (no LLM call) and recorded
# as merge_auto_resolution_skipped with reason=<limit_name>.
max_conflict_hunk_lines = 80
max_conflicted_files_per_merge = 5
max_file_size_bytes = 256000
# Hard cap on DaemonEvent.metadata JSON size to prevent JSONB row inflation.
max_event_metadata_bytes = 262144
# LLM call timeout per file.
llm_call_timeout_seconds = 120
```

### 2. Edit `executor/worktree_commit.sh`

The existing flow at lines 309–358 has this shape:

```bash
if [[ "$(git merge-base HEAD main)" == "$MAIN_SHA" ]]; then
    # no rebase needed
else
    if git rebase main 2>&1; then
        # rebase ok
    else
        # conflict path:
        #   - get conflicting file list
        #   - apply --ours rule (uv.lock) / --theirs rule (Makefile)
        #   - if any "blocking" file remains → emit ERROR + abort
fi
```

**Required edits (insert between the existing auto-resolve loop and the abort branch):**

a. Read `executor/auto_merge.toml`'s **phase value only** in bash. Use a minimal `grep -E '^phase = ' executor/auto_merge.toml | awk -F= '{print $2}' | tr -d ' '` — full TOML parsing is the Python side's job. **Default to phase=0 if the file is missing or grep returns empty.** Phase value is captured into `AUTO_MERGE_PHASE`.

b. For each `_blocking` file in the existing conflict loop, classify it against the refuse-list. **Defence-in-depth: bash classification is intentionally a coarse pattern match** (the Python side does the rich-glob classification). Bash refuse-list is **path-prefix and suffix matching** against this short list:

```bash
_REFUSE_PREFIXES=(
  "orch/db/migrations/versions/"
  "executor/"
  ".env"
  ".gitleaks.toml"
  ".gitignore"
  "orch/db/identity.py"
  "orch/config.py"
  "uv.lock"
)
_REFUSE_SUFFIXES=(
  ".png" ".jpg" ".jpeg" ".gif" ".zst" ".tar.gz" ".db" ".sqlite" ".parquet"
)
```

If the conflict file path starts with ANY prefix OR ends with ANY suffix → mark refuse-listed; do NOT include in the auto-resolve emit set.

c. Build TWO arrays from the unresolved-blocking files:
   - `_refuse_files=()` — files matching refuse-list
   - `_eligible_files=()` — files NOT matching refuse-list (eligible for LLM in the Python decision tree)

d. **Emit decision-tree outcome to stdout:**

   - If `_refuse_files` is non-empty AND `_eligible_files` is empty:
     - Behaviour identical to today: emit existing ERROR lines + `CONFLICT_FILES=<json>` marker; abort the rebase; exit 1.
     - Additionally emit `AUTO_RESOLVE_SKIPPED=<json>` where the JSON is `{"reason": "refuse_list", "refuse_files": [...], "eligible_files": []}`.

   - If `_refuse_files` is non-empty AND `_eligible_files` is also non-empty:
     - Refuse-list wins (defence-in-depth). Emit `AUTO_RESOLVE_SKIPPED=<json>` with `{"reason": "mixed_refuse_list", "refuse_files": [...], "eligible_files": [...]}`. Abort rebase, exit 1.

   - If `_refuse_files` is empty AND `_eligible_files` is non-empty:
     - Emit `AUTO_RESOLVE_REQUESTED=<json>` where the JSON is `{"eligible_files": [...], "branch": "<BRANCH_NAME>", "main_sha": "<MAIN_SHA>"}`.
     - Also emit the existing `CONFLICT_FILES=<json>` marker so today's parser still works.
     - Abort the rebase (yes, even when Phase 1 is allowed — the bash side ALWAYS aborts in Phase 0/1; the Python side decides whether to call the LLM and whether to apply). Exit 1.
     - This is intentional: bash hands the decision to the Python merge_queue.py via the stdout marker. Phase 2 will introduce a non-aborting path with `--resume-rebase`.

e. **Use `jq` if available; provide an `awk`-based fallback** (the existing code at lines 362–373 has this pattern — re-use it verbatim).

### 3. Add `--resume-rebase` flag (stub)

`worktree_commit.sh` accepts positional args today. Add a flag `--resume-rebase` parsed at the top of the script. In Phase 1 it MUST be a hard error:

```bash
if [[ "$1" == "--resume-rebase" ]]; then
    echo "[worktree_commit] ERROR: --resume-rebase is reserved for Phase 2 (auto-apply path). Phase 1 is dry-run only." >&2
    exit 2
fi
```

This plants the CLI surface so the daemon's call site can be wired in Phase 2 without re-touching this script. Including the explicit refusal also produces a clear error if anything is misconfigured.

### 4. Inline documentation

At the top of the new block in `worktree_commit.sh`, add a comment block:

```bash
# F-00084: LLM-assisted merge resolution — Phase 0/1 plumbing.
# Reference: docs/research/R-00076-llm-automated-merge-resolution.md §5.2-§5.3.
#
# This script's job in F-00084 is purely classification + stdout marker emission.
# The Python merge_queue.py reads AUTO_RESOLVE_REQUESTED and decides whether to
# invoke the LLM (per executor/auto_merge.toml's phase). In Phase 0 and Phase 1,
# this script always aborts the rebase — never resolves.
```

## Project Conventions

- Read `executor/CLAUDE.md` for rules specific to executor bash scripts. **Critical**: executor scripts MUST NOT call docker or alembic. The R1/R2 rules apply.
- Use `set -euo pipefail` semantics consistent with the existing script (don't change the script's existing shell-mode settings).
- Quote variable expansions defensively; `worktree_commit.sh` already uses defensive quoting — match its style.
- The existing script uses `>&2` for log lines and stdout for markers (`CONFLICT_FILES=` etc.). Maintain that separation: new markers go to stdout, log messages go to stderr.

## TDD Requirement

This step is bash-only; the behavioural tests for the new markers live in S06 (Tests step). For S01 you must:

1. **RED phase** — write a tiny shell-level test script (do NOT commit it; it's for your own verification) that:
   - Sets up two fresh git worktrees with a pre-fabricated conflict on `tests/integration/test_foo.py`.
   - Runs `bash executor/worktree_commit.sh` against it.
   - Confirms `AUTO_RESOLVE_REQUESTED=` appears on stdout BEFORE your edits the test would fail (no marker).
2. **GREEN phase** — apply your edits and re-run the shell test; confirm `AUTO_RESOLVE_REQUESTED=` is emitted with the expected file list.
3. Similarly verify a refuse-list path produces `AUTO_RESOLVE_SKIPPED=` instead.
4. Verify `--resume-rebase` exits 2 with the documented message.

Record the manual verification in your report.

S06 will turn these into proper pytest integration tests; your job in S01 is to prove the script behaves correctly before handoff.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format` — should be a no-op for shell scripts; if it touches anything, inspect and stage.
2. `make lint` — must report zero errors. This includes `scripts/check_templates.py` (Jinja2 templates) and `node --check` for dashboard JS. Your bash edits will be checked by shellcheck if it's wired in (check `Makefile:lint` target).
3. `make typecheck` — must report zero errors. Your changes don't touch Python in this step, but make sure nothing else in the worktree drifted.

## Test Verification

- This step writes bash only. Run only the targeted shell test from your own RED/GREEN verification.
- Do NOT run `make test-integration` or `make test-unit` — those are downstream QV gates.
- The integration test for the new markers belongs to S06.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "pipeline-impl",
  "work_item": "F-00084",
  "completion_status": "complete",
  "files_changed": [
    "executor/auto_merge.toml",
    "executor/worktree_commit.sh"
  ],
  "preflight": {
    "format": "ok",
    "typecheck": "ok",
    "lint": "ok"
  },
  "tests_passed": true,
  "test_summary": "manual shell-level verification: AUTO_RESOLVE_REQUESTED emitted; refuse-list path emits AUTO_RESOLVE_SKIPPED; --resume-rebase exits 2",
  "tdd_red_evidence": "n/a — bash/TOML edits only; behavioural pytest coverage lives in S06",
  "blockers": [],
  "notes": "Phase 0 default in auto_merge.toml — no operator-visible behaviour change on merge. Decision tree classification is wired but Python side will decide whether to actually call the LLM."
}
```
