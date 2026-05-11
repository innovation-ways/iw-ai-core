### Item Analysis: I-00081

**Bottom line:** Fix the design-doc generators (or `iw step-done`) so step-report filenames match what downstream prompts reference — every multi-step item currently burns 1–4 wasted tool calls per dependent step because prompts ask for `<ID>_S<NN>_<agent-slug>_report.md` while the lifecycle writes `<ID>_S<NN>_<Label>_report.md`.

Steps analyzed: 14   Steps with retries: 0   Total fix-cycles: 0   DB signal: yes

Workflow ran cleanly end-to-end — no fix-cycles, every step exactly one run, all QV gates green (lint, format, typecheck, 2748 unit tests, 2262 integration tests), browser verification PASS on V0/V1/V2. The 3 "test failures" inside S01 are the **expected TDD RED phase** required by CR-00045 (test asserts behavior the next backend edit will satisfy) and are not findings. The findings below are all about *how the agents spent their turns*, not about the code I-00081 shipped.

---

[1] Per-step prompt template substitutes `{Agent}` with the OpenCode slug; lifecycle writes reports using the friendly label — every downstream step hits "File not found" on first read
    Severity: MED   Class: prompt   Frequency: systemic
    Evidence:
      - ai-dev/logs/I-00081_S02_run1.log:9 — "Error: File not found: ...I-00081_S01_backend-impl_report.md"  (real file is ...I-00081_S01_Backend_report.md, line :12 shows the recovery Read)
      - ai-dev/logs/I-00081_S03_run1.log:9 — "Error: File not found: ...I-00081_S01_backend-impl_report.md"  (S03 was told to "read this first" for S01's exact context-var names — losing 1 turn)
      - ai-dev/logs/I-00081_S04_run1.log:9 and :11 — "File not found: ...I-00081_S01_backend-impl_report.md" + "File not found: ...I-00081_S03_frontend-impl_report.md"  (S04 needs both; loses 2 turns)
      - ai-dev/active/I-00081/prompts/I-00081_S02_CodeReview_prompt.md:23 — prompt-as-written asks for the `backend-impl` filename
    Recommendation: Pick ONE convention and apply it. Smallest change: design-doc generators (`iw-new-incident`, `iw-new-feature`, `iw-new-cr`) substitute `{Agent}` in `templates/design/Implementation_Prompt_Template.md` with the step *label* (`Backend`, `Frontend`, `Tests`) — the same string `iw step-done` uses when writing reports. Alternative: change `orch/cli/step_commands.py` (the report-writer) to use the agent slug. Either way, document the placeholder semantics next to lines 76–80 of the implementation prompt template so the convention is loud.
    Target: templates/design/Implementation_Prompt_Template.md, skills/iw-new-incident/SKILL.md, skills/iw-new-feature/SKILL.md, skills/iw-new-cr/SKILL.md
    Pros: Removes a recurring per-item wart that every multi-step Issue/Feature/CR hits; trivial code change in the design generator.
    Cons: Must be applied consistently — if S01's prompt uses one convention and S02's uses the other, the same gap returns.
    If we don't: Every multi-step item continues to lose 1–4 agent turns to "File not found" on the predicted upstream-report paths. Aggregated across the active queue this is non-trivial wall-clock cost.
    Effort: S (~15 lines, 4 files)

[2] OpenCode tool wrappers reject string-typed numeric args and JSON-string arrays — agent emits, retries, recovers (todowrite, bash.timeout, read.offset)
    Severity: MED   Class: platform   Frequency: recurring
    Evidence:
      - ai-dev/logs/I-00081_S01_run1.log:20 — "todowrite … Expected array, got '[{\"content\": …}]' Please rewrite the input so it satisfies the expected schema."
      - ai-dev/logs/I-00081_S01_run1.log:24,28 — same `todowrite` failure, two more retries with same JSON-string body (3 wasted turns in S01 alone)
      - ai-dev/logs/I-00081_S01_run1.log:38 — "bash … Expected number | undefined, got '60000'"
      - ai-dev/logs/I-00081_S01_run1.log:126 — "read … Expected number | undefined, got '1'"
      - ai-dev/logs/I-00081_S02_run1.log:31,35 — `bash` retried with `'120000'` then `'180000'`
      - ai-dev/logs/I-00081_S03_run1.log:158,162 — `read` rejected twice with offset/limit `'44'`
      - ai-dev/logs/I-00081_S04_run1.log:31 — same `bash` string-timeout pattern
      - Total: 11 schema rejections across S01–S04
    Recommendation: Add input coercion in the OpenCode tool wrappers — coerce numeric strings to numbers for `bash.timeout` and `read.offset`/`limit`, parse JSON-array strings into arrays for `todowrite.todos`. A `z.coerce.number()` / `z.union([z.array(...), z.string().transform(JSON.parse)])` preprocess hook is enough. Cheaper fallback: update the agent system prompt to call out "do not quote numeric arguments to bash.timeout / read.offset" in the tool-use guidance.
    Target: OpenCode tool-shim layer (likely under `executor/` or wherever the daemon launches the OpenCode CLI). Investigate `executor/launch_step.sh` and adjacent for the shim entrypoint.
    Pros: One change kills all 11 retries; benefits every step in every item.
    Cons: If the shim is owned upstream by OpenCode itself, the fix may need to live in agent prompt guidance instead.
    If we don't: 11 wasted turns per long item continues; each ~3–8 s of agent latency plus the cognitive cost of writing the corrected call.
    Effort: S (~20 lines if it's our shim; if upstream, S in our system prompt)

[3] E2E pg_dump is missing an iw-doc-generator-form `diagram-architecture` ProjectDoc — every browser-verification step that exercises this widget must hand-seed a fixture first
    Severity: MED   Class: environment   Frequency: systemic
    Evidence:
      - ai-dev/active/I-00081/reports/I-00081_S13_BrowserVerification_Report.md:12 — "No `diagram-architecture` doc existed in the seeded E2E DB (the pg_dump predates DOC-00057)."
      - ai-dev/active/I-00081/reports/I-00081_S13_QvBrowser_report.md:17 — "…which was absent from the pg_dump-seeded E2E DB."
      - ai-dev/active/I-00081/e2e_fixtures/001_md_diagram_architecture.py (file created mid-step, not committed at design time)
    Recommendation: Refresh the E2E pg_dump (`ai-dev/iw-config/...` or wherever the seed lives) so the `iw-ai-core:diagram-architecture` ProjectDoc exists in the **Markdown-with-fences** form the iw-doc-generator skill produces today. Either snapshot a fresh dump after DOC-00057 lands, OR promote the I-00081 fixture (`ai-dev/active/I-00081/e2e_fixtures/001_md_diagram_architecture.py`) into a reusable e2e seed-fixtures library indexed by feature.
    Target: the e2e pg_dump under `ai-dev/iw-config/` + a small fixture library under `tests/e2e_fixtures/`
    Pros: Future browser verifications of Code-page Architecture-Diagram features don't need ad-hoc fixtures; the seed reflects current production shape.
    Cons: Dump refresh has cost (must rerun across multiple projects); a fixture library adds a tiny maintenance burden.
    If we don't: Every future browser verification touching this widget repeats the same "hand-seed a fixture, re-seed via docker compose exec" dance — and the design doc has to anticipate it explicitly each time.
    Effort: M (~50 lines + a dump refresh procedure documented in `docs/IW_AI_Core_DB_Setup.md`)

[4] `iw-item-analyze` skill and master prompt templates still reference `ai-dev/work/<ID>/` while active items live at `ai-dev/active/<ID>/`
    Severity: LOW   Class: convention   Frequency: systemic
    Evidence:
      - skills/iw-item-analyze/SKILL.md:51,157–158,241 — output and inventory paths use `ai-dev/work/<ID>/`
      - templates/design/SelfAssess_Prompt_Template.md:72,76–77,113–114 — same drift
      - templates/design/Implementation_Prompt_Template.md:76,80 — same drift
      - ai-dev/work/CR-00040/reports/CR-00040_self_assess_findings.json:25 — prior finding flagging this exact drift (not fixed)
    Recommendation: Replace `ai-dev/work/<ID>/` with `ai-dev/active/<ID>/` across the master templates and the `iw-item-analyze` skill. The per-item I-00081 prompts already use `ai-dev/active/` correctly — the drift is master-side. Already filed by CR-00040 and CR-00041 self-assess but never burned down. The cost on I-00081 was zero (per-item prompt overrode the skill), but the rot will surface the next time anyone runs the skill against a path not overridden by a per-item prompt.
    Target: skills/iw-item-analyze/SKILL.md, templates/design/SelfAssess_Prompt_Template.md, templates/design/Implementation_Prompt_Template.md, templates/design/CodeReview_Prompt_Template.md, templates/design/CodeReview_Final_Prompt_Template.md
    Pros: Eliminates a recurring known-issue that's already been filed twice.
    Cons: None material — `sed -i 's|ai-dev/work/|ai-dev/active/|g'` covers most of it.
    If we don't: A third self-assess filing of the same finding next quarter.
    Effort: S (~10 edits, 5 files)

---

**Observations that did NOT clear the bar (one-offs, no agent thrash):**

- `ai-dev/active/I-00081/I-00081/` — a duplicate nested copy of the design doc, prompts, and evidence exists (identical to the parent dir). Likely a `iw-new-incident` skill quirk where the design landed under both `ai-dev/active/{ID}/` and `ai-dev/active/{ID}/{ID}/`. No log shows it caused thrash; flagging for cleanup curiosity.
- 3 bash "unexpected EOF while looking for matching `` ` ``" errors in S01 (lines 765, 894, 948) from agent writing multi-line Python `python -c "..."` inline scripts with unclosed backticks during root-cause exploration. Singletons within one step; no recovery cost.
