### Item Analysis: F-00087

Bottom line: Propagate the `which pi` litmus-test prohibition that fix-cycle 4 hand-patched into F-00087's S13 prompt back up into the `QVBrowser_Prompt_Template.md` and the `qv-browser` agent definition — that single misdiagnosis cost two browser runs and two fix cycles, and the template fix is S-effort because the diagnosis is already written.

Steps analyzed: 14   Steps with retries: 7 (S05, S08, S09, S10, S11, S12, S13)   Total fix-cycles: 5 (S12×1, S13×4)   DB signal: yes

The implementation half of the workflow (S01–S07) ran cleanly: one run each, no fix cycles. S02 found 1 CRITICAL + 1 HIGH + 2 MEDIUM and S03 resolved them; S06's cross-agent review caught a real cross-layer wiring gap (`get_runtime_for_tab()` unwired) and S07 fixed it — both worked exactly as the review gates are designed to. **All thrash was concentrated in the verification tail (S08–S13).** The integration-test step had one genuine failure; the browser-verification step (S13) burned 5 runs and 4 fix cycles, of which only the first run exposed a real defect — the rest was a misdiagnosis loop plus two rate-limit kills.

---

[1] qv-browser used a `which pi` container litmus test instead of the verification's authoritative signal — twice
    Severity: HIGH   Class: prompt   Frequency: systemic
    Evidence:
      - ai-dev/logs/F-00087_S13_run3.log:1 — "Root cause: `docker exec which pi` → not found in `e2e-dashboard` container"
      - ai-dev/logs/F-00087_S13_run5.log:1 — "Pi binary is not installed in the E2E stack image ... marked V4-V7 n/a"
      - ai-dev/logs/F-00087_S13_fix4.log — "the qv-browser agent used `which pi` as a litmus test and gave up after seeing 'not found'"
      - ai-dev/logs/F-00087_S13_run9.log:1 — "a litmus test the step prompt explicitly forbids" (the prohibition existed only AFTER fix-cycle 4 hand-patched the prompt)
    Recommendation: Move the prohibition fix-cycle 4 wrote into F-00087's item-specific S13 prompt up into the template and agent definition: qv-browser must NOT use container introspection (`which`, `docker exec ... which`) as a pass/fail verdict — the authoritative signal is the HTTP response of a real `runtime=pi` tab creation (201 = wired, 503 = genuinely unavailable). The dashboard logs its stub-fallback decision; tell the agent to read that log line.
    Target: templates/design/QVBrowser_Prompt_Template.md (then `iw sync-templates`); also agents/claude/qv-browser.md and agents/opencode/qv-browser.md
    Pros: Diagnosis already done by fix-cycle 4; one paragraph of prompt text prevents a 4-cycle thrash on every future runtime-shaped browser step.
    Cons: Slightly longer browser-verification prompt.
    If we don't: Every future runtime that ships a stub fallback (the established CR-00062 pattern) risks the same false `ENV_DATA_MISSING` verdict and the same 2-run / 2-cycle waste.
    Effort: S (~15 lines, 1 template + 2 agent files)

[2] Rate-limit kills mid-step left the workflow advancing on a stale report
    Severity: HIGH   Class: platform   Frequency: systemic
    Evidence:
      - ai-dev/logs/F-00087_S13_run7.log:1 — "You've hit your limit · resets 2:20am (Europe/Lisbon)" (entire 55-byte run, no step-done/step-fail)
      - ai-dev/logs/F-00087_S13_fix3.log:1 — "You've hit your limit · resets 2:20am (Europe/Lisbon)" (fix-cycle 3 produced nothing)
      - ai-dev/logs/F-00087_S13_fix4.log — "run 7's qv-browser process died (rate-limited, never reported completion) and the orchestrator surfaced an older cycle-3 report whose findings had already been partially fixed"
    Recommendation: The step executor should detect the "You've hit your limit" / rate-limit sentinel in agent output and treat the run as *incomplete* — pause and retry after the reset window rather than advancing the fix cycle. At minimum, a run that never calls `step-done`/`step-fail` must not let the orchestrator surface a prior cycle's report as current.
    Target: executor/step_executor_lib.sh
    Pros: Stops a transient quota event from corrupting fix-cycle state; saves the next agent from spending its whole budget untangling the confusion (as fix-cycle 4 did here).
    Cons: Adds a sentinel-detection branch and a wait/retry path to the executor.
    If we don't: Any rate-limit kill during a fix cycle can silently resurface stale findings, sending the next cycle to "fix" already-fixed problems.
    Effort: M (~30–50 lines, 1 file)

[3] Every S13 fix cycle re-ran the entire QV gate chain S08–S12, including the ~16-min integration suite, on already-green code
    Severity: MED   Class: platform   Frequency: recurring
    Evidence:
      - ai-dev/logs/F-00087_S08_run1.log:3 & F-00087_S08_run4.log:3 — "All checks passed!" (lint ran 4×, green every time)
      - ai-dev/logs/F-00087_S11_run1.log:3575 & F-00087_S11_run4.log:3575 — "3271 passed ... in ~87s" (unit suite ran 4×, green every time)
      - ai-dev/logs/F-00087_S12_run1.log:3198 — "1 failed, 2772 passed ... in 991.10s (0:16:31)" (only run with a real failure)
      - ai-dev/logs/F-00087_S12_run5.log:3161 — "2773 passed ... in 988.40s" (runs 3/4/5 all green re-runs of the 16-min suite)
    Recommendation: When a fix cycle's changed files are statically scoped (S13 fix-cycle 1 touched only `chat.js`, a static asset), scope the QV re-run to affected gates instead of restarting at S08 — or resume the gate chain from the failed gate. A full re-run after a Python change is defensible; re-running the 16.5-min integration suite after a JS-only change is pure wall-clock waste (~50 min of integration suite spent re-validating unchanged code here).
    Target: executor/step_executor.sh
    Pros: Cuts the verification-tail wall-clock of every multi-fix-cycle item; this item's S08–S12 ran 4× each.
    Cons: Requires a changed-files→gates impact map; a too-narrow map could miss a regression.
    If we don't: Every item that needs >1 fix cycle in a late step keeps paying the full QV chain per cycle — most expensively the integration suite.
    Effort: M (~workflow logic, 1–2 files)

[4] S01's `tdd_red_evidence` is a retroactive narrative, not a captured RED run
    Severity: MED   Class: prompt   Frequency: systemic
    Evidence:
      - ai-dev/logs/F-00087_S01_run1.log:1 — "tdd_red_evidence: Modules pre-existed at end of two-agent run; expected RED phase documented in report (ModuleNotFoundError: No module named 'orch.chat.pi')"
    Recommendation: S01 was explicitly checked per this step's instructions. Its `tdd_red_evidence` cites no specific failing test and no captured failure output — it states the modules already existed by report time, i.e. no RED run was preserved. The Backend impl agent prompt must require capturing the literal RED-run output (the failing `pytest <test>` invocation + the `ImportError`/`ModuleNotFoundError` traceback) into the report BEFORE writing any implementation file; for multi-agent ("two-agent run") backend steps, the first agent must record RED evidence before handoff.
    Target: agents/claude/backend-impl.md and agents/opencode/backend-impl.md
    Pros: Makes TDD RED evidence auditable instead of a self-asserted claim; cheap prompt change.
    Cons: Adds a mandatory capture step to the Backend agent's flow.
    If we don't: TDD-first cannot be verified after the fact for any new-subpackage backend step — the RED phase is unfalsifiable.
    Effort: S (~10 lines, 2 files)

[5] A new SSE event name reached the design's §Scope mapping table but was never registered with `EventSource.addEventListener`, and no test layer below browser verification covers named-event subscription
    Severity: MED   Class: prompt   Frequency: systemic
    Evidence:
      - ai-dev/logs/F-00087_S13_run1.log:1 — "V4 FAIL ... no streaming agent response ever reaches the UI ... message.part.added payloads from the normalizer never render"
      - ai-dev/logs/F-00087_S13_fix1.log:1 — "chat.js:NAMED_EVENTS didn't include message.part.added ... EventSource only invokes handlers registered via addEventListener for named events, so the Pi text frames were silently dropped"
      - ai-dev/logs/F-00087_S06_run1.log:1 — final cross-agent review passed S04's frontend; the gap escaped S04, S06, and S12 (integration tests "bypass the dashboard SSE stack")
    Recommendation: This is a process/test-coverage gap, not a code critique: the gap escaped frontend impl (S04), the cross-agent review (S06), and integration tests (S12), and was caught only at browser verification. The Frontend impl agent prompt should mandate that every SSE event name in a design's event-mapping table be both added to the `NAMED_EVENTS` set AND covered by a dashboard-level test that asserts `addEventListener` registration — so the gap fails at S12, not S13.
    Target: agents/claude/frontend-impl.md and agents/opencode/frontend-impl.md
    Pros: Pushes detection of unregistered named events from the expensive browser step to a fast dashboard test.
    Cons: Adds a checklist item to the frontend prompt.
    If we don't: Every new SSE event name risks being silently dropped by `EventSource` until browser verification, costing a full fix cycle each time.
    Effort: S (~10 lines, 2 files)

---

2 lower-priority findings omitted (ask to see them): (a) S05's two run logs are both 0 bytes — the Tests step's stdout was never captured, blinding this very analysis for S05 [platform, observability]; (b) a stale F-00086 RED-evidence test (`test_post_tabs_rejects_unknown_runtime`) flipped to failing when F-00087 added `pi` to the allowlist and caused S12's only real failure [design].
