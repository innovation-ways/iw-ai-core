# F-00084 S04 Code Review Report

**Step**: S04 — code-review-impl
**Work Item**: F-00084 — LLM-Assisted Merge Conflict Resolution (Phase 0 + Phase 1 dry-run)
**Agent under review**: S03 backend-impl
**Files also reviewed**: S06 test files (per checklist scope)
**Date**: 2026-05-16

---

## Summary

The S03 backend implementation is architecturally sound and the three most critical safety invariants are confirmed intact: Phase 0 never calls the LLM, Phase 1 never mutates the worktree (no `git add`, no `git rebase --continue` anywhere in `auto_merge.py`), and the existing `merge_conflict` event plus `BatchItem.status = merge_failed` always fire unconditionally.

However, **four HIGH findings require fixes before merging to production**:

1. **F-01 (HIGH)** — ABSTAIN detection uses `startswith("ABSTAIN")` instead of the spec-required exact-match `== "ABSTAIN"`. A valid Python file starting with `ABSTAIN_REASONS = [...]` would be silently discarded.
2. **F-02 (HIGH)** — `classify_conflicts()` returns `skipped_reason="refuse_list"` for mixed refuse+allow conflicts, but the Feature Design boundary table requires `"mixed_refuse_list"`. The S06 tests accept the incorrect value — they test the current (wrong) behavior, not the spec.
3. **F-03 (HIGH)** — `reload_config()` and `_cached_config` are dead code. The SIGHUP handler in `main.py` (lines 677-681) does not call `auto_merge.reload_config()`. AC6 works incidentally (fresh load per merge event), but the cache is never populated and creates a maintenance hazard.
4. **F-04 (HIGH)** — Decision tree checks file-size (step 3) before hunk-size (step 4), but the design spec requires hunk-size before file-size. When a file is both oversized-in-bytes and has oversized hunks, the wrong `skipped_reason` is emitted in the audit trail.

Two MEDIUM findings: F-05 (hardcoded PATH breaks non-standard LLM installations) and F-06 (failure-path event metadata not capped at 256 KB, unlike the success path).

All 69 unit tests pass. The S06 integration tests (119 tests) also pass, but they test the current behavior rather than the spec for F-01 and F-02.

---

## Files Reviewed

- `orch/daemon/auto_merge.py` (new, 1140 lines) — S03 backend implementation
- `orch/daemon/merge_queue.py` (modified by S03) — auto-merge integration
- `executor/step_executor_lib.sh` (modified by S03) — one-shot LLM invocation
- `executor/auto_merge.toml` (new) — phase/allowlist/refuselist config
- `tests/unit/test_auto_merge_config.py` — S03 RED stubs + S06 expansion
- `tests/unit/test_auto_merge_classifier.py` — S06 expansion
- `tests/unit/test_auto_merge_invoke.py` — S06 new file
- `tests/unit/test_auto_merge_marker.py` — S06 expansion
- `tests/unit/test_auto_merge_prompt.py` — S06 expansion
- `tests/integration/auto_merge_fixtures.py` — S06 new file
- `tests/integration/test_auto_merge_phase1.py` — S06 new file
- `tests/integration/test_auto_merge_refuse_list.py` — S06 new file
- `tests/integration/daemon/test_merge_queue_auto_merge.py` — S06 new file

---

## Checklist Results

### Module structure

| Check | Status |
|-------|--------|
| `orch/daemon/auto_merge.py` exists with all required dataclasses and functions | OK |
| All four event-type string constants defined and used consistently | OK — five constants defined: the four required plus `EVENT_AUTO_MERGE_CONFIG_INVALID` |
| `PHASE_*` constants defined; `phase >= 2` raises `ValueError` | OK — `PHASE_DISABLED=0`, `PHASE_DRY_RUN=1`, `PHASE_TESTS_ONLY=2`, `PHASE_BROADER=3`; `attempt_resolution` raises `ValueError` for phase >= 2 |

### Phase-0 short-circuit (Invariant 2)

| Check | Status |
|-------|--------|
| `attempt_resolution()` with `phase==0` never calls subprocess for LLM | OK — returns at line 858 before any subprocess invocation |
| Phase-0 path emits `merge_auto_resolution_skipped` with `reason="phase_0"` | OK — lines 848-856 |
| Unit test asserting `subprocess.run` NOT called in Phase 0 | FINDING — test uses `FakeLLM.calls==0` (adequate substitute, but not subprocess-level) |

### Dry-run never-applies (Invariant 3)

| Check | Status |
|-------|--------|
| No `git add`, `git rebase --continue`, or index-mutating subprocess in Phase 1 | OK — confirmed by `grep` across full file; zero such calls |
| `attempt_resolution()` returns `success=False` on EVERY Phase 1 code path | OK — line 1004: `AutoMergeResult(success=False, ...)` unconditional |
| Test asserts worktree index/HEAD unchanged after `attempt_resolution()` | OK — `test_invariant3_phase1_never_modifies_worktree` snapshots HEAD and `git status --porcelain` |

### Classification correctness

| Check | Status |
|-------|--------|
| Decision tree order: refuse-list > binary > oversized hunk > oversized file > too-many-files > not-allowlisted > eligible | **FINDING F-04** — order is: refuse-list > binary > file-size > hunk-size > too-many-files. Steps 3 and 4 are swapped vs spec |
| Mixed refuse-list + eligible → `skipped_reason="mixed_refuse_list"` | **FINDING F-02** — returns `"refuse_list"` regardless of whether eligible files also exist |
| Binary detection reads file bytes (null byte in first 8KB) OR suffix match | OK — `_is_binary_file()` checks suffix (line 305) then `\x00` in first 8192 bytes (line 308) |
| `fnmatch.fnmatchcase` used for glob matching | OK — lines 373, 467 |
| Empty `eligible_files` after allowlist filtering → `skipped_reason="not_allowlisted"` | OK — lines 463-478 |

### Prompt builder (R-00076 §5.5)

| Check | Status |
|-------|--------|
| All 5 prompt sections present | OK — work-item header, file purpose/path, three-way content (:1:, :2:, :3:), commit logs (both sides), instructions with ABSTAIN clause |
| `prompt_hash = sha256(prompt)` computed and stored in `LLMCallResult` | OK — line 697 |
| Description truncated to ~500 words | OK — line 513: `" ".join(words[:500])` |
| No environment variables or credentials leak into the prompt | OK — `build_resolution_prompt` takes only explicit arguments; no `os.environ` access |
| Prompt is deterministic (no `datetime.now()`, no random) | OK — unit test `test_prompt_is_deterministic` runs 10 invocations |

### LLM invocation

| Check | Status |
|-------|--------|
| `invoke_llm_for_file()` uses `step_executor_lib.sh` via subprocess | OK — lines 701-717: `bash step_executor_lib.sh auto_merge_resolve <cli_tool> <model>` |
| Timeout = `config.llm_call_timeout_seconds`; timeout maps to `LLMCallResult(error=...)` | OK — line 712, `TimeoutExpired` handled at lines 718-733 |
| Non-zero exit captured in `LLMCallResult.error` | OK — lines 754-772 |
| ABSTAIN token detection is exact-match-after-strip | **FINDING F-01** — `stdout.upper().startswith("ABSTAIN")` at line 776; should be `stdout.strip().upper() == "ABSTAIN"` |
| `(cli_tool, model)` resolved via `_resolve_runtime_option`; fallback to project default | OK — `_resolve_runtime_option()` is the only source; explicit ID → project default → None |

### merge_queue.py integration

| Check | Status |
|-------|--------|
| New code inserted AFTER `_CONFLICT_MARKER_RE` parse and BEFORE `merge_failed` | OK — merge_failed set at line 446; auto-merge code lines 461-553; merge_conflict at 560 |
| Existing `merge_conflict` DaemonEvent still fires on every conflict | OK — line 560, unconditional |
| Existing `BatchItem.status = merge_failed` still executes | OK — line 446, set before any new code |
| All new code inside try/except so exception cannot prevent failure handling | OK — lines 473-481 (skip path try/except) and 482-553 (resolve path try/except) |
| Event emission order preserved | OK — `merge_auto_resolution_attempted` → LLM calls → `merge_auto_resolved|failed|skipped` → `merge_conflict` |
| Event metadata payload size checked against `max_event_metadata_bytes` | **FINDING F-06** — size cap applied only in success path (lines 984-989), not in failure path (lines 941-960) |

### step_executor_lib.sh extension

| Check | Status |
|-------|--------|
| `auto_merge_resolve` case branch added | OK — lines 637-645, guarded by `BASH_SOURCE[0] == ${0}` |
| `_run_agent_oneshot` is new and minimal: stdin → LLM CLI → stdout, no DB writes, no PID files | OK — lines 610-628: reads stdin, calls `claude --print` or `opencode run`, no iw step-done |
| No regression to existing step-launch flow | OK — all existing functions unchanged; new code is additive and isolated |

### Config loader

| Check | Status |
|-------|--------|
| `AutoMergeConfig.load()` uses `tomllib` (stdlib) | OK — `import tomllib` at line 21 |
| Missing file → defaults (no exception to caller) | OK — lines 174-177: `FileNotFoundError` → `(cls.defaults(), None)` |
| Malformed TOML → defaults + sentinel | OK — lines 195-198: `TOMLDecodeError` → `(cls.defaults(), error_str)` |
| Reserved phase (>= 2) → consumer refuses with `ValueError` | OK — `attempt_resolution` at line 843 |

### Hot reload

| Check | Status |
|-------|--------|
| SIGHUP path re-reads `executor/auto_merge.toml` via cache | **FINDING F-03** — `reload_config()` and `_cached_config` are dead code; SIGHUP handler in `main.py` (lines 677-681) does NOT call `auto_merge.reload_config()` |
| Reload integrated with existing project_registry SIGHUP | PARTIAL — AC6 works incidentally because `merge_queue.py` loads config fresh on each conflict event |

### Logging and audit

| Check | Status |
|-------|--------|
| Each public function logs at INFO with `item_id` (and `file_path` where applicable) | OK — confirmed in `classify_conflicts`, `build_resolution_prompt`, `invoke_llm_for_file`, `attempt_resolution`, `emit_skipped_event`, `emit_config_invalid_event` |
| Logger is `logging.getLogger(__name__)` | OK — line 31 |
| No PII leakage in logs (descriptions not logged in full) | OK — only `item_id`, `file_path`, `phase`, `cli_tool`, `model` in log messages |

### Invariant coverage

| Invariant | Status |
|-----------|--------|
| Inv 1 (refuse-list → 0 LLM tokens) | OK — `classify_conflicts` returns non-None `skipped_reason`; `merge_queue.py` calls `emit_skipped_event` instead of `attempt_resolution` |
| Inv 2 (phase 0 → 0 LLM tokens) | OK — `attempt_resolution` returns before `invoke_llm_for_file`; `FakeLLM.calls==0` verified |
| Inv 3 (Phase 1 never `git add`/`git rebase --continue`) | OK — zero such calls anywhere in `auto_merge.py`; runtime git-state snapshot test passes |
| Inv 4 (operator UX unchanged) | OK — `merge_conflict` and `merge_failed` always fire |
| Inv 5 (event_metadata <= 256 KB) | PARTIAL — truncation applied in success path only; failure path is unbounded (F-06) |
| Inv 6 (decision tree deterministic) | OK — no `datetime.now()`, no random; unit test confirms |
| Inv 7 (agent + model = configured) | OK — `_resolve_runtime_option` is the only source |
| Inv 8 (failed LLM leaves clean state) | OK — `invoke_llm_for_file` returns `LLMCallResult` on all failure paths without filesystem writes |

### Project conventions

| Check | Status |
|-------|--------|
| `DaemonEvent.metadata` accessed via `event_metadata` (not `metadata`) | OK — line 1077 |
| Sync SQLAlchemy only (no `async def`) | OK |
| Type hints throughout | OK |

### Out-of-scope guard

| Check | Status |
|-------|--------|
| No new Alembic migration files | OK |
| `executor/worktree_commit.sh` edits are S01 work (not introduced by S03) | OK — `git diff HEAD` shows `worktree_commit.sh` as modified but S03 did not touch it |
| No API or frontend changes | OK |

---

## Findings

### HIGH

**F-01 — ABSTAIN detection uses prefix match, not exact match**

- **File**: `orch/daemon/auto_merge.py`, line 776
- **Code**: `if stdout.upper().startswith("ABSTAIN"):`
- **Description**: After `stdout = result.stdout.strip()`, any LLM output whose first line begins with `ABSTAIN` (e.g., a Python file containing `ABSTAIN_REASONS = [...]` or `ABSTAINING_FROM_CHANGE = True` as its first content) is incorrectly treated as a model abstention and its content is silently discarded. The prompt instructs the LLM to output exactly the single word `ABSTAIN` on its own line; the checker must verify this exactly. The S06 test `test_invoke_llm_abstain_case_insensitive` sends `"abstain\nsome note"` which still passes the prefix check — the test exercises the case-insensitivity aspect but not the false-positive risk.
- **Suggested fix**:
  ```python
  if stdout.strip().upper() == "ABSTAIN":
  ```

**F-02 — `classify_conflicts()` does not return `mixed_refuse_list` for mixed conflicts**

- **File**: `orch/daemon/auto_merge.py`, lines 376-385
- **Description**: The Feature Design boundary table (line 218) specifies: "Some refuse-listed, some allowlisted → `merge_auto_resolution_skipped` with `reason=mixed_refuse_list`; no LLM call; abort (refuse-list wins)." The bash `worktree_commit.sh` (line 464) correctly emits `"reason": "mixed_refuse_list"` when mixed. The Python classifier returns `skipped_reason="refuse_list"` regardless of whether eligible files also exist alongside refused files. This inconsistency degrades the audit trail — operators cannot distinguish a pure refuse-list hit from a mixed-file conflict in event queries.
- **Compounding issue**: The S06 tests `test_mixed_refuse_and_allow` (classifier test) and `test_mixed_refuse_and_allow_refuse_wins` (integration test) both assert `skipped_reason == "refuse_list"`, thereby accepting the incorrect behavior. These tests pass now but test against the implementation rather than the spec.
- **Suggested fix**:
  ```python
  if refuse_files:
      non_refused = [f for f in conflict_files if f not in refuse_files]
      reason = "mixed_refuse_list" if non_refused else "refuse_list"
      return ClassificationResult(..., skipped_reason=reason)
  ```
  Then update the affected unit and integration tests to assert `"mixed_refuse_list"` for mixed inputs.

**F-03 — `reload_config()` and `_cached_config` are dead code not wired to SIGHUP**

- **File**: `orch/daemon/auto_merge.py`, lines 279-290; `orch/daemon/main.py`, lines 677-681
- **Description**: The SIGHUP handler only sets `self.registry._mtime = 0.0` and wakes the poll event (main.py:680-681). It does not call `auto_merge.reload_config()`. The module-level `_cached_config` cache is never populated from the SIGHUP path. AC6 (hot-reload) works only incidentally: `merge_queue.py` calls `AutoMergeConfig.load()` fresh on every conflict event (line 486 of merge_queue.py), so config changes take effect at the next conflict regardless of SIGHUP. The `test_ac6_sighup_reloads_config` integration test tests `reload_config()` directly but does NOT exercise the SIGHUP handler — it gives false confidence.
- **Suggested fix**: Option A (preferred): Add `auto_merge.reload_config(str(_orch_root / "executor" / "auto_merge.toml"))` to the `_handle_reload` method in `main.py` after `self.registry._mtime = 0.0`. Option B: Remove `reload_config()` and `_cached_config` entirely and add a comment in `merge_queue.py` at the load site explaining that fresh-per-event satisfies AC6.

**F-04 — Decision tree checks file-size before hunk-size (wrong order vs spec)**

- **File**: `orch/daemon/auto_merge.py`, lines 404-445
- **Description**: The Feature Design checklist specifies the decision tree as: `refuse-list > binary > oversized hunk > oversized file > too-many-files > not-allowlisted`. The implementation applies file-size (step 3, lines 404-423) before hunk-size (step 4, lines 424-445). The spec says hunk-size should be step 3 and file-size should be step 4. When a file is both larger than `max_file_size_bytes` AND has a hunk exceeding `max_conflict_hunk_lines`, the audit event reports `skipped_reason="file_too_large"` instead of `skipped_reason="hunk_too_large"`. This misleads operators triaging what went wrong. The S06 tests exercise each condition in isolation so the ordering bug is not caught.
- **Suggested fix**: Swap steps 3 and 4 in `classify_conflicts()` so hunk-size check precedes file-size check.

### MEDIUM

**F-05 — Hardcoded PATH in subprocess environment**

- **File**: `orch/daemon/auto_merge.py`, lines 713-716
- **Code**:
  ```python
  env={
      "WORKTREE_PATH": worktree_path,
      "PATH": "/usr/local/bin:/usr/bin:/bin",
  },
  ```
- **Description**: This discards the calling process's `PATH`. Tools `claude`, `opencode`, or `bash` may be installed in `~/.local/bin` (common for uv-managed tools) or virtualenv paths not in the three hardcoded directories. This will produce "command not found" failures on non-standard developer machines. CLAUDE.md prohibits hardcoding configuration values.
- **Suggested fix**:
  ```python
  import os
  env={**os.environ, "WORKTREE_PATH": worktree_path},
  ```

**F-06 — `EVENT_AUTO_RESOLUTION_FAILED` metadata not bounded by `max_event_metadata_bytes`**

- **File**: `orch/daemon/auto_merge.py`, lines 941-960
- **Description**: The success path (`EVENT_AUTO_RESOLVED`) applies a 256 KB cap at lines 984-989, truncating `proposed_content` and setting `truncated=True`. The failure path builds a metadata dict containing `abstained_files`, `error_files`, `proposed_files`, and raw error strings without any size check or truncation. With 5 conflict files each producing multi-KB error messages (e.g., full stderr from a failed LLM subprocess), the failure-path event could exceed the 256 KB Invariant 5 bound. The S06 test `test_invariant5_oversized_metadata_is_truncated` only tests the success path.
- **Suggested fix**: Apply the same `_json.dumps(metadata)` size check in the failure path, truncating error strings if the payload exceeds `config.max_event_metadata_bytes`.

### LOW / SUGGESTION

**F-07 — S06 tests accept wrong behavior for F-01 and F-02**

- **Files**: `tests/unit/test_auto_merge_invoke.py:133`, `tests/unit/test_auto_merge_classifier.py:116`, `tests/integration/test_auto_merge_refuse_list.py:447`
- **Description**: `test_invoke_llm_abstain_case_insensitive` sends `"abstain\nsome note"` which passes both the prefix-check (current) and the exact-check (correct), so it does not detect the bug. `test_mixed_refuse_and_allow` asserts `skipped_reason == "refuse_list"` for mixed inputs — it tests what the implementation does rather than what the spec requires. These tests will need to be updated alongside F-01 and F-02 fixes.

**F-08 — Metadata truncation does not re-verify size after second pass**

- **File**: `orch/daemon/auto_merge.py`, lines 984-989
- **Description**: After truncating `proposed_content` to 200 chars per entry, there is no second `len(json.dumps(metadata).encode())` verification. With 5 files each having large `prompt_hash` (64 chars), `output_hash` (64 chars), and file paths, the residual metadata could theoretically still exceed `max_event_metadata_bytes` after truncation. Risk is low (200 chars × 5 files plus hashes ≈ ~2 KB), but the guard is not provably tight.

**F-09 — `test_auto_merge_prompt.py` patches `subprocess.run` at top level (fragile)**

- **File**: `tests/unit/test_auto_merge_prompt.py`, line 54 (`with patch("subprocess.run", ...)`)
- **Description**: `auto_merge.py` imports `subprocess` directly (`import subprocess`), so the correct patch target for `subprocess.run` calls inside the module is `orch.daemon.auto_merge.subprocess.run`. The top-level `subprocess.run` patch works in practice but would silently stop mocking if `build_resolution_prompt` were ever refactored to `from subprocess import run`. LOW impact since tests currently pass.

**F-10 — `fnmatch` limitation for top-level `docs/*.md` files is noted but not addressed**

- **File**: `executor/auto_merge.toml`, allowlist pattern `"docs/**/*.md"`; `tests/integration/test_auto_merge_refuse_list.py:568-589` (comment)
- **Description**: The S06 report notes that `fnmatch.fnmatchcase("docs/file.md", "docs/**/*.md")` returns `False`. Top-level docs files (`docs/README.md`, etc.) are not covered by the allowlist pattern. This is a documentation gap rather than a bug, but operators should be aware that conflicts in top-level `docs/*.md` files will be classified as `not_allowlisted`. The test `test_allowlisted_docs_pass_classification` was fixed to use a nested path (`docs/architecture/...`) to work around this.

---

## Test Quality Assessment

The S06 test suite is comprehensive for the happy paths and most edge cases. Specific strengths:

- `FakeLLM` boundary replacement is clean and avoids real subprocess spawning
- `test_invariant3_phase1_never_modifies_worktree` uses a real git repo and snapshots state — this is the most rigorous invariant test
- `test_invariant5_oversized_metadata_is_truncated` uses a 1 MB fake LLM response to exercise the truncation path
- `test_merge_queue_auto_merge.py` provides thorough line-level coverage of `_merge_item`'s new branches

Weaknesses:

- Tests for mixed refuse+allow assert the wrong reason string (accepts `"refuse_list"` instead of `"mixed_refuse_list"`) — F-02
- ABSTAIN tests do not cover the false-positive case (output starting with `ABSTAIN_`) — F-01
- Invariant 5 test only covers the success path; failure path is uncovered — F-06
- `test_ac6_sighup_reloads_config` tests the public API of `reload_config()` directly, not the SIGHUP signal path — F-03

---

## Out-of-Scope Verification

- **No new Alembic migration files**: Confirmed — `git diff HEAD --name-only` shows only `executor/step_executor_lib.sh`, `executor/worktree_commit.sh` (S01 work), `orch/daemon/merge_queue.py`. No migration files.
- **`executor/worktree_commit.sh`**: Modified in working tree but by S01, not S03. S03 did not touch this file.
- **No API or frontend changes**: Confirmed.

---

## Findings Table

| ID | Severity | File | Location | Description | Recommendation |
|----|----------|------|----------|-------------|----------------|
| F-01 | HIGH | `orch/daemon/auto_merge.py` | Line 776 | ABSTAIN detection uses `startswith("ABSTAIN")` — prefix match creates false-positive risk for files beginning with `ABSTAIN_*` | Change to `stdout.strip().upper() == "ABSTAIN"` |
| F-02 | HIGH | `orch/daemon/auto_merge.py` | Lines 376-385 | Mixed refuse+allow conflict returns `"refuse_list"` instead of `"mixed_refuse_list"` as required by spec; S06 tests accept the wrong value | Distinguish mixed case; update affected tests |
| F-03 | HIGH | `orch/daemon/auto_merge.py`, `orch/daemon/main.py` | Lines 279-290, 677-681 | `reload_config()` and `_cached_config` are dead code — SIGHUP handler does not call `reload_config()`; AC6 test covers only the dead function, not the signal path | Wire `reload_config()` into SIGHUP handler, or remove dead code |
| F-04 | HIGH | `orch/daemon/auto_merge.py` | Lines 404-445 | File-size check (step 3) runs before hunk-size check (step 4), opposite of spec; wrong `skipped_reason` emitted when both limits exceeded | Swap steps 3 and 4 |
| F-05 | MEDIUM | `orch/daemon/auto_merge.py` | Lines 713-716 | Hardcoded `PATH=/usr/local/bin:/usr/bin:/bin` in subprocess env discards calling process's PATH; breaks installs where `claude`/`opencode` are in `~/.local/bin` | Use `{**os.environ, "WORKTREE_PATH": worktree_path}` |
| F-06 | MEDIUM | `orch/daemon/auto_merge.py` | Lines 941-960 | `EVENT_AUTO_RESOLUTION_FAILED` metadata not capped at `max_event_metadata_bytes`; success path has truncation, failure path does not | Apply same size check + truncation in failure path |
| F-07 | LOW | `tests/unit/test_auto_merge_invoke.py`, `tests/unit/test_auto_merge_classifier.py`, `tests/integration/test_auto_merge_refuse_list.py` | Lines 133, 116, 447 | S06 tests for ABSTAIN (case-insensitive test does not catch false positives) and mixed-refuse (asserts wrong reason string) need updating alongside F-01/F-02 fixes | Update tests after fixing F-01 and F-02 |
| F-08 | LOW | `orch/daemon/auto_merge.py` | Lines 984-989 | Metadata truncation does not re-verify total size after second pass; guard not provably tight | Add second `json.dumps` size check after truncation |
| F-09 | LOW | `tests/unit/test_auto_merge_prompt.py` | Line 54 | `subprocess.run` patched at top-level namespace rather than `orch.daemon.auto_merge.subprocess.run`; fragile if module refactored | Change patch target |
| F-10 | LOW | `executor/auto_merge.toml`, `tests/integration/test_auto_merge_refuse_list.py` | Allowlist patterns | Top-level `docs/*.md` files not matched by `docs/**/*.md` via Python fnmatch; noted in S06 report but not resolved | Add `"docs/*.md"` to allowlist, or document the limitation |

---

## Overall Verdict: NEEDS_FIX

**Mandatory fixes before merge** (HIGH severity): F-01, F-02, F-03, F-04

**Should fix before production** (MEDIUM severity): F-05, F-06

The core safety invariants (Phase 0 no-LLM, Phase 1 no-worktree-mutation, operator UX unchanged) are all correctly implemented. The architecture is solid. The four HIGH issues are all correctness/spec-compliance bugs that affect audit trail fidelity (F-02, F-04), the safety guarantee against false ABSTAIN detection (F-01), and AC6 test coverage validity (F-03).

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "F-00084",
  "verdict": "NEEDS_FIX",
  "mandatory_fix_count": 4,
  "finding_summary": "F-01: ABSTAIN detection uses startswith instead of exact match (line 776); F-02: classify_conflicts does not return mixed_refuse_list for mixed conflicts, and S06 tests accept the incorrect behavior; F-03: reload_config() and _cached_config are dead code not wired to SIGHUP handler; F-04: decision tree has file-size before hunk-size, swapped vs spec; F-05: hardcoded PATH in subprocess env (MEDIUM); F-06: EVENT_AUTO_RESOLUTION_FAILED metadata not capped at max_event_metadata_bytes (MEDIUM). All CRITICAL safety invariants (phase-0 no-LLM, phase-1 no-mutation, operator UX unchanged) are correctly implemented.",
  "notes": "All 69 unit tests pass; 119 S06 integration tests pass. Core architecture is correct. HIGH findings F-01/F-02/F-03/F-04 must be fixed — the first two also require companion test updates in S06-generated test files."
}
```
