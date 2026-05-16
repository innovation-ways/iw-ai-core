# F-00084_S05_CodeReview_Final_prompt

**Work Item**: F-00084 — LLM-Assisted Merge Conflict Resolution (Phase 0 + Phase 1 dry-run)
**Step**: S05 (Cross-agent final review of S01..S04)
**Agent**: code-review-final-impl

---

## Inputs

- `ai-dev/active/F-00084/F-00084_Feature_Design.md`
- `ai-dev/active/F-00084/F-00084_Functional.md`
- All previous reports:
  - `ai-dev/active/F-00084/reports/F-00084_S01_Pipeline_report.md`
  - `ai-dev/active/F-00084/reports/F-00084_S02_CodeReview_report.md`
  - `ai-dev/active/F-00084/reports/F-00084_S03_Backend_report.md`
  - `ai-dev/active/F-00084/reports/F-00084_S04_CodeReview_report.md`
- Aggregated diff of all files touched in S01 + S03
- Canonical reference: `docs/research/R-00076-llm-automated-merge-resolution.md` §5 (the whole thing)

## Output

- `ai-dev/active/F-00084/reports/F-00084_S05_CodeReviewFinal_report.md`

## Scope — Cross-Agent Concerns

This step focuses on integration between the bash and Python sides. Per-agent issues should have been caught in S02/S04 — flag them here only as escalations.

### Marker round-trip

- [ ] The exact `AUTO_RESOLVE_REQUESTED=<json>` string format emitted by `worktree_commit.sh` (S01) is consumed by `auto_merge.parse_auto_resolve_marker` (S03). Trace one concrete example end-to-end.
- [ ] JSON schema matches on both sides: `eligible_files`, `branch`, `main_sha` keys.
- [ ] Same for `AUTO_RESOLVE_SKIPPED=<json>` with `reason`, `eligible_files`, `refuse_files`.
- [ ] If `jq` is absent and bash uses the awk fallback, the resulting JSON is still valid for Python's `json.loads` (test the malformed-input branch).

### Phase 0 default behaviour

- [ ] In a fresh repo with **default** `auto_merge.toml` (phase=0), trigger a synthetic conflict and confirm:
      1. `AUTO_RESOLVE_REQUESTED` IS emitted (bash classification ran).
      2. `auto_merge.attempt_resolution()` short-circuits via Phase 0 path.
      3. ZERO subprocess invocations of `step_executor.sh`.
      4. `merge_auto_resolution_skipped` event fires with `reason="phase_0"`.
      5. Existing `merge_conflict` + `merge_failed` flow is byte-identical to today's output (modulo timestamps).

### Refuse-list defence-in-depth

- [ ] A conflict in `orch/db/migrations/versions/d1e2f3*.py` is refused by **both** the bash side (S01) AND the Python side (S03 classify_conflicts).
- [ ] Even if bash's coarse match misses a path (hypothetical: a binary file like `.png` that bash forgets to suffix-match), Python's `classify_conflicts` catches it.
- [ ] The intersection-of-two-layers gives us defence-in-depth: a bug in either side alone cannot allow a forbidden file through.

### Decision-tree consistency

- [ ] Bash and Python classification agree on the I-00085-shape conflict (all 3 files are in `tests/**`, eligible).
- [ ] Bash and Python classification agree on the migration-conflict case (refuse).
- [ ] When they disagree (Python is stricter), Python wins and the Python-side `merge_auto_resolution_skipped` event records the more-specific reason.

### Operator UX preservation

- [ ] For EVERY failure path (refuse, abstain, error, phase 0), the operator sees:
      1. The same `merge_conflict` event (with the F-00076 `CONFLICT_FILES` metadata).
      2. The same `BatchItem.status = merge_failed`.
      3. The same `iw merge-queue retry-merge <ID>` command still works.
- [ ] No new operator action is required by this Feature; the new audit events are observational only.

### Configuration surface

- [ ] `auto_merge.toml` is the SOLE configuration surface for this feature (no env vars, no DB column, no CLI flag).
- [ ] Hot-reload via SIGHUP works; documented in the design doc's AC6.
- [ ] Reserved phases (2, 3) are refused with a clear error.

### Documentation cross-check

- [ ] R-00076 is cited at every relevant location in code comments (worktree_commit.sh new block, auto_merge.py module docstring).
- [ ] CLAUDE.md does NOT need updating in this Feature (no new agent invariants worth promoting yet; that's a Phase-2 task).
- [ ] The Functional doc accurately describes operator-visible behaviour at phase=0 vs phase=1.

### Testability handoff to S06

- [ ] All boundaries listed in the design's Boundary Behavior table are observable from the Python side (i.e., they emit events whose metadata can be asserted on).
- [ ] The fixture pattern (`tmp_path` bare repo + clone + simulated conflict) is feasible — call out any missing test helpers that S06 will need to introduce.

### Security

- [ ] No prompt sent to the LLM includes secrets (no env vars, no `.env` file content, no credentials from `IW_CORE_*` variables).
- [ ] No proposed resolution from the LLM is **applied** in this Feature (Invariant 3) — even if the LLM tried to inject a malicious patch, it would never reach disk.
- [ ] The refuse-list is exhaustive enough that even if Phase 2 ships, the LLM would never be allowed to edit security-sensitive files.

## Severity Mapping

- **CRITICAL** — bash and Python disagree on a refuse-list path; Phase 0 still calls the LLM; existing merge_conflict event suppressed.
- **HIGH** — marker round-trip broken on awk fallback; phase ladder enforcement absent; hot reload not wired.
- **MEDIUM** — documentation cross-references missing; minor classification differences between bash and Python.
- **LOW** — style.

## Result Contract

Standard final-review JSON with `decision: approve|request_changes|escalate`. Include a 3-line summary of the integration health (marker round-trip, phase 0 short-circuit, refuse-list defence-in-depth, operator UX preservation).
