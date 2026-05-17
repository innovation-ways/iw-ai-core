# IW AI Core — Auto-Merge Resolution Plan

> **Status**: living plan — v1.6 (2026-05-17)
> **Owner**: sergio
> **Source research**: [`docs/research/R-00076-llm-automated-merge-resolution.md`](../../docs/research/R-00076-llm-automated-merge-resolution.md) (R-00076)
> **Tracking tickets**: F-00084 (Phase 0 + Phase 1 plumbing/dry-run) · F-00085 (Sub-phase 1b observability + per-project control) · I-00088 (health-probe wiring fix)
> **Purpose**: the single place we track *what* we want to ship for LLM-assisted merge conflict resolution, *why*, and *how* — and the running status of each phase. Same convention as `TESTS_ENHANCEMENT.md`: one item at a time, vehicle (CR / Feature / direct change) decided when we pick it up.
>
> **Current status (2026-05-17)**:
>
> - **F-00084 merged** (`9ba69891`, 2026-05-16) — Phase 0 plumbing + Phase 1 dry-run.
> - **F-00085 merged** (`84f30608`, 2026-05-16) — Sub-phase 1b observability **AND** a new per-project control surface (phase toggle + runtime picker on the dashboard) that was not in v1.0–v1.3 of this plan. Adds `merge_auto_verdicts` + `auto_merge_project_config` tables, two new event types (`auto_merge_health_probe`, `auto_merge_config_updated`), an aggregator module, and a full `/<project>/auto-merge` dashboard page with status chip on every project page.
> - **I-00088 merged** (`2e268b78`, 2026-05-17) — fixed a CLI-shape mismatch in the health probe; the chip will self-correct from "down" to "healthy" once 24 h of historical false-alarm failures age out of the rolling window.
> - Deployed config: `phase = 1`, `runtime_option_id` unset → falls back to project default (id=1, opencode + MiniMax-M2.7). Audit window open since 2026-05-16.
> - **Phase 1 dry-run live + observable.** Live chip on http://iw-dev-01:9900 reads `P1 opencode/minimax/MiniMax-M2.7 0 attempts ● down` — zero real conflicts so far; "down" is the lingering I-00088 window, expected to clear by ≈ 2026-05-18.
>
> **Only one active track now**: wait for natural merge-conflict events to accumulate (OP-4 → OP-5) — passive, no work required. The Sub-phase 1b "build the dashboard" track that was previously in flight is closed (F-00085). Phase 2 (auto-apply with verification gate) is gated by audit data (§6a). Phase 3 (broader allowlist) is gated by Phase 2 stability.

---

## 1. Why we are doing this at all

On 2026-05-16 we hit the same merge-queue failure twice in one afternoon — **I-00085 and I-00086** both parked in `merge_failed` because of rebase conflicts on the exact same three test files (`tests/dashboard/test_runtime_overrides_api.py`, `tests/integration/daemon/test_phase2_apply_no_self_deadlock.py`, `tests/integration/test_agent_runtime_options.py`). In both cases:

- The conflicts were **semantically trivial** for any human reader: identical numeric updates with comment drift, or a hardcoded-assert-vs-dynamic-query divergence where both versions tested the same behaviour.
- Manual resolution took the operator ~25 min of context-switching each time (open the worktree, read the diff on both sides, pick a side, `git checkout --theirs|--ours`, `git rebase --continue`, `uv run iw merge-queue retry-merge <ID>`).
- The proximate cause was three parallel batch items (I-00084 / I-00085 / I-00086) each independently updating the same fixtures after F-00081's new runtime-option migration shifted the row counts.
- The existing `executor/worktree_commit.sh` auto-resolver only handles `uv.lock` (`--ours`) and `Makefile` (`--theirs`); everything else aborts with the same operator-action message.

**The pattern is recurring.** Every time a feature touches a shared fixture file, the second-merging item conflicts. R-00076's literature survey (MergeBERT 63–68 %, DeepMerge 78 % on small hunks, ConGra 75–85 % on Python/Java, Merge-Bench < 60 % overall, Sketch ~50 % with "fails rather than producing worse merges") shows current LLMs resolve roughly half to two-thirds of real-world conflicts correctly. GitHub's Copilot cloud agent, LLMinus, and Sketch ship the **"resolve-then-verify"** pattern in production: LLM proposes → automated tests/lint must pass → only then commit. With the verification gate as the load-bearing safety mechanism (not the model), today's I-00085 and I-00086 would have been auto-resolved.

**Guiding principles** (these go verbatim into every Phase prompt and reviewer checklist):

- *The verification gate is the safety mechanism, not the model.* LLM accuracy plateaus at 50–66 %; the gate makes the false-positive rate near-zero.
- *Phase 0 is safe-by-construction.* Default config produces zero operator-visible change; if shipped and forgotten, behaviour is identical to today.
- *Refuse-list is defence-in-depth.* Bash AND Python both classify forbidden files. A bug in either alone cannot let a migration / `.env` / `.gitleaks.toml` through.
- *Phase 1 never applies.* Even with a correct LLM output, the worktree is never mutated — proposals are captured in `DaemonEvent.event_metadata` for audit.
- *Operator UX is preserved on every failure path.* `merge_conflict` event still fires; `BatchItem.status = merge_failed`; `iw merge-queue retry-merge` still works.
- *Explicit `ABSTAIN` token.* The prompt instructs the model to refuse rather than guess. Worst-case is "fall back to today's manual path" — strictly Pareto-improving.
- *Cost ceiling lives below operator-time savings.* Even with top-tier model + retries, monthly cost < $20; single avoided manual resolution pays for the month.

---

## 2. How we will work

- **One phase at a time.** Phases 0 and 1 ship together in F-00084. Phase 2 is sequenced *after* two weeks of Phase 1 audit data. Phase 3 is gated by Phase 2 stability.
- **This document is the tracker.** Each item has: why, how/approach, vehicle, status, link. Update status as we go. Don't let it drift.
- **Vehicle decided when picked up.** Each phase below names the *expected* vehicle; we may revise (e.g., split Phase 2 into two CRs) when we get there.
- **Audit data drives Phase 2 spec.** Don't pre-design the verification gate's exact scope — collect the dry-run data first, then write the CR.
- **Skill/template sync rule** (from project memory): any change under `skills/` must propagate to IW-AI-DEV + InnoForge; any change under `templates/design/` or `ai-dev/templates/` must propagate to every project in `projects.toml`.
- **Status legend**: `TODO` · `IN PROGRESS` · `BLOCKED` · `DONE` · `DEFERRED` · `DROPPED`.

---

## 3. The phases at a glance

| Phase | Theme | One-line goal | Major gain | Vehicle | Status |
|-------|-------|---------------|------------|---------|--------|
| **0 — Plumbing** | Wire the decision tree | New TOML config, refuse-list / allowlist, marker emission, daemon-side parser — no LLM call, no behaviour change | Safe-by-default surface area; future phases just flip a flag | F-00084 (combined with Phase 1) | **DONE 2026-05-16** (merge `9ba69891`) |
| **1 — Dry-run audit** | Collect what the LLM would do | Per-file LLM invocation; proposed resolutions captured in `DaemonEvent.event_metadata`; rebase always aborted | Two weeks of real data on how often the model would have been right; spec input for Phase 2 | F-00084 (Phase 0 + Phase 1 combined) | **LIVE — 0 real conflicts observed** as of 2026-05-17. `phase = 1` deployed 2026-05-16. See §5a runbook OP-4..OP-7. |
| **1b — Observability + per-project control** | Make Phase 1 visible AND opt-in-per-project | Dashboard page + status chip + activity log + diff viewer + verdict capture + accuracy/cost rollup + health probe + refuse-list breakdown + **per-project phase/runtime override surface** (added during spec) | Sustainable OP-4 monitoring; Phase 2 entry criteria auto-computed; operator confidence; projects opt in independently | F-00085 + I-00088 (health-probe wiring fix) | **DONE 2026-05-16/17** (F-00085 `84f30608`, I-00088 `2e268b78`) |
| **2 — Auto-apply with verification gate** | Make it actually resolve | Apply LLM output; run scoped QV (lint + type-check + targeted tests + assertion scanner); only `git rebase --continue` on green; narrow allowlist `tests/**`, `docs/**`, `ai-dev/active/**/reports/**` | Today's recurring failures (I-00085-style) merge automatically; zero operator action | Feature (likely F-NNNNN — TBD) | **NOT STARTED** (gated by Phase 1 audit) |
| **3 — Broader allowlist** | Expand beyond test files | Allowlist extended to source files; possibly multi-file prompt context; possibly model upgrade | Source-file conflicts also auto-resolve | CR or Feature (TBD per audit) | **NOT STARTED** (gated by Phase 2 stability) |

---

## 4. Phase 0 — Plumbing: decision tree without LLM call

**Why now**: every later phase needs the same decision tree, marker emission, event types, and config file. Landing it as a no-op first means the surface area is reviewed and safe before any LLM tokens are consumed.

**Major gains**: a single, reviewable plumbing layer; operator-visible behaviour identical to today; refuse-list defence-in-depth in place from day one.

| # | Item | Why | How / approach | Vehicle | Status | Link |
|---|------|-----|----------------|---------|--------|------|
| 0.1 | `executor/auto_merge.toml` (default `phase = 0`) | Config surface for operator; future-proof phase ladder | New TOML with phase, allowlist patterns, refuselist patterns, limits, `runtime_option_id`. Default phase=0 = no LLM call. Comments document phase ladder. | Feature (F-00084 S01) | **DONE 2026-05-16** (merge `9ba69891`) | F-00084 |
| 0.2 | `executor/worktree_commit.sh` — classify + emit markers | Bash needs to surface conflict files to Python with classification | Refuse-list coarse match (prefixes + suffixes) in bash; emit `AUTO_RESOLVE_REQUESTED=<json>` on stdout for eligible-file conflicts, `AUTO_RESOLVE_SKIPPED=<json>` for refuse-list / mixed cases. Existing `CONFLICT_FILES=` marker still emitted. Rebase ALWAYS aborted in Phase 0/1. | Feature (F-00084 S01) | **DONE 2026-05-16** (merge `9ba69891`) | F-00084 |
| 0.3 | `--resume-rebase` flag stub | Plant Phase-2 CLI surface so its CR doesn't have to re-touch `worktree_commit.sh` | Flag accepted but exits 2 with "reserved for Phase 2" message. Surface only; no logic. | Feature (F-00084 S01) | **DONE 2026-05-16** (merge `9ba69891`) | F-00084 |
| 0.4 | `orch/daemon/auto_merge.py` — `AutoMergeConfig` + decision tree | Python-side rich-glob classifier; precedence enforcement | `tomllib`-based loader with defaults-on-missing/malformed; `classify_conflicts()` with documented precedence (refuse > binary > oversized > too-many > not-allowlisted > eligible); Invariant 6 determinism test. | Feature (F-00084 S03) | **DONE 2026-05-16** (merge `9ba69891`) | F-00084 |
| 0.5 | `orch/daemon/merge_queue.py` — marker parser + safety try/except | Daemon needs to detect markers and route to auto_merge while preserving today's failure path | New parser invoked after existing `_CONFLICT_MARKER_RE`; calls `attempt_resolution()` inside try/except; existing `merge_conflict` event + `merge_failed` status always fire. | Feature (F-00084 S03) | **DONE 2026-05-16** (merge `9ba69891`) | F-00084 |
| 0.6 | Four new `DaemonEvent` types | Audit trail with no schema migration | `merge_auto_resolution_attempted`, `merge_auto_resolved`, `merge_auto_resolution_failed`, `merge_auto_resolution_skipped` as plain TEXT values in `daemon_events.event_type`; JSONB `event_metadata` payload schema documented in R-00076 §5.7. | Feature (F-00084 S03) | **DONE 2026-05-16** (merge `9ba69891`) | F-00084 |
| 0.7 | `executor/step_executor_lib.sh` — `auto_merge_resolve` step type | LLM invocation via existing runtime, no new SDK | Minimal `_run_agent_oneshot` helper: stdin → `opencode run` / `claude --print` → stdout. No DB writes, no PID, no step-done. | Feature (F-00084 S03) | **DONE 2026-05-16** (merge `9ba69891`) | F-00084 |
| 0.8 | Hot-reload via SIGHUP | Operator advances phase without daemon restart | Re-read `auto_merge.toml` on SIGHUP via existing project_registry handler; module-level cache. | Feature (F-00084 S03) | **DONE 2026-05-16** (merge `9ba69891`) | F-00084 |
| 0.9 | Unit tests: config, classifier, prompt builder, marker parser | Plumbing-layer contracts pinned | Per F-00084 S06 plan: 11 config tests, 11 classifier tests, 10 prompt-builder tests, 7 marker-parser tests. | Feature (F-00084 S06) | **DONE 2026-05-16** (merge `9ba69891`) | F-00084 |
| 0.10 | Integration test: refuse-list defence-in-depth (AC3) | A migration file in conflict must NEVER reach the LLM | Fixture-built repo with synthetic conflict in `orch/db/migrations/versions/*.py`; assert `merge_auto_resolution_skipped` event + zero subprocess calls + bash AND Python classification agree. | Feature (F-00084 S06) | **DONE 2026-05-16** (merge `9ba69891`) | F-00084 |
| 0.11 | Integration test: phase=0 default behaviour (AC5) | Safe-by-construction proof | Fixture conflict in `tests/**`; assert `AUTO_RESOLVE_REQUESTED` emitted; `merge_auto_resolution_skipped` with `reason="phase_0"`; zero subprocess calls; existing `merge_conflict` + `merge_failed` byte-identical to today. | Feature (F-00084 S06) | **DONE 2026-05-16** (merge `9ba69891`) | F-00084 |

---

## 5. Phase 1 — Dry-run audit: capture what the LLM would do

**Why now**: literature gives us 50–66 % accuracy on benchmarks; we need our-codebase-specific data before any auto-apply. Phase 1 collects that data with zero risk — proposals are captured in event metadata but never applied.

**Major gains**: empirical answer to "how often would the resolver be right on IW AI Core conflicts?"; prompt iteration data (which prompt variant abstains less / hits more); ground truth for Phase 2's verification-gate scope.

| # | Item | Why | How / approach | Vehicle | Status | Link |
|---|------|-----|----------------|---------|--------|------|
| 1.1 | LLM prompt builder per R-00076 §5.5 | Working recipe: full files (base/ours/theirs), recent commits both sides, work-item description, explicit `ABSTAIN` token, no-invention clause | `build_resolution_prompt()` in `auto_merge.py`; deterministic (no `now()` / random); `prompt_hash = sha256(prompt)` stored in event metadata; description truncated to ~500 words; no env-leakage (S06 test enforces). | Feature (F-00084 S03) | **DONE 2026-05-16** (merge `9ba69891`) | F-00084 |
| 1.2 | LLM invocation via `step_executor.sh` | Reuse existing runtime, no SDK dep, agent+model configurable | `invoke_llm_for_file()` subprocess-calls `step_executor.sh` with new `step_type=auto_merge_resolve`; `(cli_tool, model)` resolved from `agent_runtime_options` via `runtime_option_id` in TOML; timeout from config. | Feature (F-00084 S03) | **DONE 2026-05-16** (merge `9ba69891`) | F-00084 |
| 1.3 | `ABSTAIN` token handling | Pareto-improving safety net | Exact-match-after-strip on LLM output; `LLMCallResult.abstained = True`; `merge_auto_resolution_failed` event with `failed_reason="abstain"` if any file abstains. | Feature (F-00084 S03) | **DONE 2026-05-16** (merge `9ba69891`) | F-00084 |
| 1.4 | Proposed resolutions stored in `event_metadata` JSONB | Operator-reviewable audit without new schema | Full proposed file contents inlined in `merge_auto_resolved` event metadata; Invariant 5 truncation when total payload > 256 KB (with `truncated_files: [...]` marker). | Feature (F-00084 S03) | **DONE 2026-05-16** (merge `9ba69891`) | F-00084 |
| 1.5 | Phase-1 ALWAYS-abort invariant | The dry-run guarantee | `attempt_resolution()` returns `success=False` on every code path in Phase 1; no `git add`; no `git rebase --continue`; Invariant 3 test snapshots `HEAD` + `status --porcelain` before/after and asserts byte-equality. | Feature (F-00084 S03) | **DONE 2026-05-16** (merge `9ba69891`) | F-00084 |
| 1.6 | Integration test: I-00085-shape conflict (AC1) | Anchor test on today's failure | Fixture-built repo reproducing I-00085's 3-file comment-drift conflict; mocked LLM returns correct resolutions; assert event ordering, metadata fields, abort outcome. | Feature (F-00084 S06) | **DONE 2026-05-16** (merge `9ba69891`) | F-00084 |
| 1.7 | Integration test: I-00086-shape conflict (AC2) | Anchor test on today's other failure | Fixture-built repo reproducing I-00086's hardcoded-vs-dynamic + `_PREV_REVISION` divergence; assert prompt contains three-way content and recent commit logs. | Feature (F-00084 S06) | **DONE 2026-05-16** (merge `9ba69891`) | F-00084 |
| 1.8 | Integration test: operator UX unchanged (AC4) | Pareto-improving property pinned | LLM abstains; assert `merge_conflict` + `merge_failed` fire as today; `iw merge-queue retry-merge` resets state. | Feature (F-00084 S06) | **DONE 2026-05-16** (merge `9ba69891`) | F-00084 |
| 1.9 | Integration test: SIGHUP hot reload (AC6) | Operator workflow validated | Start phase=0; rewrite TOML to phase=1; SIGHUP; next merge invokes the LLM mock. | Feature (F-00084 S06) | **DONE 2026-05-16** (merge `9ba69891`) | F-00084 |

### 5a. Phase 1 — Post-deployment operator runbook (operator items, NOT agent items)

| # | Item | When | Notes |
|---|------|------|-------|
| OP-1 | Merge F-00084 with `phase = 0` | After F-00084 approval + execution | **DONE 2026-05-16** — merged at `9ba69891`, BATCH-00107 archived as `4dfedaf7`. Deployed config: `phase = 0`, `runtime_option_id = null`. Daemon running with new plumbing as a no-op. |
| OP-2 | Edit `executor/auto_merge.toml`: `phase = 0 → 1` | When ready to start collecting audit data | **DONE 2026-05-16** — `phase = 1`, `runtime_option_id = null` (falls back to project default id=1: opencode + MiniMax-M2.7). |
| OP-3 | Send SIGHUP to daemon | Immediately after OP-2 | **DONE 2026-05-16** — `./ai-core.sh daemon reload` sent. Note: `auto_merge.toml` is read fresh per merge by `merge_queue.py:485`, no cache, so the new phase took effect immediately; SIGHUP is documented for consistency. |
| OP-4 | Monitor `merge_auto_resolution_*` events | Two weeks minimum (audit window starts 2026-05-16) | **IN PROGRESS — 0 real-conflict events as of 2026-05-17**. Primary surface is now the dashboard page at `/<project>/auto-merge` (shipped in F-00085), with status chip on every per-project page. The filter chips on that page expose `attempted / resolved / failed / skipped / health_probe / config_updated` directly — SQL is the fallback, not the default workflow.<br>Fallback SQL:<br>`SELECT event_type, count(*), max(created_at) FROM daemon_events WHERE event_type LIKE 'merge_auto_%' OR event_type LIKE 'auto_merge_%' GROUP BY event_type ORDER BY 1;` |
| OP-5 | Review accuracy on each captured event | Continuous during the audit window | For each `merge_auto_resolved` event: open the diff modal on the dashboard, compare LLM-proposed content (left) against `main`'s current content (right), and mark `correct / wrong / partial` via the inline verdict widget (persisted to `merge_auto_verdicts`). 7d/30d accuracy rollup is computed automatically — no manual tally needed. |
| OP-6 | Tally cost | End of audit window | Read off the "Token cost rollup" widget on the dashboard (7d/30d windows, per-model breakdown using `MODEL_PRICING` in `orch/auto_merge_aggregator.py`). Confirm < $20/month projection. |
| OP-7 | Decide Phase 2 spec | After audit data | If accuracy ≥ 4/5 conflicts correct → proceed to Phase 2 with confidence. If lower → Phase 2 still viable (the verification gate catches failures) but plan for more abstentions. |

---

### 5b. Phase 1 — Observability + per-project control sub-phase (DONE)

**Why we did this**: Phase 1 dry-run is invisible without UI. The 2-week audit window was friction-heavy if the operator had to run SQL to know whether anything had happened. R-00076 §3.5 had parked dashboard UI in Phase 3, but that ordering was wrong — visibility is an *enabler* of the Phase 1 audit, not a Phase 3 nice-to-have. Identified 2026-05-16 after F-00084 deployment; designed and shipped same day as **F-00085**.

**What we got**: operator confidence ("the resolver is live and ready"); sustainable monitoring without SQL-on-demand; per-event verdict capture that feeds Phase 2 entry criteria (≥ 50 % accuracy) automatically; refuse-list safety net visible as a positive signal; health probe surfacing silent breakage. **And one beyond-plan addition**: a per-project control surface (phase + runtime override on the dashboard) so projects can opt in independently of the global TOML default — mirroring F-00081's step-level override pattern.

**Vehicle**: Feature F-00085 (merge `84f30608`, 2026-05-16) + Incident I-00088 (health-probe wiring fix, merge `2e268b78`, 2026-05-17). Three-tier scope: Tier 1 (status + activity log) + Tier 2 (diff viewer + verdict + accuracy stats) + Tier 3 (health probe + refuse-list breakdown) + Control surface (new).

| # | Item | Why | How / approach | Tier | Vehicle | Status | Link |
|---|------|-----|----------------|------|---------|--------|------|
| 1.10 | `/<project>/auto-merge` dashboard page + header status chip | Make the resolver's deployed state visible at a glance | FastAPI router `dashboard/routers/auto_merge_ui.py` + page template `dashboard/templates/pages/project/auto_merge.html`; chip included from `base.html`; aggregator `orch/auto_merge_aggregator.py:get_status_snapshot()` | Tier 1 | F-00085 | **DONE 2026-05-16** | `84f30608` |
| 1.11 | Filtered events table for `merge_auto_*` rows | Replace on-demand SQL with a browsable view; expandable JSONB metadata | htmx fragment `auto_merge_events_table.html` + `auto_merge_event_row.html`; pagination; filter chips `all/attempted/resolved/failed/skipped/health_probe/config_updated`; click-to-expand event detail modal | Tier 1 | F-00085 | **DONE 2026-05-16** | `84f30608` |
| 1.12 | Explicit refuse-list counter | Confirm the safety net is being exercised even when phase=1 dry-run never resolves | `auto_merge_refuse_list.html` fragment; aggregator `get_refuse_list_breakdown()` groups `merge_auto_resolution_skipped` rows by `event_metadata.reason`; widget hidden when all-zero | Tier 1 + 3 hybrid | F-00085 | **DONE 2026-05-16** | `84f30608` |
| 1.13 | Side-by-side diff viewer for `merge_auto_resolved` events | Make OP-5 (proposed-vs-actual review) tractable; replaces JSONB-spelunking | Server-rendered `difflib.HtmlDiff` in `auto_merge_event_detail.html` modal; left = LLM `proposed_content` from `event_metadata`, right = `git show main:<file>`; "(file no longer exists on main)" placeholder if missing | Tier 2 | F-00085 | **DONE 2026-05-16** | `84f30608` |
| 1.14 | Operator-verdict capture | Drive Phase 2 entry criteria automatically | NEW table `merge_auto_verdicts` (composite PK `(project_id, daemon_event_id)`, FK to `daemon_events.id`, CHECK `verdict IN ('pending','correct','wrong','partial')`); inline + modal verdict widgets; POST endpoint persists with `verdicted_by` + `verdicted_at` | Tier 2 | F-00085 | **DONE 2026-05-16** | `84f30608`, migration `678ac4dd44b7` |
| 1.15 | Rolling accuracy + token-cost rollup | Phase 2 entry criteria (≥ 50 % accuracy, < $20/mo) become a single query | Aggregator `get_verdict_rollup()` + `get_token_cost_rollup()` (7d / 30d windows); per-model `MODEL_PRICING` dict covering opencode/MiniMax, opencode/gpt-5.3-codex, claude/sonnet-4-6, claude/opus-4-7; rendered in `auto_merge_rollup.html` | Tier 2 | F-00085 | **DONE 2026-05-16** | `84f30608` |
| 1.16 | Health: resolver-runtime reachability check | Surface silent breakage (e.g., LLM API down) without waiting for a conflict | Daemon background task `orch/daemon/auto_merge_health.py` emits `auto_merge_health_probe` event every `probe_interval_seconds` (default 300) per enabled project; metadata `{runtime_reachable, cli_tool, model, probe_duration_ms, error}`; chip renders most recent state | Tier 3 | F-00085 + I-00088 (CLI-shape fix) | **DONE 2026-05-17** | `84f30608` + `2e268b78` |
| 1.17 | Failure-rate alerting (dashboard-only) | Catch a degradation in LLM behaviour before Phase 2 ships | `[health].failure_rate_threshold_per_day` (default 3) in `executor/auto_merge.toml`; chip turns yellow / red once the threshold trips; no email/webhook | Tier 3 | F-00085 | **DONE 2026-05-16** | `84f30608` |
| 1.18 | Refuse-list activity breakdown | Show the safety net's exact pattern (refuse_list / binary / oversized / not_allowlisted / phase_0) | Aggregator `get_refuse_list_breakdown()` grouped by `event_metadata.reason`; rendered as a Tier 3 widget on the page | Tier 3 | F-00085 | **DONE 2026-05-16** | `84f30608` |
| **1.19** | **Per-project control surface (NEW — beyond original plan)** | Let operators enable/disable the resolver per project and pick its runtime without touching the global TOML | NEW table `auto_merge_project_config` (PK `project_id`, columns `phase INT NULL`, `runtime_option_id INT NULL FK agent_runtime_options.id`, `updated_at`, `updated_by`); resolution order `DB row > TOML > defaults` via `resolve_project_config()`; settings panel `auto_merge_settings.html` with phase (0/1/global) + runtime picker; POST endpoint emits new `auto_merge_config_updated` DaemonEvent | Control | F-00085 | **DONE 2026-05-16** | `84f30608`, migration `678ac4dd44b7` |

### 5b.1. Entry criteria for the Observability feature — historical

Were satisfied 2026-05-16 (F-00084 stable on main; sustainable monitoring use case named). Kept here for the precedent.

### 5b.2. Out of scope for this sub-phase (and still out of scope)

- Auto-applying resolutions (still Phase 2).
- Push notifications / email / Slack alerts (Tier 3 stopped at dashboard-visible signal).
- Verdict-via-LLM-as-judge automation (Phase 3 maybe).
- Cross-project aggregation (per-project for now; the dashboard's routing already scopes by project).
- Auth on the Settings POST endpoint (dashboard is localhost-only today; add auth when remote access lands).
- Phase 2 / 3 selectable in the Settings dropdown — only 0 / 1 are user-pickable; 2 / 3 are reserved for future CRs.

### 5b.3. Known follow-ups from F-00085 / I-00088

- The chip currently reads "down" because of pre-I-00088 false-alarm probes still inside the 24 h rolling failure window. Expected to clear automatically by ≈ 2026-05-18; no operator action needed.
- I-00088's functional doc flags one operational-hygiene follow-up (not blocking): manually clearing the historical "down" verdict from the database. Skipped; the window will age out on its own.
- `MODEL_PRICING` in `orch/auto_merge_aggregator.py` covers the currently-enabled runtimes; unknown models render as $0 with a code comment. Add new models to the dict as they're enabled.

---

## 6. Phase 2 — Auto-apply with verification gate

**Why now**: only after Phase 1 audit proves the LLM hits ≥ ~50 % correct AND the verification gate scope is empirically validated. Phase 2 is where the operator-pain reduction actually starts.

**Major gains**: today's recurring I-00085-style failures merge automatically; operator effort on parallel-fixture conflicts drops to ~0.

**Major risks**: LLM output passes lint + targeted tests but breaks cross-file invariants not in the verification gate scope. Mitigated by narrow allowlist (tests/docs/reports only); broadened only in Phase 3 after observability.

| # | Item | Why | How / approach | Vehicle | Status | Link |
|---|------|-----|----------------|---------|--------|------|
| 2.1 | Implement `attempt_resolution()` apply-path | Make Phase 2 actually resolve | When phase=2 AND classifier returns eligible AND all LLM calls return non-ABSTAIN, write resolved file content, `git add` each file, run verification gate; on green call `worktree_commit.sh --resume-rebase`; on red abort. | Feature (TBD F-NNNNN) | **NOT STARTED** | — |
| 2.2 | Verification gate — scoped subset of QV | Catch wrong-but-plausible LLM output | Scoped run: `make lint` + `make type-check` + `make test-assertions` + targeted `pytest -k "<resolved-file-stems>"`. Timeout configurable (default 600s). Each gate's exit code + log captured in event metadata. | Feature (TBD F-NNNNN) | **NOT STARTED** | — |
| 2.3 | `worktree_commit.sh --resume-rebase` real impl | Stub from Phase 0 becomes functional | Accepts the index in a resolved state; runs `git rebase --continue`; if successful, proceeds to existing squash-merge step. | Feature (TBD F-NNNNN) | **NOT STARTED** | — |
| 2.4 | Narrow allowlist for Phase 2 | Bounded blast radius | TOML allowlist patterns: `tests/**`, `docs/**`, `ai-dev/active/**/reports/**`. NOT yet source files. Refuse-list unchanged from Phase 0. | Feature (TBD F-NNNNN) | **NOT STARTED** | — |
| 2.5 | New event metadata schema for `merge_auto_resolved` (Phase 2 variant) | Verification audit | Add `verification_gate: {lint: pass/fail, type_check: pass/fail, ...}`; `applied: true|false`; `commit_sha` (the resulting rebased commit) on success. | Feature (TBD F-NNNNN) | **NOT STARTED** | — |
| 2.6 | Integration test: AC4 verification catch | The verification gate's load-bearing role pinned | Construct a fixture where the LLM's resolution would break a targeted unit test; assert verification gate fails; assert `git rebase --abort` restores pre-attempt state; assert `merge_auto_resolution_failed` event with `failed_reason="verification_failed"` and the gate log; assert `merge_conflict` still fires. | Feature (TBD F-NNNNN) | **NOT STARTED** | — |
| 2.7 | Integration test: AC1 / AC2 actually merge | The operator-pain-reduction proof | Same fixtures as Phase 1 AC1/AC2 but with phase=2; assert the resulting commit hash on main contains the resolved files and equals the manual outcome (modulo comment wording). | Feature (TBD F-NNNNN) | **NOT STARTED** | — |
| 2.8 | Concurrency cap on LLM calls | Token rate-limit friendly | Per-merge concurrency=3 across the eligible files (bounded by `max_conflicted_files_per_merge=5`); merge queue already serialises across items. | Feature (TBD F-NNNNN) | **NOT STARTED** | — |
| 2.9 | Operator kill-switch documentation | Roll back fast if needed | Confirm `phase = 0` in TOML + SIGHUP reverts to today's behaviour within one poll cycle; document in operator runbook. | Direct (doc) | **NOT STARTED** | — |
| 2.10 | Cost / latency observability | Confirm Phase 2 stays under budget | Aggregate `llm_calls[*].input_tokens + output_tokens` per merge in event metadata; add a dashboard widget showing 7-day rolling token cost. (Widget itself may be a follow-up CR.) | TBD (CR for widget) | **NOT STARTED** | — |

### 6a. Entry criteria for Phase 2 spec/kickoff

Don't open the Phase 2 design doc until ALL of these are true:

- F-00084 has merged and Phase 1 has been running for **at least two weeks** (OP-2 through OP-6 complete).
- At least **5 real conflicts** have hit Phase 1 dry-run (i.e., 5+ `merge_auto_resolution_attempted` events).
- Operator review (OP-5) confirms the LLM proposal was **correct on ≥ 50 %** of those events.
- Operator review confirms the LLM proposal was **never silently wrong on a security-sensitive file** (would have been caught by refuse-list; this is the categorical safety check).
- Cost projection (OP-6) confirms < $20/month at projected volume.

If any of these fail, revise Phase 1 (e.g., prompt iteration, model swap) before opening Phase 2.

---

## 7. Phase 3 — Broader allowlist

**Why now**: only after Phase 2 has been running with the narrow allowlist for at least one month with zero post-merge regressions traced to an auto-resolution.

**Major gains**: source-file conflicts (not just test fixtures) also auto-resolve; covers the long tail of formatter sweeps, import-list updates, parallel additive edits to source files.

**Major risks**: source-file resolutions can break cross-file invariants the verification gate doesn't observe. Mitigated by expanding the verification gate AND requiring a stricter abstention threshold.

| # | Item | Why | How / approach | Vehicle | Status | Link |
|---|------|-----|----------------|---------|--------|------|
| 3.1 | Allowlist expansion: `dashboard/templates/**`, `dashboard/static/**` | Low-risk source-file paths first | TOML allowlist additions. | CR (TBD CR-NNNNN) | **NOT STARTED** | — |
| 3.2 | Allowlist expansion: `dashboard/routers/**`, `orch/cli/**` | Medium-risk source paths | TOML allowlist additions + verification gate widened (add `make test-dashboard` for dashboard files). | Feature (TBD F-NNNNN) | **NOT STARTED** | — |
| 3.3 | Multi-file prompt context | LLM sees the file being resolved + 1–2 related files (imports / callers) | Extend `build_resolution_prompt()` with optional context-files section; gated by file-pair heuristic. | Feature (TBD F-NNNNN) | **NOT STARTED** | — |
| 3.4 | Model upgrade decision | Phase 1/2 may show Opus is meaningfully better than Sonnet on hard conflicts | Based on Phase 1/2 audit data; possibly per-allowlist-subdir model selection (cheaper model for tests, premium for source). | TBD | **NOT STARTED** | — |
| 3.5 | Operator-facing dashboard page | Audit-event browsing without raw SQL | New `/auto-merge` dashboard route showing recent attempts, accuracy stats, cost rolling 7-day. | Feature (TBD F-NNNNN) | **NOT STARTED** | — |

### 7a. Entry criteria for Phase 3 spec/kickoff

- Phase 2 has been running with the narrow allowlist for **at least one month**.
- **Zero** post-merge regressions traced to an auto-resolution (operator must explicitly verify this; not "no incident reported").
- The verification gate has caught at least one bad LLM output (proving the gate is doing its job, not just rubber-stamping).
- Cost continues to track < $30/month at the Phase 2 volume.

---

## 8. Risk register (living)

| Risk | Severity | Mitigation | Status |
|------|----------|------------|--------|
| LLM hallucinating a "fix" that passes lint + targeted tests but breaks a cross-file invariant | HIGH | Phase 2 narrow allowlist (tests/docs only); verification gate scope tuned per Phase 1 data; Phase 3 expansion gated by zero-regression record | **OPEN** — gated by Phase 1 audit |
| Refuse-list bypass via path-traversal or symlink trick | CRITICAL | Bash + Python classification both run; bash uses prefix/suffix coarse match; Python uses fnmatch with realpath; no shell expansion of paths | Mitigated in F-00084 design; verify in S05 (final cross-agent review) |
| LLM prompt leaks secrets from worktree (env vars, `.env` files) | HIGH | Prompt builder never reads env; `.env*` in refuse-list; S06 test asserts no `os.environ` leak; description truncation prevents long secrets via item title | Mitigated in F-00084 design |
| JSONB row inflation from inlining proposed file contents | MEDIUM | Invariant 5 caps single-event metadata at 256 KB with `truncated_files: [...]` marker; Phase 1 audit data will inform whether to move to sidecar in Phase 2 | Mitigated; revisit at Phase 2 kickoff |
| SIGHUP race during in-flight merge | LOW | Merge queue is serialised; reload happens on poll boundaries; worst case one merge runs with old config (acceptable for dry-run) | Accepted; revisit at Phase 2 if needed |
| Subprocess startup overhead per LLM call (~3-5s) makes Phase 2 merge-queue latency unacceptable | MEDIUM | Phase 1 audit captures wall-clock per `merge_auto_resolved` event; if > 60s p95, evaluate direct SDK integration in Phase 3 | **OPEN** — gated by Phase 1 audit data |
| Phase 1 audit produces too few real conflicts to validate Phase 2 | MEDIUM | If < 5 conflicts in 2 weeks, extend window OR seed with replays of historical conflicts via a new `iw auto-merge replay <ID>` operator command | **OPEN** — revisit at audit-data review |
| Operator forgets the feature is deployed and is surprised by audit events | LOW | Phase 0 default produces ZERO audit events (Phase 0 short-circuits before event emission for `attempted` / `resolved`); only `merge_auto_resolution_skipped` fires with `reason="phase_0"`; documented in `F-00084_Functional.md` | Mitigated by Phase 0 design |
| Phase 1 dry-run is invisible without UI; operator gives up on OP-4 monitoring | MEDIUM | Sub-phase 1b (F-00085) is the mitigation; on-demand SQL is now the fallback, not the default workflow | **CLOSED 2026-05-16** — F-00085 shipped the dashboard, status chip, activity log, diff viewer, verdict capture, and rollups |
| `auto_merge.toml` shipped with invalid `runtime_option_id = null` (TOML lacks `null` keyword); strict pre-commit TOML validator rejects it | LOW | Loader at `orch/daemon/auto_merge.py:184` regex-strips `key = null` lines for back-compat, so runtime is unaffected. Fix applied 2026-05-16 (commit `1856cf8b`): commented out the line. Follow-up: add a strict-TOML test to the F-00084 design template; consider filing I-NNNNN to harden the loader's expected schema | **MITIGATED 2026-05-16** — committed fix; follow-up incident not yet filed |
| Health probe always reports "down" — CLI-shape mismatch with `step_executor.sh` | MEDIUM | I-00088 corrected the probe call shape so the runtime is now genuinely exercised; the 24 h rolling window clears the lingering false-alarm failures automatically | **CLOSED 2026-05-17** — fix merged at `2e268b78`; chip self-corrects by ≈ 2026-05-18 |

---

## 9. Cross-references

- **Research**: [`docs/research/R-00076-llm-automated-merge-resolution.md`](../../docs/research/R-00076-llm-automated-merge-resolution.md) — full literature survey, design rationale, acceptance criteria.
- **Phase 0 + Phase 1 Feature**: F-00084 — merged `9ba69891`, archived at `ai-dev/archives/iw-ai-core/F-00084.tar.zst`.
- **Sub-phase 1b Feature (observability + control surface)**: F-00085 — merged `84f30608`, archived at `ai-dev/archives/iw-ai-core/F-00085.tar.zst`. Adds tables `merge_auto_verdicts` + `auto_merge_project_config`, event types `auto_merge_health_probe` + `auto_merge_config_updated`, aggregator `orch/auto_merge_aggregator.py`, dashboard router `dashboard/routers/auto_merge_ui.py`, page + 6 fragments.
- **Health-probe fix**: I-00088 — merged `2e268b78`, archived at `ai-dev/archives/iw-ai-core/I-00088.tar.zst`. Corrected the `step_executor.sh` CLI-shape mismatch that caused the probe to always report "down".
- **Originating incidents**: I-00085 (`.mypy_cache triggers gitleaks false positives — S12 → S16 ordering bug`), I-00086 (`Runtime override controls give no UI feedback`). Both merged on 2026-05-16 after manual rebase conflict resolution — see git log for `Merge I-00085` (f69e668b) and `Merge I-00086` (40c6ea41).
- **Sister tracking docs**: [`../work/TESTS_ENHANCEMENT.md`](../work/TESTS_ENHANCEMENT.md) — the precedent for multi-phase quality initiatives in this repo (lives under `ai-dev/work/`, not `ai-dev/active/`).
- **Project rules**: `CLAUDE.md` § "Critical Rules" — refuse-list patterns derive from the same set of files we already protect (migrations, `.env`, `.gitleaks.toml`, identity files, executor scripts).

---

## 10. Changelog

| Date | Version | Change |
|------|---------|--------|
| 2026-05-16 | v1.0 | Initial plan written after R-00076 filed and F-00084 packaged (draft). Phase 0 + Phase 1 in F-00084; Phase 2 + Phase 3 not yet started. |
| 2026-05-16 | v1.1 | F-00084 merged (`9ba69891`); all Phase 0 + Phase 1 implementation rows flipped to DONE; OP-1 closed. Phase 1 status → **AWAITING OPERATOR** (deployed config still `phase = 0`). Next action: pick a `runtime_option_id` and flip to `phase = 1` to start the audit window (OP-2..OP-7). |
| 2026-05-16 | v1.2 | OP-2 + OP-3 closed: `executor/auto_merge.toml` set to `phase = 1`, `runtime_option_id = null` (falls back to project default id=1 — opencode + MiniMax-M2.7); SIGHUP sent. Phase 1 dry-run is now live; audit window started 2026-05-16. Next: OP-4 monitoring (0 events so far). |
| 2026-05-16 | v1.3 | Added Sub-phase 1b — Observability Feature scope (§5b, 9 rows across Tier 1+2+3) — to surface the resolver's state in the dashboard and make OP-4 monitoring sustainable. Added at-a-glance row "1b — Observability". Filed risk for invisible Phase 1 (open) + TOML `null` fix (mitigated, commit `1856cf8b`). |
| 2026-05-16 | v1.4 | F-00085 picked up and merged (`84f30608`). All nine §5b rows (1.10–1.18) flipped to DONE. Vehicle assignment changed from "TBD F-NNNNN" → F-00085. Risk "Phase 1 invisible without UI" closed. |
| 2026-05-16 | v1.5 | Recorded the **beyond-plan addition** that landed in F-00085: a per-project control surface (Settings panel: phase toggle + runtime picker) backed by a new `auto_merge_project_config` table and a new `auto_merge_config_updated` DaemonEvent type. Added §5b row 1.19 and listed the table + event in §9 cross-references. |
| 2026-05-17 | v1.6 | Sync with on-disk + dashboard reality. I-00088 (CLI-shape fix for the health probe, merge `2e268b78`) closed and recorded as a §5b follow-up + risk row. Live chip state quoted in header. Tracking-ticket line broadened to F-00084 + F-00085 + I-00088. Section 5a operator runbook rows (OP-4 / OP-5 / OP-6) rewritten to point at the dashboard as the primary surface, with SQL relegated to fallback. |
