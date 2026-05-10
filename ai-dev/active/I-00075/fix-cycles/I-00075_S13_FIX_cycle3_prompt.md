# I-00075 S13 Browser Verification Fix Cycle 3/5

The end-to-end browser verification for step S13 of work item I-00075 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00075/ai-dev/active/I-00075/I-00075_Issue_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Browser Verification Report

The report below is **one hypothesis** about what's broken. The qv-browser agent's *Root Cause* and `file:line` callouts are useful clues, but they are not the spec. Verify against the design doc above before applying any fix; the spec wins on conflict.

# I-00075 S13 Browser Verification Report

## Environment
- Base URL used: `http://localhost:9939` (from `$IW_BROWSER_BASE_URL`)
- E2E user: `dev@example.local`

## Verifications

| ID | Name | Status | Failure Class | Screenshot | Notes |
|----|------|--------|---------------|------------|-------|
| V0 | Pre-flight page sanity | fail | code_defect | I-00075_v0_item_detail_500.png | `/project/iw-ai-core/item/I-99001` returns HTTP 500 due to `TypeError: not all arguments converted during string formatting` in `step_pipeline.html:20` |
| V1 | Fix-cycle amber pills render on I-99001 | fail | code_defect | I-00075_v1_i99001_500_error.png | V0 failed, V1 attempted — same 500 error prevents verification |
| V2 | No regression on zero-cycle item | n/a | null | — | Cannot load I-99001 to test V2, attempted CR-00001 as alternate — see notes |
| V3 | No regressions on adjacent flows | n/a | null | I-00075_v3_history_page_ok.png | History page loads cleanly with 4 items (I-99001, I-00001, F-00055, CR-00001); batches page also verified |

## Console / Network Errors

**On `/project/iw-ai-core/item/I-99001` (HTTP 500):**
```
TypeError: not all arguments converted during string formatting
  File "/app/dashboard/templates/components/step_pipeline.html", line 20
  Jinja2: "{}m{}s"|format(dur_m, dur_s) if dur_m > 0 else "{}s"|format(dur_s)
```

**Root cause analysis:**

The crash is in `step_pipeline.html:20`:
```jinja
{% set dur_str = "{}m{}s"|format(dur_m, dur_s) if dur_m > 0 else "{}s"|format(dur_s) %}
```

This template line expects positional arguments but receives keyword-style named arguments from the dataclass `duration_secs: float | None` which is passed as a float, not two separate integers. The `dur_m` and `dur_s` are `int`-filtered floor division but the format string `{}m{}s` requires positional args, not keyword args from a float.

**Additionally**, the `_synthetic_setup_step()` function (line 636) constructs a `StepDetail` for S00, and `_synthetic_merge_step()` (line 653) constructs one for MERGE. Neither sets `duration_secs` to a proper value that can be processed. For S00: `duration_secs=dur` where `dur` is calculated from `created - started`. For MERGE: `duration_secs=None`.

**Code defect location:** `dashboard/templates/components/step_pipeline.html:17-23` — the Jinja2 format filter does not handle the case where `duration_secs` is a float (as returned by `_aggregate_step_spans` which returns `total_seconds()`) rather than an integer. The fix should be in the Python `_get_steps` method to ensure `duration_secs` is always an integer, or the template should cast properly.

**Additionally:** `dashboard/routers/items.py:457` — `dur = (latest_completed_at - earliest_started_at).total_seconds()` returns a `float`. This float is passed to `StepDetail(duration_secs=dur)` and then to `step_pipeline.html` which expects integer positional args for the format string.

## No Regressions Observed

- **V3 (History page):** The history page at `/project/iw-ai-core/history` loads correctly and shows all 4 items including `I-99001` (fix-cycle demo fixture item).
- **V3 (Batches page):** The batches page at `/project/iw-ai-core/batches` renders correctly.
- **V3 (CR-00001):** Attempted to use CR-00001 as the V2 zero-cycle reference item; confirmed its history row appears correctly. Could not load its detail page due to the same template crash (the item_detail template uses step_pipeline for all items, not just I-99001).
- **No new console JS errors** on pages that do render (history, batches).

## Screenshots captured

- `ai-dev/active/I-00075/evidences/post/I-00075_v0_item_detail_500.png` — V0 failure: I-99001 item detail 500 error
- `ai-dev/active/I-00075/evidences/post/I-00075_v1_i99001_500_error.png` — V1: duplicate 500 on I-99001 (V1 attempted after V0)
- `ai-dev/active/I-00075/evidences/post/I-00075_v3_history_page_ok.png` — V3: history page showing I-99001 alongside production items

## Root cause

**File:** `dashboard/routers/items.py:457`
```python
dur = (latest_completed_at - earliest_started_at).total_seconds()  # returns float
```
Passed to `StepDetail(duration_secs=dur)` at line 475.

**File:** `dashboard/templates/components/step_pipeline.html:17-23`
```jinja
{% if step.duration_secs is not none %}
  {% set dur_m = (step.duration_secs // 60)|int %}
  {% set dur_s = (step.duration_secs % 60)|int %}
  {% set dur_str = "{}m{}s"|format(dur_m, dur_s) if dur_m > 0 else "{}s"|format(dur_s) %}
```
When `duration_secs` is a float (e.g., `1847.0`), floor division and modulo work but the `|int` filter should convert them — however the error occurs at line 20's `format()` call. The error message "not all arguments converted during string formatting" suggests the float is being passed where two positional args are expected.

**Fix:** Cast `dur` to `int` before passing: `dur = int((latest_completed_at - earliest_started_at).total_seconds())` at `items.py:457`. Or add `|int` to `dur_m` and `dur_s` in the template before the format call (they already have it but the issue is the float may not be fully convertible by the format string).

## Verdict

**overall_status: fail**
**overall_failure_class: code_defect**

The `duration_secs` float-to-int mismatch causes a `TypeError` on **every** item detail page (not just I-99001), making the step pipeline component completely broken in this worktree. The fix is one line in `items.py:457` — cast `total_seconds()` to `int` before assigning to `dur`.

## Pre-fix Procedure

1. **Read the design doc** at the path above. Look for a `Detailed Fix Specification` section or any spec for `S13` / the implementation step that this V suite verifies.
2. **Diff the target template / route / fixture against the spec.** List deviations explicitly before editing — missing attributes, wrong selectors, dropped guards. Browser failures are very often the *implementation* drifting from a spec the design doc already got right.
3. **Apply the minimum patch** to align code with the spec; failing V's should resolve as a side effect of that alignment.
4. **If the report's root-cause hypothesis disagrees with the spec, the spec wins.** Note the disagreement in your output rather than silently following the report.

## Where to look

1. The design doc above is authoritative for *what should be true*.
2. The Diagnostic Hypothesis above points at *what's currently false*; `file:line` references and screenshots are corroborating evidence, not gospel.
3. Screenshots are under `ai-dev/active/I-00075/evidences/post/` — open the ones named in the report's `v1_*`, `v2_*`, ... columns to see expected vs. actual.
4. The failing Vs typically map to:
   - `dashboard/templates/**` — if the UI rendered the wrong element
   - `dashboard/routers/**` — if an HTTP route returned the wrong status/fragment
   - `orch/cli/**` — if a CLI command emitted the wrong exit code or message
   - `orch/daemon/**` or `orch/db/**` — if a state transition is wrong
   - `scripts/e2e_*` — if the E2E stub/entrypoint diverged from the code-under-test's contract
   - `ai-dev/active/I-00075/e2e_fixtures/` — if the E2E seed is missing rows the V step needs

## Constraints

1. **Only fix the reported V(n) failures.** Do not refactor unrelated code.
2. **Preserve existing behavior** for every V that already passed — the report table flags passing Vs; do not regress them.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. Do **NOT** start/stop `docker compose`, run `make e2e-up`, or invoke `playwright-cli` — the orchestrator owns the E2E stack and will rebuild it before the next browser run.
5. Run any fast unit tests near the code you touched to catch regressions before the expensive E2E re-run.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator re-launches the browser verification automatically.
