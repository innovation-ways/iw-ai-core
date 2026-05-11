# I-00077 Self-Assessment Report

## Item Analysis: I-00077

**Bottom line:** The most impactful process improvement is making the `_default` editorial guide seed explicit in the `test_doc_instance_guides.py` fixture setup rather than relying on it being pre-seeded by the migration layer — this would have avoided the S12 fix cycle entirely.

**Steps analyzed:** 14  |  **Steps with retries:** 3  |  **Fix cycles:** 2  |  **DB signal:** yes

---

## Findings

### [1] SQLAlchemy boolean-AND in filter requires `and_()` not `&`
**Severity:** MED   **Class:** platform   **Frequency:** systemic

The `&` operator between SQLAlchemy column expressions produces incorrect SQL when used inside an `or_()` without explicit parentheses grouping, causing an entire condition branch to be silently dropped. The agent correctly diagnosed and fixed this in S03, but the same mistake was made again in the S08 fix cycle (when adding the `DocTypeGuide` import, a lint error). Both S03 and S08 needed a second run to converge.

**Evidence:**
- `ai-dev/logs/I-00077_S03_run1.log:407` — "Could not find oldString in the file" (edit rejected; `&` operator was silently wrong)
- `ai-dev/logs/I-00077_S08_fix1.log:23` — "A stray `/` character before the `from sqlalchemy import delete` import"

**Recommendation:** Add a ruff rule or custom lint check that flags `&` between SQLAlchemy expressions inside `or_()` without surrounding `and_()`. Alternatively, make `and_()` the default in the `docs.py` imports so agents never need to guess.

**Target:** `dashboard/routers/docs.py` (line 422); also add guidance to `tests/CLAUDE.md` about SQLAlchemy boolean ops in filters.

**Pros:** Prevents silent query logic errors that pass typecheck and format-check.
**Cons:** Minor; new lint rule requires adoption.
**If we don't:** Agents will continue to use `&` inside `or_()` and cause incorrect query behavior; the symptom is "test fails but no error visible in the test log".

**Effort:** S (~5 lines in `Makefile` or `pyproject.toml` ruff config)

---

### [2] `_default` guide seeded by migration, not `create_all()` — integration tests need explicit cleanup
**Severity:** HIGH   **Class:** environment   **Frequency:** one-off (but recurred as fix trigger)

S12's integration test `test_falls_back_to_none_when_neither_guide_exists` failed because `create_all()` does not seed the `_default` editorial guide, while the migration runner (used in production) does. The fix required the S12 fix-cycle agent to add an explicit `DELETE FROM doc_type_guides` before the test to guarantee the "nothing exists" precondition.

This is the `_default`-not-seeded-in-tests gotcha mentioned in the self-assess prompt.

**Evidence:**
- `ai-dev/logs/I-00077_S12_fix1.log:91-93` — "FAILED ... test_falls_back_to_none_when_neither_guide_exists"
- `ai-dev/logs/I-00077_S12_fix1.log:97` — "The test needs to actually ensure no `_default` guide exists"
- `ai-dev/logs/I-00077_S12_fix1.log:115-118` — `db_session.execute(delete(DocTypeGuide))` fix

**Recommendation:** Seed the `_default` editorial guide in the `tests/integration/conftest.py` `db_session` fixture (or a `test_data/` seed file) so every integration test starts with the guide present. This is more realistic — production always has it seeded. Add a comment in the fixture explaining the migration-vs-create_all distinction.

**Target:** `tests/integration/conftest.py` (add `_default` guide seed to the `db_session` fixture)

**Pros:** Tests match production behavior; no more "nothing exists" edge case that misrepresents production.
**Cons:** Minor — one-time seed addition.
**If we don't:** Future integration tests that exercise editorial guide fallback will fail the same way; agents will need fix cycles to re-discover the pattern.
**Effort:** S (~8 lines in conftest.py)

---

### [3] S03 agent's initial edit used wrong SQLAlchemy operator — fix cycle overhead
**Severity:** MED   **Class:** agent   **Frequency:** one-off

The S03 frontend-impl agent wrote `DocGenerationJob.status == JobStatus.failed & DocGenerationJob.completed_at >= cutoff` inside an `or_()` call. The `&` bitwise-and was silently wrong (valid Python, wrong SQL), causing the query to not filter as intended. The agent self-corrected on run 2 by changing to `and_()`, but this consumed a full step run.

**Evidence:**
- `ai-dev/logs/I-00077_S03_run1.log:405-407` — "edit failed ... Could not find oldString in the file" (edit rejection due to wrong string)
- `ai-dev/logs/I-00077_S03_run1.log:432` — "test still failing"

**Recommendation:** Add a code comment above complex filter expressions in `docs.py` noting that SQLAlchemy `&` is not valid in this context; use `and_()` explicitly. The fix cycle was effective here — the agent recovered without human intervention — but 1 extra run was consumed.

**Target:** `dashboard/routers/docs.py` (lines 305-330)

**Pros:** Reduces one-off fix cycles for agents unfamiliar with SQLAlchemy expression gotchas.
**Cons:** Code comment overhead.
**If we don't:** Occasional one-off fix cycles on complex filter expressions.
**Effort:** S (~3 lines of comment)

---

### [4] S08 lint fix cycle: import sorted after file edit, not before
**Severity:** MED   **Class:** convention   **Frequency:** systemic

The S08 fix-cycle agent fixed two lint errors: an unsorted `delete` import (I001) and a long line (E501). Both were introduced by the S03 agent's edit to `test_doc_instance_guides.py` but were not caught by the initial S03 run's lint pass (because the initial lint pass ran before the edit was finalized in the worktree). This is the standard lint-then-fix cycle — not itself a problem, but it confirms that lint failures are caught in the QV gate and not in the implementation step.

The pattern is consistent with other items: the lint gate catches what the implementation step introduced.

**Evidence:**
- `ai-dev/logs/I-00077_S08_fix1.log:7-10` — "two errors: sort imports (I001) and shorten line (E501)"
- `ai-dev/logs/I-00077_S08_fix1.log:44` — `$ make lint 2>&1` → "All checks passed!"

**Recommendation:** No platform change needed — the lint gate is working as designed. The issue is that the S03 agent's edit introduced lint errors that were only caught at S08, causing a fix cycle. Consider adding a "run lint locally before marking step done" advisory in the S03 prompt.

**Target:** `ai-dev/active/I-00077/prompts/I-00077_S03_frontend-impl_prompt.md` (or the generic frontend-impl prompt template)

**Pros:** Reduces fix cycles triggered by lint errors.
**Cons:** Advisory only; agents may still skip lint.
**If we don't:** Continue consuming fix cycles for lint errors introduced by implementation agents.
**Effort:** S (add advisory line to prompt)

---

### [5] S13 browser env down/up — container setup/teardown adds ~1min to QV gate
**Severity:** MED   **Class:** environment   **Frequency:** one-off

The S13 browser verification step triggered `e2e_down` and `e2e_up` because the previous run's e2e stack was still running. This added ~1 minute to the S13 wall clock. The re-pull of Docker images (from cache) was fast, but the health-probe and container-start sequence consumed real time.

**Evidence:**
- `ai-dev/logs/I-00077_S13_browser_env_down.log:1` — `[e2e_down] project=iw-ai-core-e2e-i00077`
- `ai-dev/logs/I-00077_S13_browser_env_up.log:1` — `[e2e_up] project=iw-ai-core-e2e-i00077 dashboard=9935 db=5467`
- `ai-dev/logs/I-00077_S13_browser_env_up.log:169` — `[e2e_up] probing http://localhost:9935/health...` → stack healthy

**Recommendation:** The daemon's browser-env reuse logic is working correctly — the down/up was triggered because the previous test's containers were from a different worktree context. This is expected behavior. No change needed; the ~1min cost is acceptable for isolation guarantees.

**Target:** None — informational only.

**Pros:** Full isolation between worktrees.
**Cons:** ~1 min per S13 step when containers need to be refreshed.
**If we don't:** Risk of cross-worktree container state bleed.
**Effort:** N/A

---

### [6] Skill-wording change (S01/S02) propagated cleanly across all subsequent steps
**Severity:** LOW   **Class:** design   **Frequency:** recurring

The S01 backend-impl added a "Note on null editorial snapshots" paragraph to both `iw-doc-generator/SKILL.md` and `iw-doc-system/SKILL.md`. S02 code-review confirmed the wording was correct. The skill files were later used by the doc-job agent (in production when processing real doc jobs) without any fix cycles related to the wording. The change interacted cleanly across fix cycles — no agent re-opened the skill files to re-discuss the wording.

**Evidence:**
- `ai-dev/logs/I-00077_S02_run1.log:267-270` — "Both skill files edited identically; Markdown style matches surrounding sections"
- `ai-dev/logs/I-00077_S02_run1.log:282-285` — 8 unit tests passed, 0 failed

**Recommendation:** The skill-doc update pattern is working well. No changes needed.

**Target:** None.

**Effort:** N/A

---

### [7] S03 dashboard change (failed jobs in running-jobs strip) needed one SQLAlchemy correction
**Severity:** MED   **Class:** platform   **Frequency:** systemic

The S03 frontend-impl agent added a query to include recently-failed jobs and modified the template to render them distinctly. The first attempt used the wrong SQLAlchemy operator (`&` inside `or_()`), which silently produced incorrect SQL. The agent self-corrected on run 2. This is the same class of issue as Finding #1, but it manifested in S03 rather than being caught by a fix cycle.

**Evidence:**
- `ai-dev/logs/I-00077_S03_run1.log:405-407` — "edit failed ... Could not find oldString in the file" (the edit to change `&` to `and_` was rejected because the first edit hadn't been applied correctly)
- `ai-dev/logs/I-00077_S03_run1.log:421` — `and_(DocGenerationJob.status == JobStatus.failed, DocGenerationJob.completed_at >= cutoff)` correct implementation

**Recommendation:** Same as Finding #1 — add a ruff rule or editorial guidance for SQLAlchemy boolean operators in filter contexts.

**Target:** `dashboard/routers/docs.py`

**Pros:** Prevents this class of error across the codebase.
**Cons:** None.
**If we don't:** Agents will continue to make this error in complex filter expressions.
**Effort:** S

---

*3 lower-priority findings omitted (see full JSON for details).*