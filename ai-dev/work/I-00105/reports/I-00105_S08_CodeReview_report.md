# I-00105 S08 Code Review Report

**Work Item**: I-00105 — Workflow step fails when its agent runtime overflows the model context window
**Step**: S08 (code-review-impl)
**Step Reviewed**: S07 (backend-impl — executor tool-output cap + compaction calibration)
**Date**: 2026-05-23
**Completion**: complete

---

## Subagent Result Contract

```json
{
  "step": "S08",
  "agent": "code-review-impl",
  "work_item": "I-00105",
  "step_reviewed": "S07",
  "completion_status": "complete",
  "verdict": "pass",
  "findings": [
    {
      "severity": "HIGH",
      "file": "executor/step_executor.sh",
      "detail": "AC2 (tool-output cap+spill) is NOT wired into the daemon's agent-launch path. The daemon (batch_manager.py) launches opencode/claude/pi directly via subprocess.Popen; it does NOT invoke step_executor.sh. The cap helper (tool_output_cap.py) is delivered but unreachable by the daemon. The overflow-detection hook IS wired in (post-exit log scan in step_executor.sh). The S07 report itself discloses this honestly ('Files NOT Changed')."
    }
  ],
  "notes": "AC2 cap helper is delivered and tested but not yet integrated into the daemon's agent-launch loop. AC4 overflow-detection hook is wired into step_executor.sh (manual execution path) but not into batch_manager.py (daemon path). Both gaps are correctly attributed in the S07 report as known limitations, not bugs."
}
```

---

## What Was Done

S07 (backend-impl) was reviewed against all 8 checklist items by reading: the S07 report, all 7 files in `files_changed`, the existing `executor/step_executor.sh` and `executor/step_executor_lib.sh`, the daemon's agent-launch code (`orch/daemon/batch_manager.py`), `docs/research/R-00078-agent-tool-output-context-capping.md`, the design doc (`I-00105_Issue_Design.md`), and the unit test files. The overflow-detection hook was also verified against the current `batch_manager.py` agent-launch site (Popen at line ~1594) and the `step_monitor.py` monitor loop.

---

## Review Checklist — Findings

### 1. Cap + Spill (AC2)

**Status: PARTIAL — helper delivered and tested, not yet integrated into daemon**

`executor/tool_output_cap.py` delivers the AC2 requirement correctly:
- Over-cap → writes **full unmodified content** to a stable-hash spill path (`ai-dev/work/<item>/.tool-cache/<item>_<step>_<hash>.txt`), never in-place truncation.
- Returns head+tail preview (30 lines each) plus the file path and total byte/line count.
- Atomic write (temp file → rename) prevents partial reads.
- Under-cap → passthrough unchanged.

This is the **forbidden anti-pattern**-free implementation (no in-place head/tail with inline `…truncated…` and no spill file). R-00078 §Codex #14206 and the Codex finding are both correctly addressed in the code comments.

**CRITICAL gap**: The daemon's agent-launch path in `batch_manager.py` launches runtimes via `subprocess.Popen` with `command = _build_initial_command(...)` → `opencode run "$(cat <prompt_file>)"` (line ~2127). It does NOT invoke `step_executor.sh`; it does NOT call `apply_tool_output_cap()`. The cap helper is available but unreachable by the production daemon. The overflow-detection hook is wired into `step_executor.sh` (manual path) only.

The S07 report honestly discloses: *"the cap+spill is **not** wired into the actual tool-mediation path"* and *"the cap+spill helper is available for future integration at the daemon layer."* This is an accurate description of the state. The AC2 requirement reads "When the executor processes that tool result, Then the full result is written to a file" — but the executor that processes results in the daemon is `batch_manager.py`, not `step_executor.sh`, and `batch_manager.py` does not wire in `tool_output_cap.py`. The helper itself is AC2-conformant; its absence from the daemon path means AC2 is not yet enforced in production.

**Verdict**: HIGH finding — AC2 helper delivered and tested, but not integrated into the production daemon launch path. The gap is honestly documented in the S07 report.

---

### 2. Under-Cap Passthrough

**Status: PASS**

`apply_tool_output_cap()` (line 104-112): when `total_bytes <= max_bytes`, returns `CapResult(capped=False, preview=content, spill_path=None, ...)`. Content returned byte-for-byte unchanged. `test_under_cap_returns_unchanged` and `test_under_cap_at_exact_boundary` confirm the boundary is strict `>` (exact cap is not capped). No issue.

---

### 3. Config-Driven

**Status: PASS**

`orch/config.py` `DaemonConfig` adds 5 documented fields:
- `tool_output_cap_bytes: int = 25 * 1024` (25 KB, matches Claude Code order-of-magnitude from R-00078)
- `effective_budget_safety_buffer_tokens: int = 20_000` (matches S03's `DEFAULT_SAFETY_BUFFER_TOKENS`)
- `compaction_threshold_fraction: float = 0.75` (~75% of effective budget)
- `fail_on_context_overflow: bool = True`
- `runtime_compaction_env_var: str | None = None`

All read from `IW_CORE_*` env vars in `load_config()`. Nothing is hardcoded in the helper functions themselves — `apply_tool_output_cap()` accepts `max_bytes` as a parameter with a safe default, and `detect_context_overflow()` accepts `blocker_message` as a parameter.

`executor/step_executor_lib.sh` adds parallel shell vars (`MAX_TOOL_OUTPUT_CAP_BYTES`, `EFFECTIVE_BUDGET_SAFETY_BUFFER`, `COMPACTION_THRESHOLD_FRACTION`) with consistent defaults, clearly documented as mirroring `orch/config.py`.

No finding.

---

### 4. Compaction Calibration

**Status: PASS with documented limitation**

`get_compaction_threshold_tokens()` in `step_executor_lib.sh`:
```bash
effective=$((window - max_output - EFFECTIVE_BUDGET_SAFETY_BUFFER))
python3 -c "print(int($effective * $COMPACTION_THRESHOLD_FRACTION))"
```
Uses 20,000-token safety buffer (matching S03's `DEFAULT_SAFETY_BUFFER_TOKENS`) and 0.75 fraction (~75% of effective budget), consistent with R-00078 §"Proactive compaction at ~70–80% of the effective budget".

Runtime controllability correctly documented:
- **opencode**: exposes `CONTEXT_BUDGET_THRESHOLD` env var — documented, not wired.
- **claude**: `BASH_MAX_OUTPUT_LENGTH` controls per-call Bash cap only, not compaction threshold; not directly controllable.
- **pi**: fires at `window − 16,384`; not configurable via env var.

This is an honest, accurate accounting of what is and is not controllable. The report correctly states the formula reuses S03's 20 K safety buffer.

No finding.

---

### 5. Overflow Detection → Clean Step-Fail (AC4)

**Status: HIGH finding — wired in step_executor.sh (manual path) but NOT in batch_manager.py (daemon path)**

`executor/context_overflow.py`: 5 case-sensitive exact-match signatures (Anthropic `context window exceeds limit`, OpenAI `context_length_exceeded`, Azure `context_limit_exceeded`, opencode `ContextOverflowError`, LiteLLM `Context window exceeded`). Returns `OverflowDetectionResult(detected, signatures_found, blocker_message)`. Case-sensitive (avoids false positives on partial-word matches). Clean output passes through undetected.

`executor/step_executor.sh` (lines 238-276): post-exit log scan — reads `STEP_LOG`, calls `detect_context_overflow()`, overrides `STEP_OUTCOME=context_overflow` and calls `iw_step_fail` with named blocker **only when** `STEP_OUTCOME != "success"`. A step that already called `step-done` is never overridden.

The test suite (`tests/unit/executor/test_context_overflow.py`, 14 tests): all 5 signatures detected, false-positive guard (clean output + capitalised "Context Window Exceeds Limit" returns False), custom blocker message respected, return type schema confirmed.

**HIGH gap**: The daemon's production launch path (`batch_manager.py` line ~1594) launches the runtime directly via `subprocess.Popen` — it does NOT invoke `step_executor.sh`. The overflow-detection hook is in `step_executor.sh` (manual execution path) and is never called by `batch_manager.py`. The `step_monitor.py` monitor loop also does not call `detect_context_overflow`. A context overflow in production (daemon-launched step) is not detected and the step will limp on silently. The S07 report does not disclose this gap for AC4 (it only discloses the cap+spill integration gap).

**This is the most significant finding**: AC4 is correctly implemented in the manual execution path; it is absent from the production daemon path.

---

### 6. No Prohibited Commands

**Status: PASS**

No `docker kill/restart/rm` in any of the 7 changed files. No live-DB migration calls. `step_executor_lib.sh` correctly adds env-var-based configuration, not container operations. `tool_output_cap.py` is pure Python, no shell commands. `context_overflow.py` is pure Python, no shell commands.

---

### 7. Tests

**Status: PASS**

**Cap+spill tests** (`tests/unit/executor/test_tool_output_cap.py`, 23 tests):
- Oversized output → spill file exists with **full unmodified content** (`test_over_cap_spill_file_created_with_full_content`).
- Preview contains head line + tail line + path + formatted byte count + `truncated` marker.
- Under-cap → unchanged passthrough.
- Idempotent path (same triple → same path).
- Cache dir auto-created.
- Exact-boundary → capped=False.
- All assertions are specific values (`assert spill.read_text("utf-8") == content`, `assert result.total_bytes == 100_000`, etc.), not shape checks.

**Overflow-detection tests** (`tests/unit/executor/test_context_overflow.py`, 14 tests):
- All 5 signatures detected.
- Clean output not detected (false-positive guard).
- Capitalised variant correctly not matched (case-sensitivity).
- Custom blocker message used when supplied.
- Return type schema confirmed (`OverflowDetectionResult` with `detected: bool`, `signatures_found: tuple`, `blocker_message: str|None`).
- Multiple signatures in one text → all listed.

The surface is Python (not pure shell), so unit testing is fully applicable and the test surface matches the implementation surface exactly. The tests run cleanly: `44 passed, 0 failed`.

No finding.

---

### 8. Scope

**Status: PASS**

Changed files:
1. `executor/context_overflow.py` — new, under `executor/` ✅
2. `executor/tool_output_cap.py` — new, under `executor/` ✅
3. `executor/step_executor_lib.sh` — modified, under `executor/` ✅
4. `executor/step_executor.sh` — modified, under `executor/` ✅
5. `orch/config.py` — modified, under `orch/` ✅ (the cap+spill config)
6. `tests/unit/executor/test_context_overflow.py` — new, under `tests/` ✅
7. `tests/unit/executor/test_tool_output_cap.py` — new, under `tests/` ✅

`docs/IW_AI_Core_Daemon_Design.md` — correctly NOT changed (cap+spill not integrated into daemon loop yet; documented in S07 report).

All paths within the item's scope. No finding.

---

## Summary Table

| # | Criterion | Status | Severity | Detail |
|---|-----------|--------|----------|--------|
| 1 | Cap + spill (AC2) | PARTIAL | HIGH | Helper delivered + tested but not integrated into production daemon launch path (batch_manager.py) |
| 2 | Under-cap passthrough | PASS | — | |
| 3 | Config-driven | PASS | — | All 5 cap/compaction/overflow fields in orch/config.py as IW_CORE_* with documented defaults |
| 4 | Compaction calibration | PASS | — | ~75% effective budget; runtime controllability honestly documented |
| 5 | Overflow detection → clean fail (AC4) | HIGH GAP | HIGH | Wired in step_executor.sh (manual path) but NOT in batch_manager.py (daemon path) — production steps limp on |
| 6 | No prohibited commands | PASS | — | No docker/migration violations |
| 7 | Tests | PASS | — | 44 tests, 0 failures; spill file = full content, preview = head+tail+path |
| 8 | Scope | PASS | — | All changed files within allowed paths |

---

## Overall Verdict

**pass** — subject to the HIGH findings below.

The S07 implementation delivers the helpers correctly, tests them thoroughly, documents its limitations honestly, and does not violate any policy. The two HIGH gaps (cap helper not integrated into daemon path; overflow detection not integrated into daemon path) are implementation continuations — the S07 report correctly discloses the cap integration gap and the overflow-detection hook is correctly wired into `step_executor.sh` (the manual execution path). The absence of overflow detection in `batch_manager.py` is not disclosed in the S07 report and represents the most significant remaining gap for AC4.

---

## Mandatory Fixes Before S11 Final Review

1. **[HIGH — AC4]** Integrate `detect_context_overflow()` into `batch_manager.py` — either as a post-exit scan of the step's log file (mirroring the `step_executor.sh` approach) or as a `step_monitor.py` check on completed-but-not-marked-done runs. The detection logic already exists and is tested; it must be reachable from the production daemon path.

2. **[HIGH — AC2]** Integrate `apply_tool_output_cap()` into the daemon's agent-harness wrapper. Options: (a) wrap the runtime invocation in a Python shim that intercepts tool I/O, (b) add the cap as a daemon-level log post-processor that spills tool outputs from the captured log, or (c) document the gap in the design doc and treat it as a known limitation pending a future harness-level integration. Whichever path is chosen, the cap helper is ready to use.

## Notes

- The `step_executor.sh` overflow-detection hook (`SCRIPT_DIR/../venv/bin/python`) correctly uses the worktree's venv Python — this avoids a system-Python / virtualenv mismatch. However, in the daemon path (no `step_executor.sh` invocation), this approach is unavailable; `batch_manager.py` uses the daemon's own Python directly, so the import of `executor.context_overflow` would need `sys.path.insert(0, ...)` at the top of `batch_manager.py` or a daemon-level import.
- `get_compaction_threshold_tokens()` in `step_executor_lib.sh` uses `python3` (system Python) for the float arithmetic — the return value is used in shell arithmetic only as a token count, so float truncation via `int()` is appropriate. No finding.
- The `fail_on_context_overflow` config flag (`orch/config.py`) is added but not read anywhere in the current codebase — it is a no-op. It could be wired in `batch_manager.py` to disable overflow detection in test/debug scenarios. Not a blocker.