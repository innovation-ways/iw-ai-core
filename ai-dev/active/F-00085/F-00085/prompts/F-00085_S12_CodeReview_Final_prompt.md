# F-00085_S12_CodeReview_Final_prompt

**Work Item**: F-00085
**Step**: S12 (Cross-agent final review of S01..S11 — implementation cross-cut)
**Agent**: code-review-final-impl

---

## Inputs

- All prior reports under `ai-dev/active/F-00085/reports/`:
  - S01_Database_report.md
  - S02_CodeReview_report.md (S01 review)
  - S04_Pipeline_report.md
  - S05_CodeReview_report.md (S04 review)
  - S06_Backend_report.md
  - S07_CodeReview_report.md (S06 review)
  - S08_API_report.md
  - S09_CodeReview_report.md (S08 review)
  - S10_Frontend_report.md
  - S11_CodeReview_report.md (S10 review)
- Aggregated diff of all files touched in S01 + S04 + S06 + S08 + S10
- F-00085 Feature Design + Functional doc
- Canonical reference: AUTO_MERGE_RESOLUTION.md §5b

## Output

- `ai-dev/active/F-00085/reports/F-00085_S12_CodeReviewFinal_report.md`

## Scope — Cross-Agent Concerns

Per-agent issues should have been caught in S02/S05/S07/S09/S11. This step is the integration check across DB → Pipeline → Backend → API → Frontend.

### End-to-end config resolution

- [ ] Walk one concrete example: operator clicks Settings, picks phase=1 + runtime_option_id=4, clicks Save.
  - POST `/<project>/auto-merge/config` → API validates, upserts `auto_merge_project_config`, emits `auto_merge_config_updated` event.
  - Next merge conflict → `merge_queue.py` reads TOML → calls `resolve_project_config` → resolves per-project DB row → invokes LLM with claude/claude-sonnet-4-6.
  - Resulting `merge_auto_resolved` event has `event_metadata.llm_calls[*].model = "claude-sonnet-4-6"`.
  - Aggregator's status snapshot returns `source = "per_project_db"` and `cli_tool/model` matching the DB row.
  - Chip + Settings panel reflect the new config on next page render.

### End-to-end audit trail

- [ ] Operator's config change is traceable: `auto_merge_config_updated` event has `old` and `new` in metadata; visible in the events table.
- [ ] Operator's verdict is traceable: `merge_auto_verdicts` row has `verdicted_by` and `verdicted_at`; visible in the modal + inline widget.
- [ ] Health probe stream is traceable: each probe is an `auto_merge_health_probe` event with `runtime_reachable`, `probe_duration_ms`, `error`.

### F-00084 backward compatibility (Inv 3)

- [ ] With `auto_merge_project_config` table empty AND no Settings UI used, `resolve_project_config` returns the SAME values as F-00084's direct-TOML read.
- [ ] Phase-0 default behaviour (no events, no chip, no probe) is preserved when nobody has flipped Settings.
- [ ] `merge_queue.py`'s F-00084 marker-parsing code is unchanged in shape — only the config lookup is rerouted through the aggregator.

### Phase 2/3 reservation (Inv 5)

- [ ] DB CHECK constraint refuses phase IN (2, 3).
- [ ] API POST refuses phase=2 or 3 with 400.
- [ ] Settings dropdown UI offers ONLY 0 and 1.
- [ ] No daemon code path observes phase >= 2.

### Append-only daemon_events (Inv 1)

- [ ] grep the diff for `update(DaemonEvent)` and `delete(DaemonEvent)` — must be empty.
- [ ] Verdicts and config changes live in their own tables; daemon_events only receives `session.add(...)`.

### Health probe non-blocking (Inv 7)

- [ ] Daemon main loop calls `maybe_run_probe` AFTER merge-queue and batch processing.
- [ ] try/except wraps the call — one project's failure does not block others.
- [ ] No probe runs when phase=0 — zero token cost for plumbing-only projects.

### Disabled-runtime defence in depth (AC14)

- [ ] Settings template `<option>` list built from `enabled=True` rows ONLY.
- [ ] API POST re-validates the chosen id is `enabled=True`.
- [ ] If a row is disabled between page render and POST, API rejects with 400.
- [ ] `resolve_project_config` ALSO handles the case where the per-project row points at a now-disabled row — falls through to TOML + emits `auto_merge_config_invalid`.

### Diff viewer safety (Boundary "File no longer on main")

- [ ] `git show main:<file>` subprocess timeout enforced.
- [ ] Non-zero returncode handled gracefully → placeholder.
- [ ] Exception path → placeholder, never 500.

### Documentation cross-checks

- [ ] R-00076 / AUTO_MERGE_RESOLUTION.md cited at relevant code locations (aggregator module docstring, settings template comment).
- [ ] `executor/auto_merge.toml` [health] section comments are operator-facing and accurate.
- [ ] `dashboard/CLAUDE.md` and `orch/CLAUDE.md` need no updates from this Feature (assert this).
- [ ] No stale references to "Tier 2" / "Tier 3" anywhere in code or templates — that's tracker vocabulary, not user-facing.

### Production readiness for shipping with Phase 0 default

- [ ] If the operator does nothing post-merge, behaviour is identical to today (chip hidden, no probe, no events, audit log untouched).
- [ ] If the operator flips Settings for ONE project to phase=1, only that project starts emitting events.
- [ ] Disabling Settings for one project while phase=1 remains in TOML correctly turns off behaviour for that project only.

### Test coverage gap analysis (heads-up for S13)

- [ ] Note any AC / Invariant / Boundary row that the S01..S11 reports do NOT yet have a unit/integration test for. S13 must close those gaps.

## Severity Mapping

- **CRITICAL** — chip visible when phase=0; phase=2 acceptable somewhere; daemon_events updated/deleted; backward compat broken (empty DB tables change F-00084 behaviour); refuse-list bypass.
- **HIGH** — config-resolution chain has a hole (e.g., DB row partially populated leads to wrong source attribution); audit event not emitted on settings change; probe blocks merge queue.
- **MEDIUM** — documentation cross-references missing; minor surface inconsistency between bash and Python or between API and UI; test coverage gap for a Boundary row.
- **LOW** — style.

## Result Contract

Standard final-review JSON with `decision: approve|request_changes|escalate`. Include a 5-line summary: integration health (config resolution end-to-end, audit trail end-to-end, append-only intact, Phase 2/3 reserved, defence-in-depth on disabled runtime).
