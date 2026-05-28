# I-00116 Self-Assessment Report

**Work Item**: I-00116 — Daemon marks code-review step as PID-dead when reviewer exits without `iw step-done`; downstream review chain loops unboundedly
**Step**: S17 (SelfAssess)
**Analyzer**: iw-item-analyze skill
**Scope**: Process / workflow analysis only — no review of generated code

---

## Bottom Line

The most actionable improvement is to make the S04 and S09 code-review agents read the **design doc first before diagnosing** — both steps wasted a round-trip because the initial diagnostic hypothesis was either misdirected (S04 blamed "scope violation" when it was an extant worktree artifact) or under-specified, causing unnecessary fix cycles. Adding a "read design doc → verify findings → then edit" protocol to code-review prompts would eliminate most fix-cycle iterations on this item type.

Steps analyzed: 9 implementation/code-review steps + 7 QV gates   Total retries: 4   Total fix-cycles: 1   DB signal: yes

---

## Per-Step Analysis

---

### S02 — CodeReview (Backend) — 2 runs

```
step: S02  agent: code-review-impl  status: completed
runs: 2    fix_cycles: 0
findings:
  - { id: S02-F1, severity: LOW, class: agent,
      evidence: "ai-dev/logs/I-00116_S02_run1.log:1 — 'S02 complete...'",
      note: "First run reviewed S01 cleanly and passed all 14 items.
             Second run appears to be a re-run of the same review after
             S02 step-done was called (run1 log shows final verdict;
             run2 log shows same verdict — possibly a daemon re-poll or
             duplicate launch). Both runs concluded pass." }
```

**Signal**: Single transient duplication. Total agent time wasted: <1 min.

---

### S04 — CodeReview (Backend) — 2 runs, fix_cycles: 0, but first run verdict=fail

```
step: S04  agent: code-review-impl  status: completed
runs: 2    fix_cycles: 0 (daemon did not re-open; S04 resolved on second run)
findings:
  - { id: S04-F1, severity: HIGH, class: agent,
      evidence: "ai-dev/logs/I-00116_S04_run1.log:7 — 'Verdict: fail — Three issues found (1 critical, 1 major, 1 minor): F1 CRITICAL step_monitor.py is modified in this worktree but S03 was only allowed to touch fix_cycle.py and batch_manager.py. The scope boundary is violated'",
      note: "F1 was a misread. S03 did NOT touch step_monitor.py; S01 did.
             The first-run reviewer was looking at the worktree diff,
             which contains S01+S03 contributions. S04's verdict=fail
             was caused by the reviewer not discounting S01's committed
             (but unmerged) changes from S03's diff." }
  - { id: S04-F2, severity: MED, class: agent,
      evidence: "ai-dev/logs/I-00116_S04_run1.log:8 — 'F2 Major: _transition_item_to_failed_for_loop uses a plain db.query(WorkItem).first() without SELECT FOR UPDATE'",
      note: "F2 was also misread. The S04 report (run1) itself lists
             'Idempotent guard (if status == failed: return)' as a
             passing check item, and the second run acknowledges the
             session-atomic pattern as acceptable. S04-fail verdict was
             based on a checklist that was later re-read as pass." }
  - { id: S04-SLF001, severity: MED, class: platform,
      evidence: "ai-dev/logs/I-00116_S04_run1.log:15 — 'make lint fails with 2 SLF001 private-member-access violations (fc._count_review_relaunches, fc._transition_item_to_failed_for_loop)'",
      note: "S03's cap-check in batch_manager.py called fix_cycle
             private helpers (`_get_max_review_relaunches`,
             `_transition_item_to_failed_for_loop`) without noqa
             annotations. Pre-existing lint violation existed through
             S03→S04→S05→S06 before S09 fix cycle resolved it.
             Platform: the project uses this pattern elsewhere
             (scope_overlap._matches, fc._latest_failure_reason) but
             does not annotate the existing uses consistently —
             no project-level rule exists to require or forbid the
             annotation, and there is no pre-commit hook to catch it." }
```

**Signal**: S04 wasted one run due to a misread of the worktree diff context. The second run correctly achieved pass after re-reading the code. Agent thrash: MED.

---

### S06 — CodeReview (Prompt) — 2 runs

```
step: S06  agent: code-review-impl  status: completed
runs: 2    fix_cycles: 0
findings:
  - { id: S06-F1, severity: MED, class: agent,
      evidence: "ai-dev/logs/I-00116_S06_run1.log:10 — 'CRITICAL Finding: Three daemon files (batch_manager.py, fix_cycle.py, step_monitor.py) are also modified in this worktree. They are out of scope for S05/S06'",
      note: "Same misread as S04-F1 — run1 reviewer again flagged the
             worktree's mixed diff as a scope violation, despite S05's
             report clearly stating only the four prompt/SKILL files
             were changed. Run2 reviewer recognized this and passed.
             Agent thrash: LOW." }
```

**Signal**: Repeated misread pattern from S04 carried into S06. Not promoted (one-off), but the same root cause as S04-F1.

---

### S07 — Tests — 2 runs (both empty logs)

```
step: S07  agent: tests-impl  status: completed
runs: 2    fix_cycles: 0
findings:
  - { id: S07-empty, severity: LOW, class: platform,
      evidence: "ai-dev/logs/I-00116_S07_run1.log — empty (0 bytes);
                 ai-dev/logs/I-00116_S07_run2.log — empty (0 bytes)",
      note: "Both S07 run logs are empty (0 bytes). This likely means
             the tests agent ran and exited via tool-use only (no
             stdout to capture). The S08 review (which passes) says
             S07 created all three test files and 10/10 targeted tests
             passed. The empty logs are a logging/data-collection gap —
             not an error, but evidence that the log aggregation pipeline
             does not capture tool-use-only executions." }
```

**Signal**: Logs missing. Not an execution failure (tests passed as confirmed by S08), but `ai-dev/logs/` is an unreliable signal when agents produce no stdout. Coverage: partial.

---

### S09 — CodeReview Final — run1 empty, run3 (fix cycle + final), fix1

```
step: S09  agent: code-review-final-impl  status: completed
runs: 3    fix_cycles: 1
findings:
  - { id: S09-FIX1, severity: MED, class: agent,
      evidence: "ai-dev/logs/I-00116_S09_fix1.log:1 — 'Diagnostic: Process exited without reporting completion (PID dead)'",
      note: "The fix cycle diagnostic ('PID dead') was a misdiagnosis.
             The actual fault was lint failures in batch_manager.py
             (SLF001) introduced by S03's cap implementation. The fix
             cycle correctly resolved the lint issues (added noqa
             annotations + format fix) rather than 'PID dead', but only
             because the agent fixed the right things for the wrong
             reason. Agent self-corrected but the diagnostic was noise." }
  - { id: S09-doc, severity: MED, class: design,
      evidence: "ai-dev/logs/I-00116_S09_run3.log:19 — 'F9 (HIGH): IW_CORE_MAX_REVIEW_RELAUNCHES_PER_ITEM missing from CLAUDE.md Configuration; F10 (HIGH): Two DaemonEvent types undocumented in daemon design doc'",
      note: "Two post-merge follow-up items surfaced by the final review.
             These are not blocking (item resolved with pass verdict),
             but the design documents need updating as operator tasks.
             Not a fix-cycle finding per se — the item was still closed
             pass — but worth tracking." }
```

**Signal**: One fix cycle. Diagnostic was noisy but fix was correct. Two doc follow-ups filed.

---

### QV Gates (S10–S16) — all green, no retries

```
step: S10-S16  agent: qv-gate  status: all completed on first run
Total retries: 0  fix_cycles: 0
findings: []
```

**Signal**: Clean. No issues.

---

## Promoted Findings

Below are findings that were either severity=HIGH or appeared in ≥2 steps. Nine internal findings were evaluated; four cleared the bar.

---

**[1] Code-review agents misattribute worktree-diff pollution to the current step (S04/S06 pattern)**
Severity: HIGH   Class: agent   Frequency: recurring
Evidence:
  - ai-dev/logs/I-00116_S04_run1.log:7 — "Verdict: fail — F1 CRITICAL step_monitor.py is modified in this worktree but S03 was only allowed to touch..."
  - ai-dev/logs/I-00116_S06_run1.log:10 — "CRITICAL Finding: Three daemon files...are also modified in this worktree. They are out of scope for S05/S06"  (also seen in S04)
Recommendation: Add a directive to the code-review-impl prompt files instructing reviewers to distinguish "currently scoped step's recent diff" from "active-worktree uncommitted changes from prior steps". Specifically: before flagging a scope-violation finding, the reviewer must confirm the change exists in `git log --oneline -1` for that step AND the git diff for that step specifically. A simpler alternative: explicitly name which prior steps' changes are pre-existing in the worktree so reviewers know to discount them.
Target: agents/claude/code-review-impl.md, agents/opencode/code-review-impl.md, agents/pi/code-review-impl.md (the three prompt variants updated by S05)
Pros: Eliminates ~1 wasted run per affected code-review step; prevents spurious fail verdicts on multi-step items.
Cons: Requires regenerating three files; adds a pre-check step to every code-review agent's diagnostic flow.
If we don't: Fix-cycle waste continues on every multi-step item where multiple backend steps modify overlapping files.
Effort: S (~5 lines per file, 3 files)

---

**[2] Fix-cycle diagnostic hypothesis is used as truth rather than verified against the design doc**
Severity: HIGH   Class: platform   Frequency: systemic
Evidence:
  - ai-dev/active/I-00116/fix-cycles/I-00116_S09_FIX_cycle1_prompt.md:12 — "Diagnostic Hypothesis — Findings to Address: Process exited without reporting completion (PID dead)"
  - ai-dev/logs/I-00116_S09_fix1.log:7 — "Diagnostic: Process exited without reporting completion (PID dead)"
  - ai-dev/logs/I-00116_S09_fix1.log:11 — "Changes applied: Added # noqa: SLF001 comments..."  (actual fix was lint failures, not PID recovery)
Recommendation: Update the fix-cycle template (`templates/design/FixCycle_*.md` or the fix-cycle prompt generator in `iw-workflow` skill) to add a mandatory "verify diagnostic" step before editing: the agent must check whether the reported finding is actually present before applying a fix. The existing template ("verify against design doc") is not being followed — the diagnostic was accepted as-ground-truth.
Target: templates/design/FixCycle_Template.md  (or the skill that generates fix-cycle prompts)
Pros: Fixes the root cause of noisy diagnostics wasting cycles.
Cons: Requires template update; may slow fix-cycle agents slightly.
If we don't: Fix cycles continue to apply correct fixes for wrong reasons, or (worse) apply wrong fixes when the diagnostic is genuinely wrong.
Effort: M (~20 lines in template, 1 doc)

---

**[3] Pre-existing SLF001 lint violations introduced by S03's cap implementation bloomed through S03→S04→S05→S06 before being caught by S09 (4 steps)**
Severity: MED   Class: environment   Frequency: systemic
Evidence:
  - ai-dev/logs/I-00116_S04_run1.log:15 — "make lint fails with 2 SLF001 private-member-access violations (fc._count_review_relaunches, fc._transition_item_to_failed_for_loop)"
  - ai-dev/logs/I-00116_S05_run1.log:30 — "make lint: pass...pre-existing SLF001 warnings in batch_manager.py unrelated to S05"
  - ai-dev/logs/I-00116_S06_run2.log:20 — "make lint has a pre-existing SLF001 warning from S03 in batch_manager.py"
  - ai-dev/logs/I-00116_S09_fix1.log:11 — "Added # noqa: SLF001 comments to the two private-member accesses"
Recommendation: Add a targeted `make lint` check to the Backend step prompt's Post-Edit Gate section, specifically checking the two files named `fix_cycle.py` and `batch_manager.py` for the new private-helper calls. More generally: require the post-edit `make lint` to be run against ALL files touched since the last step start, not just the target files. Alternatively: add a pre-commit hook that flags `SLF001` at commit time so violations cannot reach review stages.
Target: orch/daemon/fix_cycle.py (the implementation responsible for defining `_get_max_review_relaunches`, `_count_review_relaunches`, `_transition_item_to_failed_for_loop` — these should be public, not private, OR the calling pattern should be annotated with noqa at the call site: `# noqa: SLF001` added immediately to `batch_manager.py` calls)
Pros: Prevents lint waste through review chain; aligns with existing pattern in `scope_overlap._matches` / `fc._latest_failure_reason`.
Cons: Requires operator to decide: public-helper convention vs. noqa-annotation convention and enforce globally.
If we don't: Any future Backend step that adds cross-module private helper calls will trigger the same 4-step lint propagation.
Effort: M (~2 items: (1) decide and document the project's private-helper-call convention; (2) add targeted lint check to Backend prompt Post-Edit Gate)

---

**[4] Test-agent log capture gap (S07): 0-byte run logs for successful executions**
Severity: MED   Class: platform   Frequency: systemic
Evidence:
  - ai-dev/logs/I-00116_S07_run1.log — 0 bytes (empty)
  - ai-dev/logs/I-00116_S07_run2.log — 0 bytes (empty)
Note: S07 executed successfully (created all 3 test files, targeted pytest passed 10/10), but no log was written to ai-dev/logs/. This makes post-facto analysis reliant on secondary evidence (S08's review report).
Recommendation: Investigate why agents that use certain tools (e.g., running pytest, creating files) produce no stdout-to-log capture. Possible causes: (a) stdout is not being piped into the current executor's log; (b) the agent used tool-use mode with no shell stdout; (c) the log file for this run was opened but not written. Ensure the executor writes a summary log even for tool-use-only runs (e.g., post-step hook that writes the result contract to disk before uploading).
Target: executor/ (the shell scripts that capture agent output and write logs — could also be `executor/worktree_commit.sh` or the OpenCode agent harness config)
Pros: Enables full post-hoc analysis for all tool-use-only agent executions; closes a blind spot for the iw-item-analyze skill.
Cons: Requires executor/infrastructure changes; may have false-positive summaries if not carefully scoped.
If we don't: The self-assessment skill will have incomplete log coverage for any steps where the agent bypasses shell stdout.
Effort: L (~50–100 lines, 1 executor script change + test)

---

## Summary

| Finding | Severity | Class | Frequency | Effort |
|---------|----------|-------|----------|--------|
| #1: Worktree-diff misattribution in code review | HIGH | agent | recurring | S |
| #2: Fix-cycle diagnostic not verified against design doc | HIGH | platform | systemic | M |
| #3: SLF001 lint violation bloomed through 4 review steps | MED | environment | systemic | M |
| #4: Test-agent 0-byte logs for successful executions | MED | platform | systemic | L |

Total fix-cycle iterations that could have been avoided: 1 (S09). Total redundant review runs: 3 (S04-run2, S06-run2, S09-fix). Total QV failures: 0.

The item itself is fully resolved with all acceptance criteria passed. The findings above are process/cross-item improvements.

---

*Analysis produced by `iw-item-analyze` skill. Log coverage: S01, S02 (2 runs), S03, S04 (2 runs), S05, S06 (2 runs), S07 (empty logs noted), S08, S09 (fix1 + run3; run1 was empty), S10-S14 (all full logs fully read). No tarball archive available. DB telemetry: item-status JSON read only — no direct DB queries.*
