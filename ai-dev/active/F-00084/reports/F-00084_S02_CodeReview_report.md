# F-00084 S02 Code Review Report

**Step**: S02
**Agent**: code-review-impl
**Date**: 2026-05-16
**Reviewing**: S01 Pipeline implementation (pipeline-impl)
**Files reviewed**:
- `executor/auto_merge.toml` (new)
- `executor/worktree_commit.sh` (modified)
**Reference documents**: `ai-dev/active/F-00084/F-00084_Feature_Design.md`, `docs/research/R-00076-llm-automated-merge-resolution.md`

---

## 1. Summary

The S01 implementation correctly delivers the `auto_merge.toml` configuration file and the `--resume-rebase` guard in `executor/worktree_commit.sh`. The classification logic (refuse-list vs eligible) and the JSON marker emission are structurally sound, and no python modules were touched prematurely. However, there is one HIGH-severity defect: the `CONFLICT_FILES` marker that existing F-00076 parser code depends on is **not emitted** in the blocking-conflict branch. The comment at line 472 promises this emission ("Also emit existing CONFLICT_FILES marker so today's parser still works") but the actual `echo` statement is absent. Additionally, the `AUTO_RESOLVE_SKIPPED` marker (both for refuse-list and mixed cases) is missing the `branch` and `main_sha` fields that the review checklist requires and that the Python side will likely need. One MEDIUM defect is that the phase value from `_phase_raw` is never validated as an integer before being stored in `AUTO_MERGE_PHASE`, making it vulnerable to a whitespace-containing or non-numeric line in the TOML.

---

## 2. Decision

**request_changes**

Two issues must be corrected before S03 begins:

1. The `CONFLICT_FILES` marker must be emitted in the blocking branch (HIGH).
2. The `AUTO_RESOLVE_SKIPPED` marker should carry `branch` and `main_sha` fields for consistency with `AUTO_RESOLVE_REQUESTED` and for S03's Python parser (HIGH based on checklist requirement for those fields).

---

## 3. Findings

| ID | Severity | File | Line(s) | Description | Recommendation |
|----|----------|------|---------|-------------|----------------|
| F001 | HIGH | `executor/worktree_commit.sh` | 471–473 | `CONFLICT_FILES` marker is NOT emitted in the blocking branch. Line 472 has a comment "Also emit existing CONFLICT_FILES marker so today's parser still works" but no `echo` statement follows. The `CONFLICT_FILES` marker only appears on lines 489–506, which is the **auto-resolved** path (i.e., no blocking files). The F-00076 parser in `merge_queue.py` reads `CONFLICT_FILES` to learn which files conflicted. Without this marker in the blocking path, the operator's conflict-file list will be empty and the existing `merge_conflict` DaemonEvent will have no `conflict_files` payload. This breaks AC4 invariant ("merge_conflict DaemonEvent fires with the conflict file list"). | After the `if/elif/elif` block but before `git rebase --abort`, emit `CONFLICT_FILES` using the same jq/awk pattern already present on lines 489–506. Populate it from the `_blocking` variable (all blocking files, matching today's semantics). |
| F002 | HIGH | `executor/worktree_commit.sh` | 459, 464 | `AUTO_RESOLVE_SKIPPED` marker does not include `branch` or `main_sha` fields. The review checklist states both markers' JSON must include `eligible_files`, `refuse_files`, `branch`, `main_sha`, and `reason`. The `AUTO_RESOLVE_REQUESTED` marker at line 471 correctly includes `branch` and `main_sha`, but the two `AUTO_RESOLVE_SKIPPED` branches (refuse-only at line 459 and mixed at line 464) omit these fields. The Python parser in S03 will need `branch` and `main_sha` to record the correct DaemonEvent metadata even on skip paths. | Add `"branch": "${BRANCH_NAME}", "main_sha": "${MAIN_SHA}"` to both `AUTO_RESOLVE_SKIPPED` JSON objects. |
| F003 | MEDIUM | `executor/worktree_commit.sh` | 368–371 | Phase value from TOML is accepted as-is without integer validation. If the TOML file has a syntactically valid but non-integer value (e.g. `phase = "one"` or trailing comment `phase = 0  # default`), `_phase_raw` will be non-empty and the non-integer string will be stored in `AUTO_MERGE_PHASE`. The design's "If grep finds the phase line but value is non-integer, treat as 0 (defensive)" requirement is not implemented. | After assigning `_phase_raw`, add: `if ! [[ "$_phase_raw" =~ ^[0-9]+$ ]]; then _phase_raw=""; fi` before checking `if [[ -n "$_phase_raw" ]]; then`. |
| F004 | MEDIUM | `executor/auto_merge.toml` | 39–63 | The refuselist is missing `pyproject.toml`. R-00076 §2.4 lists `pyproject.toml` (specifically `[project]` and `[tool.alembic]` sections) as a "Never Automate" file because dependency-graph changes need `uv lock` regeneration, not LLM edits. It is not in the Feature Design's explicit list, but is referenced in the research document that reviewers must cross-check. | Add `"pyproject.toml"` to the `[refuselist] patterns` in `executor/auto_merge.toml`. Even if the Feature Design does not enumerate it explicitly, the research document (canonical reference per §Notes) does. |
| F005 | LOW | `executor/worktree_commit.sh` | 477 | The error-log loop at line 477 uses `$_blocking` (bare variable with word splitting) rather than iterating over the array `_blocking_files`. Consistent with the existing style, but after the `SC2206` array conversion it would be cleaner (and shellcheck-quieter) to use `"${_blocking_files[@]}"`. | Change `for _bf in $_blocking; do` to `for _bf in "${_blocking_files[@]}"; do` (minor style nit, not a bug). |
| F006 | LOW | `executor/auto_merge.toml` | 27–34 | The allowlist includes `"ai-dev/active/**/I-*/reports/**"`, `"ai-dev/active/**/F-*/reports/**"`, and `"ai-dev/active/**/CR-*/reports/**"` in addition to the generic `"ai-dev/active/**/reports/**"`. The three ID-specific patterns are subsumed by the generic pattern. They are not harmful, but they add noise. | Remove the three redundant sub-patterns, keeping only `"ai-dev/active/**/reports/**"`. |

---

## 4. Checklist Results

| Checklist Item | Result | Notes |
|----------------|--------|-------|
| `executor/auto_merge.toml` exists with `phase = 0` default | PASS | File present, `phase = 0` at line 15 |
| Allowlist patterns scoped to `tests/**`, `docs/**`, `ai-dev/active/**/reports/**` only | PASS | All three base patterns present; extra redundant ID-specific variants present (LOW F006) |
| `runtime_option_id = null` default | PASS | Line 22: `runtime_option_id = null` |
| Comments explain phase ladder, runtime_option_id fallback, refuse-list defence-in-depth | PASS | Header comment block covers all three clearly |
| Refuselist includes `orch/db/migrations/versions/*.py` | PASS | Line 40 |
| Refuselist includes `.gitleaks.toml` | PASS | Line 41 |
| Refuselist includes `.env` and `.env.*` | PASS | Lines 42–43 |
| Refuselist includes `.gitignore` | PASS | Line 44 |
| Refuselist includes `orch/db/identity.py` | PASS | Line 45 |
| Refuselist includes `orch/config.py` | PASS | Line 46 |
| Refuselist includes all `executor/*.sh` | PASS | Lines 47–50 (four executor scripts by name) |
| Refuselist includes `executor/scope_gate.py` | PASS | Line 51 |
| Refuselist includes `executor/auto_merge.toml` | PASS | Line 52 |
| Refuselist includes `uv.lock` | PASS | Line 53 |
| Refuselist includes binary suffixes (png, jpg, zst, tar.gz, db, sqlite, parquet) | PASS | Lines 54–62 |
| New code inserted in conflict branch, before abort, not on happy path | PASS | Inserted inside `if [[ -n "$_blocking" ]]; then` (line 355), before abort at line 483 |
| `--resume-rebase` flag parsed and exits 2 with error message | PASS | Lines 47–50; message goes to stderr, exit 2 returned |
| `AUTO_RESOLVE_REQUESTED` emitted on stdout (not stderr) | PASS | Line 471: plain `echo` (stdout) |
| `AUTO_RESOLVE_SKIPPED` emitted on stdout (not stderr) | PASS | Lines 459, 464: plain `echo` (stdout) |
| `AUTO_RESOLVE_REQUESTED` JSON includes `eligible_files`, `branch`, `main_sha` | PASS | Line 471 |
| `AUTO_RESOLVE_SKIPPED` JSON includes `branch` and `main_sha` | FAIL | Lines 459, 464 both omit `branch` and `main_sha` (F002) |
| `CONFLICT_FILES` marker STILL emitted on every conflict in blocking path | FAIL | Comment at line 472 promises it but no `echo` is present in blocking path (F001) |
| Rebase is ALWAYS aborted in Phase 0/1 (no `git rebase --continue`) | PASS | Line 483: `git rebase --abort`; no `--continue` in blocking path |
| Existing `_REBASE_TAKE_OURS` / `_REBASE_TAKE_THEIRS` behaviour unchanged | PASS | Lines 344–352 untouched; new block only activates when `$_blocking` is non-empty |
| Bash refuse-list is coarse defence-in-depth (prefix + suffix) | PASS | Lines 381–393 |
| No new dependencies (no yq, no python -c) | PASS | Only grep/awk/jq/printf — all pre-existing patterns |
| Phase parsing defaults to 0 when file is missing | PASS | `AUTO_MERGE_PHASE=0` set before file check (line 366) |
| Phase parsing defensive on non-integer value | FAIL | No integer validation on `_phase_raw` (F003) |
| Inline comment cites R-00076 | PASS | Line 357: "Reference: docs/research/R-00076-llm-automated-merge-resolution.md §5.2-§5.3" |
| Comment explains Phase 0/1 always-abort invariant | PASS | Lines 361–362 state this explicitly |
| No Python module touched in S01 | PASS | Only `executor/` files changed |
| No test file touched in S01 | PASS | No `tests/` changes |
| `executor/CLAUDE.md` rules respected (no docker, no alembic) | PASS | No docker or alembic invocations anywhere in new code |

---

## 5. Detailed Analysis

### F001 — Missing `CONFLICT_FILES` emit in blocking branch (HIGH)

The existing `merge_queue.py` (pre-F-00084) parses stdout for the `CONFLICT_FILES` marker to populate the `merge_conflict` DaemonEvent. The design requires this marker to continue working after S01. Looking at the code:

- Lines 487–506: `CONFLICT_FILES` is built and emitted only in the "all auto-resolved" path (i.e., after the `if [[ -n "$_blocking" ]]; then` block exits without the early `exit 1`).
- Inside the blocking branch (lines 355–484), the comment at line 472 says the marker will be emitted, but no `echo` statement follows.

This means every conflict that is not auto-resolvable by the existing uv.lock/Makefile rules will produce NO `CONFLICT_FILES` marker on stdout. The Python side will see only `AUTO_RESOLVE_REQUESTED` or `AUTO_RESOLVE_SKIPPED`, but not the conflict file list that the existing merge_conflict event population depends on.

**Fix**: After computing `_refuse_json` and `_eligible_json` (but before the `if/elif/elif` block, or immediately after it), build and emit a `CONFLICT_FILES` marker for ALL blocking files. This is straightforward to do using the same jq/awk pattern at lines 490–505, applied to the `_blocking` variable.

### F002 — `AUTO_RESOLVE_SKIPPED` missing `branch` and `main_sha` (HIGH)

The review checklist mandates that both markers include `eligible_files`, `refuse_files`, `branch`, `main_sha`, and `reason`. The `AUTO_RESOLVE_REQUESTED` marker is correct; the two `AUTO_RESOLVE_SKIPPED` emit points are not:

- Line 459: `{"reason": "refuse_list", "refuse_files": ..., "eligible_files": []}` — missing `branch` and `main_sha`.
- Line 464: `{"reason": "mixed_refuse_list", "refuse_files": ..., "eligible_files": ...}` — same omission.

`BRANCH_NAME` and `MAIN_SHA` are both set before the conflict-handling block (lines 188 and 308 respectively), so they are available.

### F003 — Phase value not validated as integer (MEDIUM)

The design doc (Boundary Behavior table) states: "If grep finds the phase line but value is non-integer, treat as 0 (defensive)." The grep pattern `^phase = ` with awk `{print $2}` and `tr -d ' '` will strip the leading space around `=`, but it will also happily extract values like `"0"`, `0#comment`, or `"one"` without complaint. A comment on the same line as `phase = 0` (e.g. `phase = 0  # plumbing`) would produce `0` correctly only after `tr -d ' '` removes trailing spaces — actually that case works because the comment starts with `#` and awk splits on `=`, giving `0  # plumbing` for field 2, and `tr -d ' '` strips to `0#plumbing`. This means a commented phase line could accidentally set `AUTO_MERGE_PHASE=0#plumbing`, which the Python side might choke on.

The fix is a simple regex guard: `if ! [[ "$_phase_raw" =~ ^[0-9]+$ ]]; then _phase_raw=""; fi` before the non-empty check.

### F004 — `pyproject.toml` absent from refuselist (MEDIUM)

R-00076 §2.4 explicitly lists `pyproject.toml` as "Never Automate" because dep-graph changes require `uv lock` regeneration, not LLM text editing. While the Feature Design's `auto_merge.toml` snippet in R-00076 §5.2 does include it, the implemented `executor/auto_merge.toml` does not. The notes section of the Feature Design states "R-00076 is the canonical reference" and reviewers "MUST cross-check implementation against R-00076 §5". Since the bash prefix-list does not explicitly cover `pyproject.toml` either (it would not be caught by the `executor/` prefix or any suffix), a conflict in `pyproject.toml` would be classified as eligible and forwarded to the Python side — where the rich-glob classifier could potentially let it through if the Python refuselist also has this gap.

---

```json
{
  "decision": "request_changes",
  "findings": [
    {
      "id": "F001",
      "severity": "HIGH",
      "file": "executor/worktree_commit.sh",
      "line": 472,
      "description": "CONFLICT_FILES marker is promised by comment but never emitted in the blocking-conflict branch. The only CONFLICT_FILES emit is in the auto-resolved path (line 506), which is mutually exclusive with the blocking path. The F-00076 parser depends on this marker to populate merge_conflict DaemonEvent with conflict_files. Without it, every blocking conflict will emit a merge_conflict event with an empty conflict_files list, breaking AC4.",
      "recommendation": "After the if/elif/elif classification block (after line 473), and before git rebase --abort (line 483), build and emit the CONFLICT_FILES marker using the _blocking variable and the same jq/awk pattern already at lines 490-505."
    },
    {
      "id": "F002",
      "severity": "HIGH",
      "file": "executor/worktree_commit.sh",
      "line": 459,
      "description": "AUTO_RESOLVE_SKIPPED JSON at lines 459 and 464 is missing 'branch' and 'main_sha' fields. The review checklist requires both markers to include branch, main_sha, eligible_files, refuse_files, and reason. AUTO_RESOLVE_REQUESTED at line 471 is correct. The Python S03 parser will need these fields for DaemonEvent metadata even on the skipped path.",
      "recommendation": "Add '\"branch\": \"${BRANCH_NAME}\", \"main_sha\": \"${MAIN_SHA}\"' to both AUTO_RESOLVE_SKIPPED JSON objects. Both variables are available in scope."
    },
    {
      "id": "F003",
      "severity": "MEDIUM",
      "file": "executor/worktree_commit.sh",
      "line": 368,
      "description": "Phase value from TOML is not validated as an integer. If the line contains trailing content (e.g. phase = 0  # comment), awk will produce '0  # comment' and tr -d ' ' will give '0#comment', which is non-numeric. The design requires treating non-integer values as 0.",
      "recommendation": "Add a regex guard after extracting _phase_raw: 'if ! [[ \"$_phase_raw\" =~ ^[0-9]+$ ]]; then _phase_raw=\"\"; fi'"
    },
    {
      "id": "F004",
      "severity": "MEDIUM",
      "file": "executor/auto_merge.toml",
      "line": 39,
      "description": "pyproject.toml is absent from the [refuselist] patterns. R-00076 §2.4 explicitly lists it as 'Never Automate' because dependency-graph changes need uv lock regeneration, not LLM text editing. A conflict in pyproject.toml would currently be classified as eligible for LLM resolution.",
      "recommendation": "Add '\"pyproject.toml\"' to [refuselist] patterns. Also add it to the bash _REFUSE_PREFIXES in worktree_commit.sh (exact filename match, not a prefix, so use a dedicated check or add 'pyproject.toml' to a separate exact-match list)."
    },
    {
      "id": "F005",
      "severity": "LOW",
      "file": "executor/worktree_commit.sh",
      "line": 477,
      "description": "Error-log loop at line 477 uses bare $_blocking (word-split) rather than the array _blocking_files that was constructed earlier. Not a correctness bug for files without spaces, but inconsistent with the SC2206 suppressed array conversion two lines earlier.",
      "recommendation": "Change 'for _bf in $_blocking; do' to 'for _bf in \"${_blocking_files[@]}\"; do'."
    },
    {
      "id": "F006",
      "severity": "LOW",
      "file": "executor/auto_merge.toml",
      "line": 33,
      "description": "Allowlist includes three redundant ID-specific patterns (ai-dev/active/**/I-*/reports/**, ai-dev/active/**/F-*/reports/**, ai-dev/active/**/CR-*/reports/**) that are all subsumed by the generic ai-dev/active/**/reports/** pattern on line 31.",
      "recommendation": "Remove the three ID-specific patterns to reduce noise. The generic pattern already covers them."
    }
  ]
}
```
