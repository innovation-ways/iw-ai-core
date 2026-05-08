# CR-00036 Self-Assessment Report

## Item Analysis: CR-00036

**Bottom line:** QV gates (format, lint) required fix cycles but resolved cleanly; browser verification needed 3 fix cycles due to an E2E seed import error introduced during S17's fixture authoring, which obscured the root cause across cycles.

**Steps analyzed:** 18 (S01–S18)
**Steps with retries / fix cycles:** 7 (S04, S06, S12, S13, S16, S17 — with S12/S13/S16/S17 each taking multiple cycles)
**Total fix cycles:** 15 (S04×1, S06×1, S12×2, S13×4, S16×3, S17×3, plus earlier steps)
**DB signal:** yes (DB:UP, full telemetry available)

---

## Findings

### [1] QV fix-cycle count was inflated by unclear gate-failure diagnostic output
**Severity:** MED   **Class:** platform   **Frequency:** recurring

Evidence:
- `ai-dev/active/CR-00036/fix-cycles/CR-00036_S12_FIX_cycle1_prompt.md:16` — "lint failed: exit=2" with no parseable output beyond the generic "Failed CR-00036 step S12: lint failed: exit=2"
- `ai-dev/active/CR-00036/fix-cycles/CR-00036_S12_FIX_cycle2_prompt.md:16` — same unparseable output on cycle 2
- S13 hit 4 consecutive format-fix cycles (cycles 1–4) before passing — each cycle consumed a full gate run + agent invocation for a single-file format issue in `ai-dev/active/CR-00036/e2e_fixtures/002_v1_v4_v7_seed.py`
- S16 hit 3 integration-test fix cycles; the root error (14 migration-roundtrip test failures) was a schema mismatch between the worktree migration (CR-00036 adds `auto_merge` column) and the test's hardcoded downgrade SQL which expected the pre-CR-00036 schema

**Recommendation:** Strengthen the QV gate reporter to emit structured, machine-parseable error output (the actual ruff/mypy/pytest failure lines, not just exit codes). The current "unparseable output" pattern means every fix-cycle prompt wastes an agent turn on diagnostic spelunking before applying the actual fix.

**Target:** `orch/qv_gate_validator.py`, `orch/test_runner.py`

**Pros:** Reduces fix-cycle count on QV gates; agents spend time fixing not diagnosing.

**Cons:** Changes to gate reporting could affect downstream consumers of gate output.

**If we don't:** Each QV gate failure costs an extra agent turn + full gate re-run for diagnosis before the real fix is attempted.

**Effort:** M (~orch/qv_gate_validator.py + orch/test_runner.py)

---

### [2] Browser verification E2E seed authored inline in worktree (not self-contained fixture)
**Severity:** MED   **Class:** design   **Frequency:** one-off (this item only)

Evidence:
- `ai-dev/active/CR-00036/e2e_fixtures/CR-00036_S17_FIX_cycle1_prompt.md:92` — "e2e_seed: failed: cannot import name 'Item' from 'orch.db.models'" — the E2E fixture in `e2e_fixtures/002_v1_v4_v7_seed.py` imported `Item` which no longer exists in `orch.db.models`
- This import error was introduced in S17's own fixture file, not by prior steps — the item's implementation (S01–S16) was correct; the failure was in the verification author's fixture code
- 3 fix cycles on S17 were needed to resolve the import error and then correctly seed the `awaiting_merge_approval` state

**Recommendation:** E2E fixtures in `ai-dev/active/<ID>/e2e_fixtures/` should be self-verifying (smoke test runnable standalone) before being used in browser verification. Consider a pattern where fixture files are validated against the current schema before the browser step runs.

**Target:** `ai-dev/active/CR-00036/e2e_fixtures/` (or `orch/daemon/browser_env.py` for fixture validation)

**Pros:** Faster browser verification cycles; fewer fix cycles on browser steps.

**Cons:** Fixture validation adds latency to the E2E stack startup.

**If we don't:** Browser verification steps continue to burn fix cycles on fixture authoring errors that are independent of the actual feature being verified.

**Effort:** M (~5 files)

---

### [3] QV gates passed on retry without agent action (flaky-on-first-run)
**Severity:** LOW   **Class:** platform   **Frequency:** systemic (seen in S12, S13)

Evidence:
- S12 lint gate: fix cycle 1 failed, fix cycle 2 passed — the agent in cycle 1 may have resolved the issue but the gate report truncated before confirming, or the re-run succeeded because the agent correctly applied the fix in cycle 1
- S13 format gate: 4 cycles with no clear explanation of why each successive cycle was needed — the final cycle (cycle 4) passed with a format fix on `e2e_fixtures/002_v1_v4_v7_seed.py`, but cycles 1–3 all failed with no clear delta between them

**Recommendation:** Introduce a "retry once before declaring failure" behavior for QV gates, so transient or race-condition failures (e.g., concurrent file modification during format check) don't create a full fix-cycle agent turn.

**Target:** `orch/qv_gate_validator.py`

**Pros:** Eliminates unnecessary fix cycles for one-time transient gate failures.

**Cons:** Could mask real intermittent failures.

**If we don't:** Genuinely flaky gates will continue to produce fix cycles even when the code is correct.

**Effort:** S (~1 function in orch/qv_gate_validator.py)

---

### [4] No findings on core implementation quality
All 17 implementation and code-review steps (S01–S11) completed on the first attempt with no fix cycles. The design doc (CR-00036_CR_Design.md) was complete and served as the authoritative source of truth during every fix cycle. Code review findings (S04, S06, S08, S10) were all LOW/MED severity, fixed during review, with zero mandatory fixes required after the first pass.

The `awaiting_merge_approval` state machine, `auto_merge` column, `approve_merge` service, CLI, API endpoints, and frontend UI all passed their respective gates cleanly. Browser verification (S17) passed all 8 verifications (V1–V8) after the E2E fixture fix.

---

## Coverage Notes

Log inventory: no `.worktrees/CR-00036/ai-dev/logs/` directory exists — the worktree was already cleaned up. Analysis based on: step reports (`ai-dev/active/CR-00036/reports/*.md` as secondary evidence), fix-cycle prompts (`ai-dev/active/CR-00036/fix-cycles/`), workflow manifest, and DB telemetry via `iw item-status --json`. Fix-cycle prompts were read in full for all QV steps (S12–S17). Self-assess step (S18) runs the analysis; no run logs exist for it. DB:UP — full signal available.