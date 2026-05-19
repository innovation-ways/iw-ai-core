# CR-00062 S14 SelfAssess Report

## Step Summary

Ran the `iw-item-analyze` skill against the just-completed CR-00062 execution. Examined raw run logs under `.worktrees/CR-00062/ai-dev/logs/`, fix-cycle prompts under `ai-dev/active/CR-00062/fix-cycles/`, agent self-reports under `ai-dev/active/CR-00062/reports/`, and DB telemetry via `iw item-status CR-00062 --json`. Did **not** review the generated code.

## Item Analysis: CR-00062

**Bottom line:** Promote two brittle test-constant patterns (Alembic `_HEAD_REVISION` and hardcoded `agent_runtime_options` row counts) into the Tests-impl prompt template as an explicit "if S01 touched migrations or seed data, also update these pinned tests" checklist — they cost an entire S13 fix cycle here and will fire on every future schema-touching CR.

**Steps analyzed:** 14 · **Steps with retries:** 4 (S02, S10, S11, S13) · **Total fix-cycles:** 2 (S11, S13) · **DB signal:** yes.

**Coverage notes:** Read S01/S03/S04/S05/S06/S07/S08/S09 logs in full (all < 2 KB). Sampled tail/grep for S11 run3 (19 KB), S12 run1/run2 (~391 KB each), S13 run1/run3 (~380 KB each); read the FAILED summary block in full for both fix-cycle prompts. No `*_run4.log` for any step except S11 (one spurious replay). DB telemetry: full step list via `iw item-status --json`. Did not query daemon events table (file evidence was sufficient).

---

### [1] Schema-touching CR breaks Alembic-head-pinned integration test

**Severity:** HIGH · **Class:** prompt · **Frequency:** systemic · **Target file:** `iw-ai-core`

**Evidence:**
- `ai-dev/logs/CR-00062_S13_run1.log:3314` — `FAILED tests/integration/daemon/test_phase2_apply_no_self_deadlock.py::test_i_00063_apply_succeeds_when_no_blocking_lock`
- `tests/integration/daemon/test_phase2_apply_no_self_deadlock.py:37` — `_HEAD_REVISION = "6d78323d0954"  # head — CR-00062 add pi runtime options`
- `ai-dev/active/CR-00062/reports/CR-00062_S13_QvGate_report.md` (via fix cycle) — `bumped _HEAD_REVISION to 6d78323d0954 (the new Pi-runtime migration head)`

**Recommendation:** Extend the Tests-impl prompt template (and S01 Database-impl prompt) with a checklist item: "If this step adds a new Alembic revision, grep for `_HEAD_REVISION` and any test that asserts on alembic head; update them as part of S05." S05 added new tests but had no instruction to refresh existing ones — burning a full fix cycle (~17 minutes of integration tests) on a deterministic, foreseeable failure.

**Target:** `templates/design/CR_Design_Template.md` (S05 Tests prompt boilerplate) and the Tests-impl agent system prompt (`agents/claude/tests-impl.md`, `agents/opencode/tests-impl.md`, `agents/pi/tests-impl.md`).

**Pros:** Saves one entire integration-test fix cycle (~17 min) on every schema-touching CR. Tests stay in lockstep with migrations without human intervention.

**Cons:** Slightly longer prompt; one more checklist item agents must read.

**If we don't:** Every future migration-adding CR (next is presumably another `_runtime_options` row, then any column add) burns the S13 fix slot the same way. Worse, when the fix budget is exhausted, the item strands.

**Effort:** S (~5 lines in the Tests prompt boilerplate; ~5 lines in each agent's system prompt).

---

### [2] Hardcoded seed-row counts in `agent_runtime_options` tests are brittle

**Severity:** HIGH · **Class:** design · **Frequency:** systemic · **Target file:** `iw-ai-core`

**Evidence:**
- `ai-dev/logs/CR-00062_S13_run1.log:3317-3318` — `FAILED tests/integration/test_agent_runtime_options.py::TestAgentRuntimeOptionsTable::test_seed_rows_present` and `test_can_disable_non_default_row`
- `ai-dev/active/CR-00062/reports/CR-00062_S13_QvGate_report.md` (fix log) — `6 → 8 rows, with the two pi rows at sort_order=25, 26 … 5 → 7 non-default rows`
- `ai-dev/active/CR-00062/CR-00062_CR_Design.md` AC list — adds two seed rows but says nothing about updating tests that assert on totals

**Recommendation:** Either (a) refactor `test_seed_rows_present` / `test_can_disable_non_default_row` to assert on shape/properties (e.g., "every row has sort_order > 0", "exactly one is_default=true") rather than literal counts, or (b) add an explicit instruction to the CR design template's "seed data" section: "If your migration seeds new rows in a table covered by row-count assertions, list the assertion file in the same step's task list." The S01 design context already knew two rows were being added; the S05 prompt didn't connect that fact to existing assertions.

**Target:** `tests/integration/test_agent_runtime_options.py` (refactor — preferred) **or** `templates/design/CR_Design_Template.md` (template note).

**Pros:** Refactor option (a) protects against every future row-add CR. Template option (b) is cheaper but only as good as the next prompt reader's attention.

**Cons:** Refactor changes test semantics; some count-assertions are intentional invariants that should stay. Need to distinguish the two.

**If we don't:** Same pattern as [1] — every seed-row-touching CR burns a fix cycle.

**Effort:** S–M (refactor: ~15 lines in 1 file. Template note: ~3 lines.)

---

### [3] `make quality` "test-assertions" gate surfaces pre-existing violations from prior CRs

**Severity:** MED · **Class:** platform · **Frequency:** systemic · **Target file:** `iw-ai-core`

**Evidence:**
- `ai-dev/logs/CR-00062_S11_run1.log:8-9` — `tests/unit/daemon/test_scope_overlap.py:127: tautology …` and `tests/unit/test_auto_merge_aggregator.py:315: tautology …`
- `ai-dev/active/CR-00062/reports/CR-00062_S11_QvGate_report.md` (fix log) — `Both tests were merged from earlier work (CR-00058, I-00096) but were missed by the assertion baseline; the scanner classifies assert <expr> in <expr> as tautological, so the gate flagged them as new violations.`
- Git status (per branch state) — `M tests/unit/daemon/test_scope_overlap.py` · `M tests/unit/test_auto_merge_aggregator.py` (these are *not* CR-00062 scope files)

**Recommendation:** The assertion-strength baseline is leaking — violations land via merge but only surface in the next CR's quality gate. Two options: (a) make `make quality` also run as a *required* check on `main` after every merge (separate from per-CR gating), so violations are caught immediately rather than carried; (b) move `test-assertions` to a separate Makefile target that runs as a *blocking* pre-merge check in the daemon's merge queue, not as part of the per-CR quality gate (so per-CR gates only flag what the CR itself touched). Option (b) requires diff-aware scanning.

**Target:** `Makefile` (split `test-assertions` from `quality`), `orch/daemon/merge_queue.py` or `scripts/check_assertion_strength.py` (diff-aware mode).

**Pros:** Stops cross-CR leakage. Eliminates the "wait, why is CR-00062 fixing CR-00058's test?" surprise the agent (correctly) flagged.

**Cons:** Operational change to the merge gate; may need to grandfather existing violations.

**If we don't:** Every CR keeps inheriting one or two latent violations from prior merges, eating fix-cycle slots and forcing scope-violating edits. The CR-00062 fix cycle correctly applied the scope-broadened edit but it set a bad precedent (in-scope CRs reaching into unrelated test files).

**Effort:** M (~50 lines, 2-3 files, requires a baseline-migration step).

---

### [4] Spurious QV-gate re-runs after a green pass (S02 ran 3x, S10 ran 3x)

**Severity:** MED · **Class:** platform · **Frequency:** recurring · **Target file:** `iw-ai-core`

**Evidence:**
- `ai-dev/logs/CR-00062_S02_run1.log:17-18` — `3 passed in 9.09s … Completed CR-00062 step S02` then `S02_run2.log` and `S02_run3.log` both pass identically
- `ai-dev/logs/CR-00062_S10_run1.log` / `_run2.log` / `_run3.log` — three identical 4-line "All checks passed!" logs, ~5 min and ~50 min apart
- `ai-dev/logs/CR-00062_S11_run4.log` — same as `_run3.log`, run an hour later

**Recommendation:** Investigate the daemon's QV-gate idempotency check. A step that's already `status=completed` should not be relaunched. The repeated `_run3` / `_run4` timestamps span ~45 min and ~1 hour respectively, suggesting either (a) the daemon's poll loop re-acquires the step after a daemon restart / SIGHUP, or (b) an item-level retry handler is replaying *all* steps rather than the failing one.

**Target:** `orch/daemon/batch_manager.py` (step-selection logic) or `orch/daemon/fix_cycle.py` (replay scope).

**Pros:** Each spurious S02 re-run consumes ~9s of integration-test time + DB churn; each spurious S10 / S11 / S13 re-run consumes minutes. Avoiding these directly shortens batch wall-clock.

**Cons:** Need to confirm via DB event log (`daemon_events`) whether these are daemon restarts or genuine re-launches; root-causing may be non-trivial.

**If we don't:** Every batch pays a few minutes of redundant gate execution. With concurrent worktrees this scales linearly.

**Effort:** S–M (depends on root cause; likely a single condition in batch_manager).

---

### [5] `make quality` emits 111 deptry warnings as noise on every run

**Severity:** LOW · **Class:** environment · **Frequency:** recurring · **Target file:** `project`

**Evidence:**
- `ai-dev/logs/CR-00062_S11_run3.log:tail` — `Found 111 dependency issues.` followed by `For more information, see the documentation: https://deptry.com/`
- `ai-dev/logs/CR-00062_S11_run4.log:tail` — identical 111-issue tail

**Recommendation:** Either (a) configure `deptry` via `pyproject.toml` `[tool.deptry]` to exclude `.claude/skills/**` (most of the noise is `lib`/`pptx`/`checks` modules from vendored skill scripts that aren't part of the project's dep graph) and acknowledge the genuine `dashboard/middlewares/alembic_guard.py: 'starlette'` transitive imports explicitly, or (b) drop deptry from `make quality` entirely and run it as a separate, advisory `make deps-check` target. Right now the `|| true` mask hides the noise from the exit code but still pollutes ~100 lines of every quality log, hurting log-grep usability and making real issues hard to spot.

**Target:** `pyproject.toml` `[tool.deptry]` section, `Makefile` `quality` target.

**Pros:** ~100 fewer lines per quality-gate log; future grep `Error|failed` queries become tractable.

**Cons:** Existing deptry signal is lost if simply disabled; takes a few minutes to write the exclusion list correctly.

**If we don't:** Logs stay polluted; future log-analysis steps (including this one) keep paying the cost of skimming past it.

**Effort:** S (~10 lines in `pyproject.toml`).

---

## Result Contract

```json
{
  "step": "S14",
  "agent": "self-assess-impl",
  "work_item": "CR-00062",
  "completion_status": "complete",
  "files_changed": [
    "ai-dev/active/CR-00062/reports/CR-00062_S14_SelfAssess_report.md"
  ],
  "preflight": {
    "format": "n/a — analysis only",
    "typecheck": "n/a — analysis only",
    "lint": "n/a — analysis only"
  },
  "tests_passed": true,
  "test_summary": "analysis-only",
  "tdd_red_evidence": "n/a — self-assess step",
  "process_findings": [
    {"id": "P1", "category": "prompt", "severity": "high", "summary": "S05 Tests prompt has no checklist for refreshing _HEAD_REVISION-pinned tests when S01 adds a migration", "recommendation": "Extend Tests-impl prompt and CR design template with a migration-head-update checklist item"},
    {"id": "P2", "category": "prompt", "severity": "high", "summary": "Hardcoded agent_runtime_options seed-row counts in integration tests break on every seed-data CR", "recommendation": "Refactor tests to assert shape/properties, OR add a template note linking seed-data changes to count-assertion files"},
    {"id": "P3", "category": "tool", "severity": "medium", "summary": "make quality's test-assertions scanner catches pre-existing violations from prior CRs (CR-00058/I-00096) in unrelated files, forcing scope-broadening edits in S11 fix cycle", "recommendation": "Split test-assertions into a diff-aware per-CR check + a blocking post-merge full-tree check"},
    {"id": "P4", "category": "manifest", "severity": "medium", "summary": "QV gates S02 (3 runs), S10 (3 runs), S11 (4 runs) re-ran after green passes — daemon idempotency check is missing or misfiring", "recommendation": "Audit batch_manager.py step-selection to skip already-completed QV gates on daemon restart / SIGHUP"},
    {"id": "P5", "category": "env", "severity": "low", "summary": "deptry emits 111 advisory issues on every quality run, gated with || true but polluting logs", "recommendation": "Configure [tool.deptry] excludes for .claude/skills/** OR move deptry to a separate advisory make target"}
  ],
  "blockers": [],
  "notes": "Workflow executed cleanly overall: 14 steps, 2 fix-cycles, no item-level retries or escalations. All findings are systemic patterns (not CR-00062-specific code issues). Per skill scope: did NOT review generated code."
}
```
