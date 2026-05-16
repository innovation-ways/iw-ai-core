# F-00085_S15_CodeReview_Final_prompt

**Work Item**: F-00085
**Step**: S15 (Final cross-agent review of S01..S14 — implementation + tests holistic)
**Agent**: code-review-final-impl

---

## Inputs

- All prior reports in `ai-dev/active/F-00085/reports/`
- F-00085 Feature Design + Functional doc
- Canonical reference: `ai-dev/active/AUTO_MERGE_RESOLUTION.md` §5b

## Output

- `ai-dev/active/F-00085/reports/F-00085_S15_CodeReviewFinal_report.md`

## Scope — Whole-Feature Holistic Review

S12 reviewed S01..S11 cross-cut (implementation). This step adds S13+S14 (tests) into the picture and looks at F-00085 as one shippable artifact.

### Implementation × Tests round-trip

- [ ] Every public function in `orch/auto_merge_aggregator.py` is exercised by ≥ 1 test.
- [ ] Every event type emitted by `orch/daemon/auto_merge_health.py` is asserted on.
- [ ] Every endpoint in `dashboard/routers/auto_merge_ui.py` has happy + error tests.
- [ ] Diff viewer's `git show` boundaries (success / non-zero / timeout) are all tested.
- [ ] Config resolution chain is traced end-to-end in `test_auto_merge_control_surface.py`.

### AC + Invariant final sign-off

For each AC1..AC14:
- [ ] A test exists.
- [ ] The test maps to the exact Given/When/Then.
- [ ] The test passes in S13's report.
- [ ] The implementation actually produces the asserted behaviour (cross-check via diff reading).

For each Invariant 1..9:
- [ ] Enforced by code structure where possible (e.g., Inv 1: no UPDATE/DELETE on daemon_events grep).
- [ ] Plus at least one test that would fail if the invariant were violated.

### Whole-feature safety review

- [ ] Phase 0 is provably safe-by-default: with empty `auto_merge_project_config` AND `phase=0` in TOML, nothing observable changes from F-00084 today.
- [ ] Phase 2/3 is provably unreachable: DB CHECK + API validation + UI dropdown all refuse; no daemon code path observes phase >= 2.
- [ ] Refuse-list intact: F-00084's refuse-list still wins; new per-project config can ONLY change phase + runtime, not the safety list.
- [ ] Operator UX preserved: existing `merge_conflict` event + `BatchItem.status = merge_failed` + `iw merge-queue retry-merge` all unchanged.
- [ ] Health probe never blocks merges (Inv 7).

### Documentation completeness

- [ ] F-00085 Feature Design accurately describes what was built.
- [ ] F-00085 Functional doc describes operator-visible behaviour accurately.
- [ ] `ai-dev/active/AUTO_MERGE_RESOLUTION.md` §5b rows 1.10..1.18 should be flagged for status update post-merge (note this in your report; the tracker update is operator/follow-up work).
- [ ] No CLAUDE.md updates required (assert this).
- [ ] No new agent invariants worth promoting yet.

### Cross-batch hygiene

- [ ] No file outside the design's Impacted Paths list was touched.
- [ ] No new dependency in `pyproject.toml`.
- [ ] No new env var required.
- [ ] One new migration file (S01).

### Production readiness

- [ ] Default deploy → no operator-visible change (no chip, no events, no probe).
- [ ] An operator can enable Phase 1 for one project via Settings without touching others.
- [ ] An operator can swap models per project via Settings.
- [ ] If something goes wrong, `phase=0` in Settings (or in TOML + SIGHUP) reverts to today's behaviour.
- [ ] The health probe respects the per-project runtime — choosing a cheap model = cheap probes.

### Risk register (carry into report)

- Subprocess `git show` failure modes — verify try/except is present in router code.
- Per-model pricing drift — note `MODEL_PRICING` is code-resident.
- Health probe idle cost — note that operators can raise `probe_interval_seconds` or set phase=0.
- Settings concurrency — note last-write-wins is acceptable for single-operator localhost.
- JSONB row inflation — Phase 1 dry-run still inlines proposed contents in events; F-00085 doesn't change this (carry-over from F-00084).

### Phase 2 readiness check

- [ ] Phase 2 design CR will need: verification gate (lint + type-check + targeted tests + assertion scanner), apply path (`git add` + `git rebase --continue`), `--resume-rebase` flag actual impl. None of these are blocked by F-00085's surface.
- [ ] Audit events from Phase 1 are now visible in the dashboard — operator can review accuracy without SQL (AC3 + AC4).

## Severity Mapping

- **CRITICAL** — Phase 0 default behaviour changes; Phase 2/3 selectable somewhere; verdict capture lost; daemon_events updated/deleted.
- **HIGH** — AC or Invariant uncovered; integration tests don't trace config resolution end-to-end; documentation drift.
- **MEDIUM** — risk register incomplete; coverage < 90 % on aggregator.
- **LOW** — style.

## Result Contract

Standard final-review JSON with `decision: approve|request_changes|escalate`. Include:

- A one-paragraph summary of readiness for default-on Phase 0 merge.
- A bullet list of what an operator needs to do post-merge to start using the page (visit page → see status → optionally flip Phase via Settings).
- A bullet list of what to look for in production (token cost, probe failure rate, verdict accuracy).
