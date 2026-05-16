# F-00084 S05 — Final Cross-Agent Code Review

**Step**: S05
**Agent**: code-review-final-impl
**Date**: 2026-05-16
**Work Item**: F-00084 — LLM-Assisted Merge Conflict Resolution (Phase 0 + Phase 1 dry-run)
**Scope**: Cross-layer correctness review of S01 (bash/TOML) + S03 (Python backend), informed by S02 and S04 per-agent reviews.

---

## 1. Review Process

All implementation files were read directly:
- `executor/auto_merge.toml`
- `executor/worktree_commit.sh` (F-00084 additions)
- `orch/daemon/auto_merge.py`
- `orch/daemon/merge_queue.py` (F-00084 additions)
- `executor/step_executor_lib.sh` (F-00084 additions)
- All four unit test files in `tests/unit/test_auto_merge_*.py`

Per-agent review findings from S02 and S04 were read and cross-checked. All 27 unit tests were run and confirmed passing. The research doc R-00076 §5 was cross-referenced.

---

## 2. Findings Table

| ID | Severity | Location | Description | Recommendation |
|----|----------|----------|-------------|----------------|
| X01 | HIGH | `executor/worktree_commit.sh` lines 457–473 | **CONFLICT_FILES marker absent from blocking-conflict branch — unresolved from S02-F001.** The `CONFLICT_FILES` marker is emitted only on line 506 (the all-auto-resolved path). In the blocking path (lines 355–484), a comment on line 472 promises its emission but no `echo` statement exists. The `_CONFLICT_MARKER_RE` in `merge_queue.py` (line 55) matches `^\[worktree_commit\] CONFLICT_FILES (\[.*\])$`. Because this regex is only searched on the blocking path's output (lines 452–457), and the blocking path never emits the marker, `conflict_files` stays `[]` for every blocking conflict. Consequence: `batch_item.merge_info["conflict_files"]` is always empty on blocking conflicts, breaking AC4 invariant ("merge_conflict DaemonEvent fires with the conflict file list") and making the dashboard event view uninformative for every real-world conflict this feature was designed to help with. | After the if/elif/elif block (after line 473), before `git rebase --abort` (line 483), add: build `_conflict_json` from `_blocking_files` using the same jq/awk pattern on lines 490–505, then emit `echo "[worktree_commit] CONFLICT_FILES ${_conflict_json}"`. |
| X02 | HIGH | `executor/worktree_commit.sh` lines 459, 464 | **AUTO_RESOLVE_SKIPPED JSON omits `branch` and `main_sha` — unresolved from S02-F002.** Both skip-marker emits (`refuse_list` at line 459, `mixed_refuse_list` at line 464) omit `branch` and `main_sha` fields. `AUTO_RESOLVE_REQUESTED` at line 471 correctly includes them. `merge_queue.py` reads `_auto_resolve_request.get("branch", "")` and `_auto_resolve_request.get("main_sha", "")` (lines 523–524), but these fields are only present on the `AUTO_RESOLVE_REQUESTED` marker, not on `AUTO_RESOLVE_SKIPPED`. For skip events, the emitted DaemonEvent metadata will always contain empty `branch` and `main_sha` strings, reducing audit trail quality. Both variables (`BRANCH_NAME`, `MAIN_SHA`) are in scope at the emit points. | Add `"branch": "${BRANCH_NAME}", "main_sha": "${MAIN_SHA}"` to both `AUTO_RESOLVE_SKIPPED` JSON objects at lines 459 and 464. |
| X03 | HIGH | `orch/daemon/auto_merge.py` line 776 | **ABSTAIN detection uses `.startswith` instead of exact match — unresolved from S04-F01.** The check is `stdout.upper().startswith("ABSTAIN")`. A resolved Python file that opens with `ABSTAIN_CONFIGS = [...]` or `ABSTAIN = True` would be incorrectly treated as a model abstention, causing the dry-run event to record `abstained=True` and `proposed_content=None` for a valid resolution. Design and prompt both specify exact match. | Change line 776 to: `if stdout.strip().upper() == "ABSTAIN":` |
| X04 | HIGH | `orch/daemon/auto_merge.py` lines 346–489 | **`classify_conflicts()` does not return `mixed_refuse_list` — unresolved from S04-F02.** When some files are refuse-listed and some are eligible, the function returns `skipped_reason="refuse_list"` regardless. The design's Boundary Behavior table explicitly requires `reason=mixed_refuse_list` for the mixed case; this is a named scenario in the feature's acceptance test plan and will cause S06 integration tests to fail. The distinction also matters for audit: operators seeing `refuse_list` cannot tell whether there were also eligible files that were blocked by the defence-in-depth policy. | After the refuse-list check (lines 366–385), track whether any files passed (would be eligible if refuse-list not applied). If `len(refuse_files) > 0` and `len(conflict_files) - len(refuse_files) > 0`, return `skipped_reason="mixed_refuse_list"`. |
| X05 | HIGH | `orch/daemon/auto_merge.py` line 715 | **PATH hardcoded to `/usr/local/bin:/usr/bin:/bin` — unresolved from S04-F05.** The subprocess env for LLM calls explicitly replaces the calling process's PATH with a minimal fixed list. The `claude` CLI binary installed via `uv tool install` lives at `~/.local/bin/claude`, and `opencode` typically lives at `~/.local/bin/opencode`. Neither path is on the hardcoded list. This makes Phase 1 LLM calls fail with "command not found" on any non-root installation, which is the normal operator setup. | Change the `env` dict to inherit the caller's PATH: `"PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin")`. |
| X06 | MEDIUM | `orch/daemon/auto_merge.py` lines 940–961 | **`EVENT_AUTO_RESOLUTION_FAILED` metadata is not size-capped — unresolved from S04-F06.** The 256 KB `max_event_metadata_bytes` guard applies only to the success path (`EVENT_AUTO_RESOLVED`). The failure path at lines 940–961 includes `abstained_files`, `error_files`, `proposed_files`, and token counts but has no size cap. For an 8-file conflict where each file produces a long error string, this can exceed Invariant 5's limit. | Apply the same size-cap logic (truncate per-file error strings and set `metadata["truncated"] = True`) to the failure path's metadata before calling `_emit_event`. |
| X07 | MEDIUM | `executor/worktree_commit.sh` line 368 | **Phase value not validated as integer — unresolved from S02-F003.** A TOML line like `phase = 0  # default` passes through `awk -F= '{print $2}' | tr -d ' '` to produce `0#default`. The Python side later receives this in the `AUTO_MERGE_PHASE` marker and any string comparison will fail silently. The design requires treating non-integer values as 0. | Add: `if ! [[ "$_phase_raw" =~ ^[0-9]+$ ]]; then _phase_raw=""; fi` after line 370, before the non-empty check. |
| X08 | MEDIUM | `executor/auto_merge.toml` / `orch/daemon/auto_merge.py` | **`pyproject.toml` absent from refuse-list — unresolved from S02-F004.** R-00076 §2.4 explicitly lists `pyproject.toml` as "Never Automate" because dep-graph changes require `uv lock` regeneration. Neither `executor/auto_merge.toml` nor `_DEFAULT_REFUSELIST` in `auto_merge.py` includes this entry. The bash prefix-list in `worktree_commit.sh` also does not cover it. A conflict in `pyproject.toml` would pass all filters and reach the LLM in Phase 1. | Add `"pyproject.toml"` to `[refuselist] patterns` in `executor/auto_merge.toml` and to `_DEFAULT_REFUSELIST` in `auto_merge.py`. Add an exact-filename match guard in the bash `_REFUSE_PREFIXES` or a dedicated `_REFUSE_EXACT` check. |
| X09 | MEDIUM | `orch/daemon/auto_merge.py` lines 282–290 + `orch/daemon/main.py` | **`reload_config()` and `_cached_config` are dead code unintegrated with SIGHUP — unresolved from S04-F03.** `reload_config()` is defined but never called. The SIGHUP handler in `main.py` (`_handle_reload` at line 677) only resets `self.registry._mtime`. AC6 (hot reload) is incidentally met because `merge_queue.py` loads config fresh on every conflict event (line 486), but the `_cached_config` module variable gives a false impression of a caching mechanism that is never populated. Future callers who use `_cached_config` directly will get `None`. | Either (a) call `auto_merge.reload_config(toml_path)` from `main.py`'s `_handle_reload` to make the cache coherent, or (b) remove `_cached_config` and `reload_config()` entirely and add a comment in `merge_queue.py` line 486 documenting that fresh-load is intentional for AC6. |
| X10 | MEDIUM | `tests/unit/test_auto_merge_*.py` | **No unit test for `attempt_resolution()` phase-0 short-circuit — unresolved from S04-F07.** The design requires a test asserting `subprocess.run` call_count == 0 when `phase == PHASE_DISABLED`. Without it, a regression that accidentally calls the LLM in phase 0 would not be caught by the unit suite. The design's "TDD Approach" section explicitly lists `test_attempt_resolution_phase_0_no_llm`. | Add a unit test in `tests/unit/test_auto_merge_classifier.py` or a new `test_auto_merge_attempt.py` that patches `subprocess.run` and asserts it is never called when `attempt_resolution()` is invoked with `phase=0`. Requires a mock DB session. |
| X11 | LOW | `executor/worktree_commit.sh` line 477 | **Error-log loop uses bare `$_blocking` instead of `${_blocking_files[@]}` — unresolved from S02-F005.** Minor style inconsistency; not a correctness bug for files without spaces. | Change `for _bf in $_blocking; do` to `for _bf in "${_blocking_files[@]}"; do`. |
| X12 | LOW | `executor/auto_merge.toml` lines 31–34 | **Redundant allowlist sub-patterns — unresolved from S02-F006.** Patterns `ai-dev/active/**/I-*/reports/**`, `ai-dev/active/**/F-*/reports/**`, `ai-dev/active/**/CR-*/reports/**` are all subsumed by `ai-dev/active/**/reports/**`. Not a correctness issue. | Remove the three redundant sub-patterns. |
| X13 | LOW | `orch/daemon/auto_merge.py` lines 984–989 | **Single truncation pass may still exceed cap — from S04-F08.** After truncating each `proposed_content` to 200 chars, the total may still exceed `max_event_metadata_bytes` if there are 5 files with large hashes and metadata overhead. A second size check is missing. | After the truncation loop, re-serialize and check again. If still over the cap, truncate further or drop `per_file` entries from the end. |
| X14 | LOW | `orch/daemon/auto_merge.py` | **`_BINARY_SUFFIXES` in Python is richer than `_REFUSE_SUFFIXES` in bash and than the `[refuselist]` in TOML.** The Python set includes `.ico`, `.bmp`, `.svg`, `.pdf`, `.gz`, `.tar`, `.zip`, `.pyc`, `.so`, `.dll`, `.exe`, `.whl` which are not in the TOML refuselist or bash list. This is a conservative choice (Python catches more) rather than a defence-in-depth gap, but the discrepancy means the TOML is not the single source of truth for binary suffixes. | Document in a comment that Python's binary detection has additional suffix coverage beyond the TOML refuselist, and that this is intentional defence-in-depth. No code change required. |

---

## 3. Integration Health Summary

**Marker round-trip**: The `AUTO_RESOLVE_REQUESTED` marker (bash → Python) is correctly formed and consumed end-to-end for the happy-path (all-eligible) case. The `AUTO_RESOLVE_SKIPPED` marker is parseable but is missing `branch`/`main_sha` fields (X02). **CRITICAL GAP**: the pre-existing `CONFLICT_FILES` marker — which `merge_queue.py` relies on to populate `merge_info["conflict_files"]` and the `merge_conflict` DaemonEvent — is never emitted in the blocking-conflict branch. Every blocking conflict (the common case) will land in the DB with `conflict_files: []`, breaking AC4 and the dashboard event view.

**Phase 0 short-circuit**: The phase-0 path in `attempt_resolution()` correctly short-circuits before any subprocess call, emits `EVENT_AUTO_RESOLUTION_SKIPPED` with `reason="phase_0"`, and returns `success=False`. `BatchItem.status = merge_failed` and `merge_conflict` DaemonEvent both fire unconditionally. Core Phase-0 safety invariants (Invariants 1, 2, 3) are intact. No LLM tokens are consumed.

**Refuse-list defence-in-depth**: The two-layer guard (bash coarse-prefix + Python rich-glob) is structurally sound. Python's `classify_conflicts()` catches patterns the bash list misses. However, `pyproject.toml` is absent from both layers (X08), and the bash and Python layers disagree on the `mixed_refuse_list` reason string (bash emits `mixed_refuse_list` correctly; Python always returns `refuse_list` for any refuse hit, making them inconsistent on the mixed case — X04). The absence of `CONFLICT_FILES` in the blocking path (X01) is orthogonal to security but does affect audit completeness.

**Operator UX preservation**: `BatchItem.status = merge_failed` is set unconditionally before the new auto-merge code runs. The `merge_conflict` DaemonEvent fires unconditionally at line 560. `iw merge-queue retry-merge <ID>` continues to work. The existing operator workflow is not broken. The only degradation is that `conflict_files` in the event payload will always be `[]` on blocking conflicts due to X01.

---

## 4. Cross-Layer Consistency Assessment

### JSON schema match
- `AUTO_RESOLVE_REQUESTED`: bash emits `{"eligible_files": [...], "branch": "...", "main_sha": "..."}`. Python expects `_auto_resolve_request.get("eligible_files", [])`, `.get("branch", "")`, `.get("main_sha", "")`. MATCH.
- `AUTO_RESOLVE_SKIPPED`: bash emits `{"reason": "...", "refuse_files": [...], "eligible_files": [...]}` (missing `branch`/`main_sha`). Python calls `emit_skipped_event(db, project_id, item_id, _auto_skip)` which forwards the dict verbatim. PARTIAL MATCH (missing fields — X02).

### Configuration surface
`auto_merge.toml` is loaded fresh at every conflict event (line 486 of `merge_queue.py`), making it the de-facto single configuration surface. SIGHUP's effect on hot-reload is incidental (config is always fresh-loaded). The `_cached_config` mechanism is dead code (X09). Reserved phases (2, 3) are correctly refused by `attempt_resolution()` at line 843.

### Event ordering
Confirmed correct: `merge_auto_resolution_attempted` → per-file LLM → `merge_auto_resolved | merge_auto_resolution_failed | merge_auto_resolution_skipped` → `merge_conflict`. All wrapped in `try/except` so exceptions cannot suppress the `merge_conflict` event.

### Awk fallback JSON validity
The awk fallback for `_build_json_array` (bash lines 437–451) correctly escapes backslashes and double-quotes and produces valid JSON. Empty arrays produce `[]`. A file with a backslash in its path would produce valid JSON. A file with a newline in its path would fail (but such paths would already fail git rebase itself), so this is acceptable.

---

## 5. Security Assessment

- No prompt sent to LLM includes secrets: `build_resolution_prompt()` uses only `item_id`, `item_title`, `item_description` (first 500 words), and `git show` output. No `os.environ` access inside the prompt builder. PASS.
- Phase 1 never calls `git add` or `git rebase --continue`. Confirmed by grep — no such calls anywhere in `auto_merge.py`. PASS.
- Refuse-list bars migration files, security configs, env files, identity files, and executor scripts. Structurally sound. Gap: `pyproject.toml` missing (X08).

---

## 6. Testability Handoff to S06

S06 will need:
- A `tmp_path` bare-repo fixture with three conflict states (all-eligible, all-refused, mixed).
- A mock `db` session (for unit tests of `attempt_resolution` phase-0 assertion).
- The `CONFLICT_FILES` marker emission bug (X01) means that integration tests for AC4 which assert on `conflict_files` in the `merge_conflict` event will fail until X01 is fixed.
- The `mixed_refuse_list` reason string (X04) means S06 tests asserting `reason == "mixed_refuse_list"` on `merge_auto_resolution_skipped` will pass for bash-emitted skips (which correctly emit `mixed_refuse_list`) but fail for Python-reclassified skips (which emit `refuse_list`). This will only manifest if the Python classifier catches a file the bash list missed — exactly the defence-in-depth case.
- The hardcoded PATH (X05) means Phase 1 integration tests that actually invoke `step_executor_lib.sh` will fail in standard developer environments unless X05 is fixed.

---

```json
{
  "decision": "request_changes",
  "critical_count": 0,
  "high_count": 5,
  "medium_count": 4,
  "low_count": 5,
  "summary": "Five HIGH findings remain unresolved from per-agent reviews (S02, S04): CONFLICT_FILES marker never emitted in blocking-conflict branch (X01 breaks AC4 conflict_files payload); AUTO_RESOLVE_SKIPPED missing branch/main_sha fields (X02); ABSTAIN detection uses startswith instead of exact match (X03); classify_conflicts never returns mixed_refuse_list (X04 breaks boundary test); PATH hardcoded and will break Phase 1 LLM calls in non-root environments (X05). Four MEDIUM issues: EVENT_AUTO_RESOLUTION_FAILED metadata uncapped (X06), phase value not validated as integer (X07), pyproject.toml absent from refuse-list (X08), reload_config dead code (X09). All safety invariants for Phase 0/1 (no LLM in phase 0, no worktree mutation in phase 1, operator UX preserved) are correctly implemented."
}
```
