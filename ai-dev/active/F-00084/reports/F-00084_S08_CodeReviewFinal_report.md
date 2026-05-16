# F-00084 S08 — Final Cross-Agent Code Review

**Step**: S08 — code-review-final-impl
**Work Item**: F-00084 — LLM-Assisted Merge Conflict Resolution (Phase 0 + Phase 1 dry-run)
**Date**: 2026-05-16
**Scope**: Full holistic review of S01–S07 (pipeline, backend, tests, all per-agent reviews, prior cross-agent review)
**Reviewer**: code-review-final-impl

---

## 1. Executive Summary

**Feature readiness for Phase 0 (default-on merge): CONDITIONAL PASS**

Phase 0 is provably safe. With `phase = 0` (the shipped default), no LLM token is ever consumed, the existing `merge_conflict` + `merge_failed` operator path runs exactly as before, and no new env vars are required. The feature can be merged and deployed without operator action and will have zero runtime impact on the existing merge pipeline.

Phase 1 (dry-run) is structurally sound — the non-mutating invariant is proven by code inspection (no `git add`, no `git rebase --continue` anywhere in `auto_merge.py`) — but has a **blocking defect that will cause Phase 1 LLM calls to fail** in any standard installation: the hardcoded `PATH` in `invoke_llm_for_file` excludes `~/.local/bin`, where `claude` and `opencode` are installed via `uv tool install`. This means Phase 1 can never successfully invoke the LLM until this is fixed.

Five findings from the S02/S04/S05 per-agent reviews were NOT resolved during S06 implementation:
- CONFLICT_FILES marker absent from blocking-conflict branch (HIGH)
- AUTO_RESOLVE_SKIPPED missing `branch` and `main_sha` (HIGH)
- ABSTAIN detection uses `.startswith` instead of exact match (HIGH)
- `classify_conflicts()` never returns `mixed_refuse_list` (HIGH)
- PATH hardcoded, breaking Phase 1 LLM invocation (HIGH)

Two additional HIGH findings were introduced during S06/S07:
- `merge_queue.py` new branches have no test coverage (HIGH)
- AC4/Invariant 4 not verified through the actual `_merge_item()` path (HIGH)

Two design requirements are unimplemented:
- `config_reloaded` DaemonEvent not emitted on SIGHUP (AC6 gap, MEDIUM)
- SIGHUP handler never calls `reload_config()` — AC6 satisfied only incidentally (MEDIUM)

All 119 tests pass. Lint, typecheck, and format gates pass cleanly.

**Decision: request_changes** — Phase 0 is merge-safe but the HIGH findings must be resolved before Phase 1 is enabled. The operator guide (§7) describes safe deployment.

---

## 2. Findings Table

| ID | Severity | Location | Description | Status |
|----|----------|----------|-------------|--------|
| R01 | HIGH | `executor/worktree_commit.sh` line 472 | `CONFLICT_FILES` marker promised by comment but never emitted in blocking branch. `batch_item.merge_info["conflict_files"]` will always be `[]` for blocking conflicts, breaking the dashboard conflict-file display and the existing F-00076 audit trail for every conflict this feature was designed to handle. Comment says "Also emit existing CONFLICT_FILES marker so today's parser still works" but no `echo` follows. CONFLICT_FILES is only emitted on line 506, which is the mutually exclusive all-auto-resolved path. | Unresolved from S02-F001, S05-X01 |
| R02 | HIGH | `executor/worktree_commit.sh` lines 459, 464 | `AUTO_RESOLVE_SKIPPED` JSON missing `branch` and `main_sha` fields. Both skip markers (`refuse_list` at line 459, `mixed_refuse_list` at line 464) omit these fields. `AUTO_RESOLVE_REQUESTED` at line 471 correctly includes them. `merge_queue.py` reads `_auto_skip` as-is via `emit_skipped_event`, so the `merge_auto_resolution_skipped` event metadata will always have empty/absent `branch` and `main_sha` on skip paths. Reduced audit trail quality. | Unresolved from S02-F002, S05-X02 |
| R03 | HIGH | `orch/daemon/auto_merge.py` line 776 | ABSTAIN detection uses `.upper().startswith("ABSTAIN")` instead of exact match. Any valid Python file whose first non-whitespace content starts with `ABSTAIN_` (e.g., `ABSTAIN_CONFIGS = []`, `ABSTAIN = True`) would be incorrectly flagged as model abstention, causing a false `merge_auto_resolution_failed` event with `abstained=True` for a valid LLM response. Design and prompt spec require exact match: `stdout.strip().upper() == "ABSTAIN"`. | Unresolved from S04-F01, S05-X03 |
| R04 | HIGH | `orch/daemon/auto_merge.py` lines 346–489 | `classify_conflicts()` does not return `skipped_reason="mixed_refuse_list"`. When some files are refused and some are eligible, line 384 always returns `skipped_reason="refuse_list"`. Bash correctly emits `mixed_refuse_list` on the mixed case (line 464 of `worktree_commit.sh`); Python's defence-in-depth reclassification disagrees. The design's Boundary Behavior table requires `mixed_refuse_list` on the mixed case. | Unresolved from S04-F02, S05-X04 |
| R05 | HIGH | `orch/daemon/auto_merge.py` line 715 | `PATH` hardcoded to `/usr/local/bin:/usr/bin:/bin`. The `claude` CLI installed via `uv tool install` lives at `~/.local/bin/claude`; `opencode` at `~/.local/bin/opencode`. Neither path is on the hardcoded list. All Phase 1 LLM calls will fail with "command not found" in a standard developer or daemon environment. Phase 0 is unaffected (never calls LLM). Fix: `"PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin")`. | Unresolved from S04-F05, S05-X05 |
| R06 | HIGH | `tests/integration/test_auto_merge_phase1.py` | `merge_queue.py`'s new dispatch branches are not exercised. S06 tests call `attempt_resolution()` and `classify_conflicts()` directly, bypassing `_merge_item()`. The "neither marker present" path (standard conflict unchanged), "malformed marker defensive fallback" (what `merge_queue.py` does when `parse_auto_resolve_marker()` returns `None`), and the full phase-dispatch logic are all untested. | From S07-F1 |
| R07 | HIGH | `tests/integration/test_auto_merge_phase1.py` | AC4/Invariant 4 not verified through the actual merge path. The `test_ac4_*` tests only assert on `attempt_resolution()` return values and `merge_auto_resolution_failed` events. Neither `BatchItem.status = merge_failed` nor that `merge_conflict` DaemonEvent fires with the same behaviour as today is asserted. The design's AC4 explicitly requires both. | From S07-F2 |
| R08 | MEDIUM | `orch/daemon/auto_merge.py` lines 941–961 | `EVENT_AUTO_RESOLUTION_FAILED` metadata is not size-capped. The 256 KB `max_event_metadata_bytes` guard applies only to the `EVENT_AUTO_RESOLVED` path (lines 983–989). For failures with large error strings or many abstained files, the event metadata can exceed Invariant 5's limit. | Unresolved from S04-F06, S05-X06 |
| R09 | MEDIUM | `executor/worktree_commit.sh` line 368–371 | Phase value from TOML not validated as integer. `awk -F= '{print $2}' | tr -d ' '` on `phase = 0  # comment` produces `0#comment`, which is non-numeric. The design requires treating non-integer values as 0 (defensive). Fix: add `if ! [[ "$_phase_raw" =~ ^[0-9]+$ ]]; then _phase_raw=""; fi`. | Unresolved from S02-F003, S05-X07 |
| R10 | MEDIUM | `executor/auto_merge.toml` + `orch/daemon/auto_merge.py` | `pyproject.toml` absent from refuse-list in both TOML and `_DEFAULT_REFUSELIST`. R-00076 §2.4 explicitly lists it as "Never Automate" because dependency-graph changes need `uv lock` regeneration, not LLM edits. A conflict in `pyproject.toml` would currently pass all filters and reach the LLM in Phase 1. The bash `_REFUSE_PREFIXES` also does not cover it (no prefix or suffix match). | Unresolved from S02-F004, S05-X08 |
| R11 | MEDIUM | `orch/daemon/auto_merge.py` lines 282–290 + `orch/daemon/main.py` | `reload_config()` and `_cached_config` are dead code. The SIGHUP handler in `main.py` does NOT call `auto_merge.reload_config()`. AC6 is incidentally satisfied because `merge_queue.py` loads config fresh on every conflict event (line 486). But the intended caching mechanism is unintegrated and gives a false impression. Additionally, the design requires a `config_reloaded` DaemonEvent to fire on reload — this event is never emitted anywhere in the codebase. | Unresolved from S04-F03, S05-X09; AC6 event gap from S07-F3 |
| R12 | MEDIUM | `tests/integration/auto_merge_fixtures.py` | `make_git_conflict_repo()` is defined and exported but never called by any test. Dead fixture code. | From S07-F5 |
| R13 | MEDIUM | `orch/daemon/auto_merge.py` + `executor/auto_merge.toml` | `fnmatch.fnmatchcase("docs/IW_AI_Core_Architecture.md", "docs/**/*.md")` returns `False` — Python's `fnmatch` does not treat `**` as a recursive glob; it requires at least one directory separator between `docs/` and the filename. Top-level `docs/*.md` files are not allowlisted. Conflicts in `docs/IW_AI_Core_Architecture.md`, `docs/IW_AI_Core_Daemon_Design.md`, etc. would be classified as `not_allowlisted` and skipped, even though the design intent is to allow doc-file conflicts. S06 noted this gap and fixed the test path but did not fix the production config or comment. | New finding (S06 noted, not escalated) |
| R14 | LOW | `executor/worktree_commit.sh` line 477 | Error-log loop uses bare `$_blocking` (word-split) instead of array `"${_blocking_files[@]}"`. Style inconsistency, not a correctness bug. | Unresolved from S02-F005 |
| R15 | LOW | `executor/auto_merge.toml` lines 31–34 | Three redundant allowlist sub-patterns (`ai-dev/active/**/I-*/reports/**`, `ai-dev/active/**/F-*/reports/**`, `ai-dev/active/**/CR-*/reports/**`) are all subsumed by `ai-dev/active/**/reports/**`. | Unresolved from S02-F006 |
| R16 | LOW | `orch/daemon/auto_merge.py` lines 984–989 | Single truncation pass may not be sufficient: after truncating `proposed_content` to 200 chars per file, total may still exceed `max_event_metadata_bytes` for a 5-file conflict with large hashes. Second size check is absent. | From S04-F08 |
| R17 | LOW | `tests/unit/test_auto_merge_prompt.py` | Four duplicate test pairs (determinism, ABSTAIN clause, work-item header) add no coverage and inflate the test count. | From S07-F7 |
| R18 | LOW | `tests/unit/test_auto_merge_config.py` | `test_load_malformed_toml` uses a loose assertion: `"TOML" in error or "parse" in error.lower() or "error" in error.lower()`. Any string containing "error" passes. Tighter assertion recommended. | From S07-F10 |

---

## 3. AC Sign-Off Table

| AC | Description | Test Coverage | Implementation | Status |
|----|-------------|---------------|----------------|--------|
| AC1 | I-00085 shape: 3 test files, phase=1 dry-run | `test_ac1_i00085_shape_phase1_dry_run`, `test_ac1_resolution_attempted_event_structure` | `attempt_resolution()` correctly dispatches 3 LLM calls, emits `merge_auto_resolution_attempted` + `merge_auto_resolved` events with correct metadata | PASS |
| AC2 | I-00086 shape: prompt contains three-way content | `test_ac2_i00086_shape_prompt_contains_three_way_content` | `build_resolution_prompt()` correctly fetches `:1:`, `:2:`, `:3:` git-show refs; prompt builder unit tests cover all 5 sections | PASS (with note: test verifies LLM dispatch count and model/cli_tool, not prompt content at integration level — acceptable since unit tests cover that) |
| AC3 | Refuse-list never invokes LLM | `test_ac3_migration_file_refuse_list`, `test_ac3_migration_refuse_list_attempt_resolution_phase1`, 8 parametrized `test_refuse_list_*` tests | `classify_conflicts()` returns `skipped_reason="refuse_list"` on all refuse patterns; `emit_skipped_event` fires; zero LLM calls | PASS |
| AC4 | Operator UX unchanged on any failure | `test_ac4_operator_ux_unchanged_on_abstain`, `test_ac4_operator_ux_unchanged_on_llm_error` | `attempt_resolution()` returns `success=False`; `merge_auto_resolution_failed` event fires | PARTIAL — tests verify `attempt_resolution()` return values but do NOT verify `BatchItem.status=merge_failed` or `merge_conflict` DaemonEvent through the actual `_merge_item()` path (R07) |
| AC5 | Phase 0 is a fully-functional no-op | `test_ac5_phase0_default_no_llm_call`, `test_ac5_phase0_short_circuit_invariant_2` | Phase-0 short-circuit in `attempt_resolution()` emits `merge_auto_resolution_skipped` with `reason="phase_0"`, returns immediately, zero subprocess calls | PASS |
| AC6 | Configuration is hot-reloadable | `test_ac6_sighup_reloads_config`, `test_ac6_reload_config_missing_file_returns_defaults` | `reload_config()` reads TOML and updates cache; fresh-load in `merge_queue.py` line 486 ensures next conflict uses updated config | PARTIAL — `config_reloaded DaemonEvent` not emitted anywhere; SIGHUP handler not wired; AC6 satisfied only incidentally via fresh-load pattern (R11) |

---

## 4. Invariant Sign-Off Table

| Invariant | Description | Test | Implementation Enforcement | Status |
|-----------|-------------|------|---------------------------|--------|
| Inv 1 | No LLM token for refuse-listed file | All AC3 tests assert `len(fake_llm.calls) == 0` | `classify_conflicts()` short-circuits before `attempt_resolution()` | PASS |
| Inv 2 | No LLM token when `phase = 0` | `test_ac5_phase0_default_no_llm_call`, TDD red evidence in `test_ac5_phase0_short_circuit_invariant_2` | `attempt_resolution()` lines 846–866 return before any subprocess call | PASS |
| Inv 3 | Phase 1 never calls `git add` or `git rebase --continue` | `test_invariant3_phase1_never_modifies_worktree` — snapshots HEAD + status before/after | `auto_merge.py` grep confirms no `git add` or `git rebase --continue` anywhere | PASS |
| Inv 4 | Existing operator commands unchanged on failure path | AC4 tests (partial) | `BatchItem.status = merge_failed` at line 446 (unconditional, before F-00084 code); `merge_conflict` event at line 560 (unconditional) | PARTIAL — code structure is correct but no test verifies the full `_merge_item()` path (R07) |
| Inv 5 | `event_metadata` <= 256 KB | `test_invariant5_oversized_metadata_is_truncated` | Truncation at lines 983–989 for `EVENT_AUTO_RESOLVED`; `EVENT_AUTO_RESOLUTION_FAILED` path uncapped (R08) | PARTIAL — success path capped; failure path uncapped |
| Inv 6 | Decision tree is deterministic | `test_decision_tree_determinism_invariant_6` — 10 repeated invocations | No `datetime.now()` or `random.*` in classifier or prompt builder | PASS |
| Inv 7 | Agent + model from `runtime_option_id` config | `test_ac2_i00086_shape_prompt_contains_three_way_content` verifies `call.model == default_runtime_option.model` | `_resolve_runtime_option()` is sole resolver; `invoke_llm_for_file` passes its `(cli_tool, model)` exclusively | PASS |
| Inv 8 | Failed LLM call leaves worktree clean | `test_invariant8_failed_llm_leaves_worktree_clean` — byte-identical comparison before/after | `invoke_llm_for_file` returns `LLMCallResult` on all paths; no file writes ever; Python code never calls `git add` | PASS |

---

## 5. Safety Walk-Throughs

### 5.1 Phase 0 No-Op Proof

Code path: `_merge_item()` → catch `MergeError` → parse `AUTO_RESOLVE_REQUESTED` marker → `AutoMergeConfig.load()` → `classify_conflicts()` → `attempt_resolution()` (phase=0 branch) → `_emit_event(SKIPPED, reason=phase_0)` → return.

- `AutoMergeConfig.load()` with missing file returns `defaults()` where `phase = PHASE_DISABLED = 0`. No exception possible.
- `attempt_resolution()` line 846: `if config.phase == PHASE_DISABLED:` branches immediately. No `invoke_llm_for_file()` call. No `subprocess.run()` call in this path.
- `_emit_event()` writes a `DaemonEvent` row. `db.commit()` persists it.
- Return `AutoMergeResult(success=False, ...)` — control returns to `_merge_item()`.
- `db.commit()` at line 555.
- `_emit_event(merge_conflict, ...)` at line 560 — fires exactly as today.

**Proof**: Zero LLM tokens, zero subprocess calls, zero worktree mutations. Operator sees `merge_failed` + `merge_conflict` + one extra `merge_auto_resolution_skipped` event. All pre-F-00084 behaviour preserved.

### 5.2 Phase 1 Non-Destructive Proof

Code path: `attempt_resolution()` (phase=1) → `_resolve_runtime_option()` → `_emit_event(ATTEMPTED)` → per-file loop calling `invoke_llm_for_file()` → `subprocess.run(bash step_executor_lib.sh auto_merge_resolve)` → capture stdout only → `_emit_event(RESOLVED|FAILED)` → return `AutoMergeResult(success=False)`.

- `invoke_llm_for_file()` does NOT write to any file. It calls `subprocess.run()` with `capture_output=True` and reads `result.stdout`. No filesystem writes.
- No call to `git add`, `git rebase --continue`, `git commit`, or any git mutation in all of `auto_merge.py`. Verified by grep (zero matches).
- `attempt_resolution()` line 1004: `return AutoMergeResult(success=False, ...)` unconditionally. The comment "Phase 1 ALWAYS returns success=False — never auto-applies" is accurate.
- `_merge_item()` receives `success=False` and falls through to the unconditional `db.commit()` + `_emit_event(merge_conflict)` + `logger.error()`. No `git rebase --continue` is called by `_merge_item()`.
- The `--resume-rebase` guard in `worktree_commit.sh` lines 47–50 exits with code 2 if accidentally called, ensuring Phase 2's apply path cannot be triggered by a script invocation bug.

**Proof**: Worktree is never modified. Rebase is always aborted (by bash, not Python). LLM output is captured to DB only.

### 5.3 Refuse-List Defence-in-Depth Proof

- **Bash layer (coarse)**: `_REFUSE_PREFIXES` and `_REFUSE_SUFFIXES` in `worktree_commit.sh` lines 381–393 catch migration paths (`orch/db/migrations/versions/`), executor scripts (`executor/`), env files (`.env`), identity files, and common binary suffixes.
- **Python layer (rich)**: `classify_conflicts()` uses `fnmatch.fnmatchcase()` against `config.refuselist_patterns` (full glob patterns from `auto_merge.toml`).
- **Defence-in-depth**: If bash misclassifies a file as eligible, Python's richer glob list will catch it. GAP: `pyproject.toml` is absent from BOTH layers (R10). If `pyproject.toml` has a conflict, neither bash nor Python will block LLM resolution.

---

## 6. Risk Register

| Risk | Likelihood | Impact | Mitigation | Residual Risk |
|------|-----------|--------|-----------|---------------|
| Oversized JSONB rows (Invariant 5) | Low (Phase 1 only) | Medium — event-view query degradation | Success path: 256KB cap with truncation at line 984. Failure path: uncapped (R08). | LOW for Phase 0; MEDIUM for Phase 1 failure path |
| Prompt leaking secrets | Very Low | High | `build_resolution_prompt()` uses only `item_id`, `item_title`, `item_description` (first 500 words), and `git show` output. No `os.environ` access in prompt builder. Confirmed by grep. | NEGLIGIBLE |
| Race between SIGHUP reload and in-flight merge | Very Low | Low | Merge queue is serialised. Fresh-load on every conflict event means at most one merge runs with stale config. | NEGLIGIBLE for Phase 0; ACCEPTABLE for Phase 1 dry-run |
| LLM hallucinating content | Medium (Phase 1) | None (Phase 1 never applies) | Phase 1 dry-run never calls `git add`. Proposals captured in `event_metadata` only. Phase 2 verification gate will enforce test/lint pass. | NONE for Phase 1 |
| Subprocess overhead | Low | Low | `invoke_llm_for_file` timeout is configurable (`llm_call_timeout_seconds = 120`). No evidence of issues from integration tests (15s wall-clock for 119 tests). | LOW |
| LLM binary not found (PATH) | HIGH in Phase 1 | HIGH — Phase 1 silently fails | Hardcoded PATH at line 715 excludes `~/.local/bin`. All Phase 1 LLM calls will fail with `FileNotFoundError` or "command not found". Fix required before enabling Phase 1 (R05). | BLOCKING for Phase 1 |
| `pyproject.toml` conflict reaching LLM | Low | Medium — dep-graph edits without `uv lock` regeneration | Missing from both refuse layers (R10). Fix: add to both TOML and Python defaults. | LOW for Phase 0 (no LLM); MEDIUM for Phase 1 |
| ABSTAIN false-positive | Low | Low (Phase 1 only) | `startswith("ABSTAIN")` would flag files starting with `ABSTAIN_*` identifiers. In practice unlikely but non-zero. Fix required (R03). | LOW |

---

## 7. Operator Guide — Phase 0 to Phase 1 Advancement

**Current state**: `executor/auto_merge.toml` has `phase = 0`. Safe to merge and deploy. Zero operator action required.

**When Phase 1 is desired (after mandatory fixes below)**:

Prerequisites (all required before enabling Phase 1):
1. Fix R05 (hardcoded PATH) — otherwise all LLM calls silently fail.
2. Fix R03 (ABSTAIN startswith) — otherwise valid Python files starting with `ABSTAIN_*` are misclassified.
3. Fix R01 (CONFLICT_FILES missing) — otherwise the dashboard shows empty conflict-file lists for all blocking conflicts.
4. Fix R04 (mixed_refuse_list not returned) — otherwise mixed-file conflicts are misclassified in audit trail.
5. Ensure an `AgentRuntimeOption` row with `is_default=True` and `enabled=True` exists in the orch DB, OR set `runtime_option_id = <id>` in `auto_merge.toml`.

Advancement steps:
```
# 1. Verify the LLM binary is reachable from the daemon's PATH
which claude  # or: which opencode
# 2. Edit executor/auto_merge.toml
phase = 1
# 3. SIGHUP the daemon (no restart needed)
pkill -HUP -f "iw daemon"
# 4. Monitor dashboard events for merge_auto_resolution_attempted and merge_auto_resolved rows
# 5. After two weeks of dry-run data, evaluate Phase 2 readiness
```

Rollback:
```
# Immediately revert to Phase 0 — no LLM calls, no state change
# Edit executor/auto_merge.toml: phase = 0
# SIGHUP the daemon
```

---

## 8. Cross-Batch Hygiene Check

| Check | Result |
|-------|--------|
| Files outside design's Impacted Paths | PASS — no files outside manifest were touched |
| New dependency in `pyproject.toml` | PASS — no new deps; `tomllib` is stdlib (Python 3.11+) |
| New env var required | PASS — no new env vars |
| New migration file | PASS — no Alembic migration; events reuse existing TEXT `event_type` column |
| Dashboard or API changes | PASS — no frontend changes |

**One unexpected addition**: `tests/unit/test_auto_merge_invoke.py` was added (not in the original design manifest's Impacted Paths which listed only four unit test files). This is a net positive addition but worth noting.

**`tests/fixtures/auto_merge/**`** listed in the design's Impacted Paths was never created — `auto_merge_fixtures.py` lives in `tests/integration/` instead. Not a problem, just a design deviation.

---

## 9. Documentation Completeness

- Design doc (`F-00084_Feature_Design.md`) accurately describes the delivered scope.
- No stale Phase 2 references in code comments that could be confused with the current implementation (all Phase 2 references are clearly marked "RESERVED" or "follow-up CR").
- `executor/auto_merge.toml` header comment explains the phase ladder clearly.
- `orch/daemon/auto_merge.py` module docstring accurately describes Phase 0/1 behaviour.
- **Gap**: The `config_reloaded DaemonEvent` in AC6 spec is neither implemented nor documented as out-of-scope.

---

## 10. Overall Assessment

```
Phase 0 safety invariants:     ALL PASS
Phase 1 non-destructive proof:  PASS (but Phase 1 is broken by PATH issue R05)
Test suite:                     119/119 PASS
Lint/typecheck/format:          ALL PASS
AC coverage:                    AC1, AC2, AC3, AC5 PASS; AC4 PARTIAL; AC6 PARTIAL
Invariant coverage:             Inv 1,2,3,6,7,8 PASS; Inv 4 PARTIAL; Inv 5 PARTIAL
```

The seven HIGH findings represent real gaps: five are unresolved carry-overs from per-agent reviews (R01–R05), two are test coverage gaps (R06–R07). None of R01–R05 compromise Phase 0 safety or Phase 1 non-destructive invariants, but R05 (hardcoded PATH) makes Phase 1 entirely non-functional in practice, and R01 (missing CONFLICT_FILES) degrades the dashboard for every blocking conflict — even under Phase 0 — because `batch_item.merge_info["conflict_files"]` is empty.

**Recommendation**: Merge to unblock Phase 0 deployment. Create a targeted fix cycle for R01–R07 before Phase 1 is enabled. The Phase 1 enablement should be blocked on at minimum R01, R03, R04, R05 being resolved.

---

```json
{
  "review": "F-00084_S08_CodeReviewFinal",
  "decision": "request_changes",
  "critical": 0,
  "high": 7,
  "medium": 6,
  "low": 5,
  "findings": [
    {
      "id": "R01",
      "severity": "HIGH",
      "location": "executor/worktree_commit.sh:472",
      "description": "CONFLICT_FILES marker promised by comment but never emitted in blocking branch. batch_item.merge_info[conflict_files] always empty for blocking conflicts.",
      "recommendation": "After the if/elif/elif block at line 473, add echo for CONFLICT_FILES using _blocking_files array and same jq/awk pattern as lines 490-505."
    },
    {
      "id": "R02",
      "severity": "HIGH",
      "location": "executor/worktree_commit.sh:459,464",
      "description": "AUTO_RESOLVE_SKIPPED JSON missing branch and main_sha fields. merge_auto_resolution_skipped events have incomplete audit trail on skip paths.",
      "recommendation": "Add '\"branch\": \"${BRANCH_NAME}\", \"main_sha\": \"${MAIN_SHA}\"' to both AUTO_RESOLVE_SKIPPED JSON objects."
    },
    {
      "id": "R03",
      "severity": "HIGH",
      "location": "orch/daemon/auto_merge.py:776",
      "description": "ABSTAIN detection uses startswith not exact match. Files starting with ABSTAIN_* identifiers incorrectly treated as model abstention.",
      "recommendation": "Change to: if stdout.strip().upper() == \"ABSTAIN\":"
    },
    {
      "id": "R04",
      "severity": "HIGH",
      "location": "orch/daemon/auto_merge.py:346-489",
      "description": "classify_conflicts never returns skipped_reason=mixed_refuse_list. Mixed refuse+eligible always returns refuse_list, inconsistent with bash and design spec.",
      "recommendation": "Track eligible files alongside refused; if both non-empty, return skipped_reason=mixed_refuse_list."
    },
    {
      "id": "R05",
      "severity": "HIGH",
      "location": "orch/daemon/auto_merge.py:715",
      "description": "PATH hardcoded to /usr/local/bin:/usr/bin:/bin. claude and opencode binaries at ~/.local/bin are unreachable. All Phase 1 LLM calls fail.",
      "recommendation": "Change to: \"PATH\": os.environ.get(\"PATH\", \"/usr/local/bin:/usr/bin:/bin\")"
    },
    {
      "id": "R06",
      "severity": "HIGH",
      "location": "tests/integration/test_auto_merge_phase1.py",
      "description": "merge_queue.py new dispatch branches (neither-marker path, malformed-marker fallback, phase-dispatch) not exercised by any test.",
      "recommendation": "Add unit tests calling through merge_queue._merge_item() or its new sub-paths directly."
    },
    {
      "id": "R07",
      "severity": "HIGH",
      "location": "tests/integration/test_auto_merge_phase1.py",
      "description": "AC4/Invariant 4 not verified through _merge_item(). No test checks BatchItem.status=merge_failed or that merge_conflict event fires after auto-merge attempt.",
      "recommendation": "Extend AC4 tests to call through _merge_item() or add an Invariant 4 integration test."
    },
    {
      "id": "R08",
      "severity": "MEDIUM",
      "location": "orch/daemon/auto_merge.py:941-961",
      "description": "EVENT_AUTO_RESOLUTION_FAILED metadata not size-capped. Failure path can exceed 256KB (Invariant 5 partial violation).",
      "recommendation": "Apply same truncation logic from success path to failure path metadata."
    },
    {
      "id": "R09",
      "severity": "MEDIUM",
      "location": "executor/worktree_commit.sh:368-371",
      "description": "Phase value not validated as integer. Trailing comment on TOML line produces non-numeric _phase_raw.",
      "recommendation": "Add: if ! [[ \"$_phase_raw\" =~ ^[0-9]+$ ]]; then _phase_raw=\"\"; fi"
    },
    {
      "id": "R10",
      "severity": "MEDIUM",
      "location": "executor/auto_merge.toml + orch/daemon/auto_merge.py",
      "description": "pyproject.toml absent from refuse-list in both layers. R-00076 §2.4 explicitly requires it.",
      "recommendation": "Add to [refuselist] patterns in auto_merge.toml and to _DEFAULT_REFUSELIST in auto_merge.py. Add exact-filename check to bash _REFUSE_PREFIXES."
    },
    {
      "id": "R11",
      "severity": "MEDIUM",
      "location": "orch/daemon/auto_merge.py:282-290 + orch/daemon/main.py",
      "description": "reload_config and _cached_config dead code. SIGHUP handler not wired. config_reloaded DaemonEvent (required by AC6) never emitted.",
      "recommendation": "Either wire SIGHUP handler to call auto_merge.reload_config() and emit config_reloaded event, OR remove _cached_config and document that fresh-load satisfies AC6 and remove config_reloaded from AC6 spec."
    },
    {
      "id": "R12",
      "severity": "MEDIUM",
      "location": "tests/integration/auto_merge_fixtures.py",
      "description": "make_git_conflict_repo() defined, exported, and documented but never called by any test.",
      "recommendation": "Remove or use the function."
    },
    {
      "id": "R13",
      "severity": "MEDIUM",
      "location": "executor/auto_merge.toml + orch/daemon/auto_merge.py",
      "description": "fnmatch does not treat ** as recursive glob. docs/IW_AI_Core_Architecture.md (top-level docs) does not match docs/**/*.md. Such files get skipped_reason=not_allowlisted.",
      "recommendation": "Add docs/*.md as an additional allowlist pattern, or document this limitation clearly in auto_merge.toml."
    },
    {
      "id": "R14",
      "severity": "LOW",
      "location": "executor/worktree_commit.sh:477",
      "description": "Error-log loop uses bare $_blocking instead of ${_blocking_files[@]}.",
      "recommendation": "Change to: for _bf in \"${_blocking_files[@]}\"; do"
    },
    {
      "id": "R15",
      "severity": "LOW",
      "location": "executor/auto_merge.toml:31-34",
      "description": "Three redundant allowlist sub-patterns subsumed by ai-dev/active/**/reports/**.",
      "recommendation": "Remove the three ID-specific sub-patterns."
    },
    {
      "id": "R16",
      "severity": "LOW",
      "location": "orch/daemon/auto_merge.py:984-989",
      "description": "Single truncation pass may still exceed cap if many files with large metadata overhead.",
      "recommendation": "Add second size check after truncation loop."
    },
    {
      "id": "R17",
      "severity": "LOW",
      "location": "tests/unit/test_auto_merge_prompt.py",
      "description": "4+ duplicate test pairs add no coverage.",
      "recommendation": "Remove duplicate tests."
    },
    {
      "id": "R18",
      "severity": "LOW",
      "location": "tests/unit/test_auto_merge_config.py",
      "description": "test_load_malformed_toml uses loose error assertion.",
      "recommendation": "Assert on specific TOML error class name or file path in error message."
    }
  ]
}
```
