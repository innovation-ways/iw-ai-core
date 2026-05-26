### Item Analysis: I-00114

Bottom line: add a schema-version/TODO note to `executor/pi_narration_guard.py` so future pi JSONL shape changes do not silently misclassify narration exits.

Steps analyzed: 13   Steps with retries: 6   Total fix-cycles: 6   DB signal: yes

Anchors checked:
- Narration-exit recurrence within this incident itself: no `step_crashed` daemon events for `entity_id='I-00114'` (count=0).
- Builder pairing drift risk: **already mitigated**; both builders retain explicit sync guidance:
  - `orch/daemon/batch_manager.py:2127` — `Keep in sync with ``fix_cycle._build_fix_inner_command```
  - `orch/daemon/fix_cycle.py:2332` — `Mirrors ``batch_manager._build_initial_command`` — the two helpers must stay aligned`
- S13 test-determinism (`test_pi_narration_guard.py`): no flake signals; tests passed in all S13 runs (`run1`, `run3`, `run5`) while retries were caused by another test (`test_cli_spec_conformance`).
- pi runtime evolution coverage: classifier currently has no schema-version targeting note/TODO.

[1] Missing explicit pi JSONL schema-version guardrail in narration classifier
    Severity: MED   Class: design   Frequency: systemic
    Evidence:
      - `executor/pi_narration_guard.py:116` — `_extract_last_assistant_blocks(...)` parses ad-hoc keys (`type`, `role`, `content`) without version note.
      - `executor/pi_narration_guard.py:136` — `classify_last_assistant(...)` assumes block types `toolCall|text|thinking` with no compatibility comment.
    Recommendation: add a short comment/TODO beside classifier logic naming the currently assumed pi session schema and expected fallback behavior on schema drift.
    Target: `executor/pi_narration_guard.py`
    Pros: makes future pi-runtime upgrades safer and easier to audit.
    Cons: documentation-only; does not itself prevent drift.
    If we don't: future schema changes can degrade detection silently until incident symptoms reappear.
    Effort: S (~6-12 lines, 1 file)

[2] Expensive retry loop on long QV gates remains visible (non-narration failure source)
    Severity: MED   Class: platform   Frequency: recurring
    Evidence:
      - `ai-dev/logs/I-00114_S13_run1.log:3666` — `1 failed ... in 1205.07s`
      - `ai-dev/logs/I-00114_S13_run3.log:3667` — `1 failed ... in 1190.89s`
      - `ai-dev/logs/I-00114_S13_run5.log:3634` — pass after ~1188s.
    Recommendation: consider adding a fail-fast precheck for CLI-spec doc parity before full integration suite to avoid burning ~20m retries on known deterministic doc drift failures.
    Target: `Makefile` / integration gate command path (`make test-integration` composition)
    Pros: reduces retry budget burn and queue latency.
    Cons: adds another gate layer to maintain.
    If we don't: the same deterministic failure class can keep consuming full-suite reruns.
    Effort: M (~20-40 lines, 1-2 files)
