# CR-00065 Self-Assessment Report

**Item**: CR-00065 — Live Agent Session Log Viewer
**Analyzer**: self-assess-impl (via `iw-item-analyze` skill)
**Date**: 2026-05-20
**DB signal**: yes (DB:UP, step status confirmed via `iw item-status --json`)

---

## Item Analysis: CR-00065

**Bottom line**: The integration test gate (S10) consumed 4 retries (~67 min wall-clock) because tests encode hardcoded migration-revision constants that must be updated whenever a new migration is added — this is a systemic fragility that affects every CR with a DB migration.

Steps analyzed: 12 | Steps with retries: 5 (S02, S03, S04, S05, S10) | Total fix-cycles: 1 (S10→fix1) | DB signal: yes

---

### Item Summary

CR-00065 delivered a new feature — the Live Agent Session Log Viewer — across 12 workflow steps. All implementation steps (S01–S05) were correct per the code review (0 CRITICAL, 0 HIGH, 0 MEDIUM_FIXABLE). The browser verification (S11) passed all 6 checks.

The item ran cleanly from a code-quality standpoint. No agent thrash, no repeated tool failures, no convention violations, no environment gaps. The single significant inefficiency was the integration-test gate.

---

### Findings

**[1] Integration tests encode hardcoded migration-revision constants — fragile across every DB-migration CR**
Severity: HIGH | Class: environment | Frequency: systemic
Evidence:
- `tests/integration/daemon/test_phase2_apply_no_self_deadlock.py:134` — `_HEAD_REVISION = "e45b45f74ea0"` hardcoded; CR-00065's migration `00490acc4cdf` replaced it; 2 tests failed
- `tests/dashboard/test_item_steps_table_render.py:373` — `assert header_count == 11` hardcoded; CR-00065's Logs column bumped to 12; 1 test failed
- `tests/integration/test_dashboard_remaining.py:420` — text assertion not scoped to the correct DOM region; unrelated UI text ("Clear chat" button) caused failure
- S10 ran 5 times (run1 fail, run2 fail, run3 fail, run4 pass, run5 pass) = ~67 min wall-clock on this gate alone

Recommendation: Adopt one or both strategies:
- **Strategy A** (preferred): Add a pytest fixture `current_head_revision` that reads the actual Alembic head revision at runtime. Tests that assert against pending migrations should use `alembic history --limit 1 --style=plain` to discover the head dynamically, not a hardcoded constant.
- **Strategy B**: Add a `make update-test-constants` command that auto-discovers and updates hardcoded revision constants before the integration test run. The S10 prompt should invoke this automatically.

Target: `tests/integration/daemon/test_phase2_apply_no_self_deadlock.py` (Strategy A: replace `_HEAD_REVISION` with a runtime fixture; Strategy B: add auto-update hook in S10 prompt)
Target: `tests/dashboard/test_item_steps_table_render.py` (Strategy A: make assertion count parametric via a fixture; Strategy B: `make update-test-constants` updates 11→12)

Pros: Every future CR with a DB migration or a new UI column will pass S10 on first try. Saves ~50 min of agent + wall-clock time per affected CR.
Cons: Strategy A requires changing the test fixture architecture; Strategy B is a one-line prompt change but is a workaround, not a fix.
If we don't: Every CR that adds a migration or UI column continues to fail S10 and require a fix-cycle. At current CR frequency, this will happen roughly monthly.
Effort: M (~3 files, plus prompt template update) for Strategy A; S (~1 prompt file) for Strategy B

---

**[2] S11 Browser Verification spent ~45 min in environment setup (down/up cycles) before running**
Severity: MED | Class: environment | Frequency: one-off
Evidence:
- `ai-dev/logs/CR-00065_S11_browser_env_down.log` — E2E stack torn down for unrelated reason
- `ai-dev/logs/CR-00065_S11_browser_env_up.log` — E2E stack rebuilt (Docker build + container startup)
- `ai-dev/logs/CR-00065_S11_fix1.log` — one fix cycle to correct the htmx polling wrapper pattern
- Combined: ~45 min of which only ~3 min was actual browser verification work

Recommendation: Add a "pre-flight" check in the `qv-browser` prompt that detects whether a healthy E2E stack already exists before invoking the rebuild sequence. If `docker ps --filter "name=iw-ai-core-e2e-" --format "{{.Status}}"` returns "healthy" for all required services, skip the rebuild. If any service is down, do an incremental `docker compose up` rather than a full teardown + rebuild.

Target: `ai-dev/active/CR-00065/CR-00065/prompts/CR-00065_S11_BrowserVerification_prompt.md` (add pre-flight E2E health check before stack setup)

Pros: ~30–45 min saved per browser-verification step when the stack is already up.
Cons: Pre-flight check adds ~5s overhead; slight increase in prompt complexity.
If we don't: Browser verification steps waste most of their time on Docker setup even when the stack is already running.
Effort: S (~20 lines in prompt, no code change)

---

**[3] QV gate (S02) ran 3 times when 1 run should have sufficed**
Severity: MED | Class: platform | Frequency: one-off
Evidence:
- `ai-dev/logs/CR-00065_S02_run2.log` — first pass (3 tests, all pass)
- `ai-dev/logs/CR-00065_S02_run3.log` — second pass (3 tests, all pass), ~6 hours after run2
- `ai-dev/logs/CR-00065_S01_run2.log` — S01 ran once with "key findings" about WorkItemType enum coercion

The step was correct on run2. Run3 was a separate invocation (possibly daemon re-poll or manual re-trigger). The S01 finding about `WorkItemType` enum is notable: the agent discovered SQLAlchemy's test engine doesn't auto-coerce enum strings, which is a known project issue. No explicit retry was needed — the agent corrected itself within the same run.

Recommendation: Check whether `make migration-check` is idempotent across repeated invocations. If the gate is re-triggered automatically (daemon poll), investigate why S02 was picked up again ~6 hours later when nothing in the worktree changed.

Target: `orch/daemon/qv_gate_validator.py` — add logging of why a QV gate is being re-launched; if the worktree hasn't changed since the last pass, skip the re-run.

Pros: Eliminates unnecessary QV gate re-runs, saves ~10s per spurious re-run and reduces DB load.
Cons: Requires daemon-side logic change.
If we don't: QV gates re-run spuriously, wasting DB slots and agent time on trivial changes.
Effort: M (~10 lines, daemon change)

---

### Coverage Notes

- All logs < 1 MB — read in full. S10 logs were the largest (~385 KB each) and read via targeted tail + grep to find failures.
- DB:UP — step status confirmed via `iw item-status CR-00065 --json`.
- Coverage: S01–S09 full log reads; S10 log1 tail+grep; S10 log4/log5 tail reads; S11 all logs full read.

---

### Lower-priority observations (omitted from top 3)

- S04 ran with an empty log file (run2 = 0 bytes), suggesting daemon killed/restarted mid-step or log capture failed. Log loss doesn't affect correctness but makes post-mortem harder.
- S03 ran 3 times (run1/run2 not available; run3 is the survivor) — non-deterministic opencode output rather than explicit failure.
- The `make update-test-constants` approach (Strategy B for finding [1]) would also catch the S04/S05 multi-run issue by ensuring assertions are dynamic rather than hardcoded.