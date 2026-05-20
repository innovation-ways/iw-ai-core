# F-00087 — Step S14 (SelfAssess) Report

**Step**: S14 · **Agent**: `self-assess-impl` · **Date**: 2026-05-20

## What was done

Ran the `iw-item-analyze` skill over F-00087's full execution history (14 steps,
S01–S13) to surface recurring process issues — agent thrash, tool failures,
fix-cycle waste, prompt gaps, manifest issues. Analyzed raw run/fix-cycle logs
under `ai-dev/logs/` and step reports under `ai-dev/active/F-00087/reports/`;
DB telemetry pulled via `iw item-status --json`. **Execution history only —
no review of the generated Pi-runtime code.**

## Files changed

- `ai-dev/active/F-00087/reports/F-00087_self_assess_report.md` — narrative analysis
- `ai-dev/active/F-00087/reports/F-00087_self_assess_findings.json` — structured findings (5 promoted, 2 omitted)
- `ai-dev/active/F-00087/reports/F-00087_S14_SelfAssess_report.md` — this report

## Test results

N/A — analysis step, no tests run.

## Issues / observations

S01–S07 ran cleanly (one run each, no fix cycles); all thrash was in the
verification tail S08–S13. Five findings cleared the promotion bar:

1. **HIGH / prompt** — qv-browser used a `which pi` container litmus test
   instead of the authoritative HTTP signal (twice → 2 wasted S13 runs + 2 fix
   cycles). Fix-cycle 4 already hand-patched F-00087's S13 prompt; the fix needs
   propagating to `QVBrowser_Prompt_Template.md` + the `qv-browser` agent def.
2. **HIGH / platform** — two runs (S13 run7, fix3) were killed by rate limits
   ("You've hit your limit"), never reported, and the orchestrator advanced on a
   stale cycle-3 report.
3. **MED / platform** — every S13 fix cycle re-ran the full QV chain S08–S12,
   running the ~16-min integration suite 4× on already-green code.
4. **MED / prompt** — S01's `tdd_red_evidence` is a retroactive narrative, not a
   captured RED run (explicitly checked per this step's instructions).
5. **MED / prompt** — a new SSE event name (`message.part.added`) reached the
   design mapping table but was never registered with `EventSource.addEventListener`;
   the gap escaped S04/S06/S12 and was caught only at browser verification.

2 lower-priority findings omitted (empty S05 run logs; stale F-00086 test) —
documented in the findings JSON.

**Bottom line**: propagate the `which pi` prohibition into the QVBrowser prompt
template and qv-browser agent definition — S-effort, diagnosis already done.

Soft step — does not block merge.
