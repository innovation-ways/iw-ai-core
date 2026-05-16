# F-00084_S08_CodeReview_Final_prompt

**Work Item**: F-00084 — LLM-Assisted Merge Conflict Resolution (Phase 0 + Phase 1 dry-run)
**Step**: S08 (Final cross-agent review of S01..S07 — implementation + tests holistic)
**Agent**: code-review-final-impl

---

## Inputs

- All prior reports under `ai-dev/active/F-00084/reports/`:
  - S01_Pipeline_report.md
  - S02_CodeReview_report.md
  - S03_Backend_report.md
  - S04_CodeReview_report.md
  - S05_CodeReviewFinal_report.md (first cross-agent review)
  - S06_Tests_report.md
  - S07_CodeReview_report.md
- Design + functional docs
- Canonical reference: R-00076 §5 (full)

## Output

- `ai-dev/active/F-00084/reports/F-00084_S08_CodeReviewFinal_report.md`

## Scope — Final Cross-Agent Holistic Review

S05 reviewed S01–S04 (the implementation cross-cut). This step adds S06+S07 (tests) into the picture and looks at the WHOLE feature as one shippable artifact.

### Implementation × Tests round-trip

- [ ] Every public function in `orch/daemon/auto_merge.py` (S03) is exercised by at least one test (S06).
- [ ] Every event type emitted by S03's code is asserted on in at least one test.
- [ ] Every classification branch in `classify_conflicts` is covered.
- [ ] The fixture-based I-00085 and I-00086 reproductions (S06) actually trace the marker round-trip from bash (S01) through Python (S03) and assert on the resulting DaemonEvent rows.

### Acceptance criteria — final sign-off

For each AC1..AC6 in the design:
- [ ] A test exists.
- [ ] That test maps to the exact AC scenario (Given/When/Then).
- [ ] That test passes in the S06 report.
- [ ] The implementation actually produces the asserted behaviour (cross-check by re-reading the relevant S03 code section).

### Invariants — final sign-off

For each Invariant 1..8 in the design:
- [ ] A test exists.
- [ ] The implementation enforces the invariant by code structure, not just by tests (i.e., the safety property isn't "passes tests today" — it's "cannot be violated short of editing this specific guard").

### Holistic safety review

- [ ] Phase 0 is **provably** a no-op: walk the code path from `_merge_item` → marker parse → `attempt_resolution` → Phase-0 short-circuit. There is no way for an LLM token to be consumed.
- [ ] Phase 1 is **provably** non-destructive: walk the code path; there is no call to `git add`, `git rebase --continue`, or any worktree-mutating operation.
- [ ] Refuse-list is defence-in-depth: bash AND Python both classify the same forbidden file; both must fail for a forbidden file to slip through.
- [ ] Operator UX is **provably** preserved: walk the code path for every failure mode; for each one, confirm the existing `merge_conflict` event fires AND `BatchItem.status = merge_failed` is set AND `iw merge-queue retry-merge` still works.

### Documentation completeness

- [ ] Design doc accurately reflects what was built.
- [ ] Functional doc describes the phase=0 default behaviour correctly (no operator-visible change).
- [ ] R-00076 citations in code comments are accurate (section numbers match).
- [ ] No stale references to "Phase 2" verification gate behaviours in code or comments (Phase 2 is a follow-up CR).

### Cross-batch hygiene

- [ ] No file outside the design's "Impacted Paths" list was touched.
- [ ] No new dependency added to `pyproject.toml`.
- [ ] No new env var required.
- [ ] No new migration file.

### Production readiness for Phase 0

- [ ] Default config (`phase=0`) means this Feature is safe to merge with zero operator action.
- [ ] If an operator forgets the feature is deployed, behaviour is identical to today.
- [ ] If an operator advances to `phase=1`, the new behaviour is observational only; nothing breaks.
- [ ] If an operator MIS-configures `phase=2` or `phase=3`, the daemon refuses cleanly.

### Risk register (call out in report)

- [ ] Risk: oversized JSONB rows. Mitigated by Invariant 5 truncation. Note in report whether truncation cap is appropriate given typical conflict sizes.
- [ ] Risk: prompt leaking secrets. Mitigated by no-env-leakage test (S06). Confirm by spot-checking the prompt builder for any `os.environ` reads.
- [ ] Risk: race between SIGHUP reload and an in-flight merge. Acceptable for dry-run. Note in report.
- [ ] Risk: LLM hallucinating. Mitigated by Phase 1's never-apply invariant. Note in report.
- [ ] Risk: subprocess overhead for the LLM call. Note observed wall-clock from S06 integration tests.

## Severity Mapping

- **CRITICAL** — phase 0 not safe-by-default; refuse-list bypassable; operator UX changed on default config; secrets leak in prompt.
- **HIGH** — AC or Invariant uncovered; integration tests don't actually trace the bash→Python round-trip; documentation drift.
- **MEDIUM** — risk register incomplete; oversized-row truncation cap suboptimal; coverage < 90 %.
- **LOW** — style.

## Result Contract

Standard final-review JSON with `decision: approve|request_changes|escalate`. Include a one-paragraph summary of the feature's readiness for Phase 0 default-on merge and a bullet list of what an operator needs to do to advance to Phase 1.
