# I-00081 — S14 SelfAssess Report

## What was done

Invoked the `iw-item-analyze` skill on the just-completed I-00081 execution. Read all 17 raw step logs under `ai-dev/logs/` in full (largest 343 KB, well under the 1 MB sampling threshold), cross-checked the per-step prompts under `ai-dev/active/I-00081/prompts/`, and pulled the canonical step state via `uv run iw item-status I-00081 --json`. Found 4 promotable patterns and wrote them to the two contracted output files.

## Files changed

- `ai-dev/active/I-00081/reports/I-00081_self_assess_report.md` — human-readable narrative with 4 findings + 2 unpromoted observations.
- `ai-dev/active/I-00081/reports/I-00081_self_assess_findings.json` — structured findings JSON with `bottom_line`, `coverage_notes`, and 4 findings each carrying severity / class / target / evidence / effort / paste_prompt.
- `ai-dev/active/I-00081/reports/I-00081_S14_SelfAssess_report.md` — this report.

No source-tree files touched. Read-only with respect to everything outside `ai-dev/active/I-00081/reports/`.

## Test results

Not applicable — this is an analysis step. Skipped: no tests for analysis step.

## Issues / observations

The workflow ran exceptionally cleanly: **0 fix-cycles, every step exactly one run**, all QV gates green (lint, format, typecheck, 2748 unit tests, 2262 integration tests), browser verification PASS on V0/V1/V2. The 3 test failures inside S01 are the expected TDD RED phase required by CR-00045 and are not findings.

Bottom-line process improvement from the analysis: fix the design-doc generators (or `iw step-done`) so step-report filenames match what downstream prompts reference. The prompt templates substitute `{Agent}` with the OpenCode agent slug (`backend-impl`), but the lifecycle writes reports using the friendly label (`Backend`). Every multi-step item currently burns 1–4 wasted "File not found" tool calls on dependent steps. See `I-00081_self_assess_report.md` finding [1] for full evidence and the recommended fix.

Three other promoted findings: (2) OpenCode tool wrappers should coerce string-typed numeric args (11 schema rejections across S01–S04); (3) the E2E pg_dump is missing an iw-doc-generator-form `diagram-architecture` ProjectDoc, forcing every browser verification of this widget to hand-seed a fixture; (4) the master prompt templates and `iw-item-analyze` skill still reference `ai-dev/work/<ID>/` instead of `ai-dev/active/<ID>/` (already filed by CR-00040 and CR-00041 but not fixed).
