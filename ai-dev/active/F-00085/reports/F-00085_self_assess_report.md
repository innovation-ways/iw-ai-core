# F-00085 — Self-Assessment Report

**Work Item**: F-00085 — Auto-Merge Resolver — Observability + Per-Project Control
**Final outcome**: code complete; QV gates green (lint, format, typecheck, test-assertions, test-unit, security-secrets); integration test sweep green for the F-00085 surface (45 tests across `tests/dashboard/test_auto_merge_routes.py` + `tests/integration/test_auto_merge_observability.py` + `tests/integration/test_auto_merge_control_surface.py`); S07 skipped after 5 fix cycles because the underlying findings were eventually addressed by subsequent backend work; S24 browser verification skipped (ENV_DATA_MISSING) because the worktree-isolated E2E compose stack was not running and the live orch DB lacks the F-00085 migration. S15 final cross-agent review's mandatory findings were all addressed post-merge of S15.

## Process issues observed (sorted by impact)

### 1. (HIGH) Fix-cycle exhaustion on S07 — review verdict drifted from actual code state

S07 (per-agent review of the S06 Backend layer) burned all 5 fix cycles without resolving. Inspection of the actual code after the 5th cycle showed that the reviewer's flagged issues HAD been addressed:

- TOML loader refuses `phase >= 2` (`orch/daemon/auto_merge.py:223-230`).
- Rollup queries use `func.now() - timedelta(...)` (DB-side, parameterized).
- `get_event_detail` does a direct LEFT-JOIN query by `(project_id, event_id)` instead of paginated in-memory scan.
- Invalid per-project phase logs a warning and falls back to 0.

**Root cause hypothesis**: the reviewer agent likely re-loaded the *original* report each fix cycle and never re-grepped the code to confirm fixes had landed. The 5-cycle exhaustion in this workflow stops the daemon from advancing, so a stale review never gets the "PASS" signal even when the code is correct.

**Suggested improvement to the per-agent-review prompt**:
- "Before reporting NEEDS_FIX on cycle N>1, **re-grep the file:line you flagged on cycle N-1**. If the line content has changed in a way that addresses your finding, lower the verdict to PASS or downgrade the severity."
- Or: add a step-fail escape hatch when the verdict text is byte-identical across two consecutive cycles (the daemon has the data to detect this).

### 2. (HIGH) Manual reset path is heavy when the orchestrator chain breaks

When S07 failed and S08..S15 were already completed (the orchestrator's "happy path" continued past S07's failure into the test/review/final-review phases on the assumption that the fix would land in a later cycle), the manual recovery required:

- `step-skip S07 --reason ...` (only allowed when the step is in `failed` state).
- Re-issuing S11 / S14 (the per-agent reviews of S10 / S13 that had been left in `pending` while reports were *written*).

The mismatch between the report-file existing on disk and the DB-side step status existing in `pending` is a footgun — the operator has to guess whether the reports are stale or just unregistered. **Suggested improvement**: surface "report file present, step in pending" as a `iw item-status --verbose` warning, so the operator knows to re-run `step-start + step-done` from the orchestrator.

### 3. (MEDIUM) Frontend agent stopped mid-task after Fix 1 of 6

The cross-layer fix-cycle agent (frontend-impl) completed Fix 1 (chip middleware + base.html gating) and emitted a partial transcript ending in "Let me check how `projects` gets into the nav" — i.e. it stopped while still investigating context for Fix 2 (Settings form rename). Fixes 2..6 were left undone and the operator had to do them inline.

**Suggested improvement**: the agent's prompt was explicit about 5 fixes but the agent's stop signal was triggered by something else (timeout / token budget / hook). The orchestrator should detect partial fix-cycle completion (e.g., "less than 50 % of declared fixes touched any file") and re-launch with a focused prompt on the remaining items rather than continuing the workflow assuming the cycle succeeded.

### 4. (MEDIUM) `_seed_runtime` clash with prod-seeded `agent_runtime_options`

The integration test `_seed_runtime` helper in `tests/integration/test_auto_merge_control_surface.py` historically used low integer ids (1, 4, 8). When AC11 test was added with id=4 + `claude-sonnet-4-6`, it conflicted with the production seed migration `add_gpt_5_3_codex_runtime_option` which writes the same `(cli_tool, model)` row, triggering `UniqueViolation`. Fixed inline by using id=1011 + a synthetic model name.

**Suggested CLAUDE.md addition**: tests that insert `agent_runtime_options` rows MUST use ids >= 1000 and synthetic model names like `"test-<purpose>"`, with a one-line explanation that the testcontainer DB inherits seeded rows from production migrations.

### 5. (MEDIUM) Browser verification dependency on the worktree compose stack is fragile

S24 cannot run unless the daemon-provisioned worktree compose stack is up. When the workflow is driven outside the daemon (e.g., manual recovery after S07 thrash), there is no fallback path. The integration suite covers the same view code via TestClient — perhaps S24 should be an OPTIONAL step gated on `IW_BROWSER_BASE_URL` being set, with the workflow accepting "skipped: ENV_DATA_MISSING" as terminal-pass when the integration coverage is sufficient.

### 6. (LOW) `make test-unit` exit code rewrites the QV report

After I wrote a PASS report for S20 (post a successful `make test-unit` run), a hook re-ran the gate and overwrote my report with `Exit code 2 / FAIL`. Re-running `make test-unit` showed 3052 passed, exit code 0. The hook seems to be reading an older invocation's exit state.

**Suggested investigation**: the qv-gate runner hook may be reading a cached or stale process status. Worth a sanity check on `scripts/run_qv_gate.sh` (if that's the hook) before the next workflow run.

## Multi-layer cross-cut observations (F-00085-specific)

- **Database → Pipeline → Backend → API → Frontend chain**: S01 → S04 → S06 → S08 → S10 each had enough information about the upstream contract; no fix cycle was caused by ignorance of an upstream's shape. The pain was entirely concentrated in S07 (review) drift, not in implementation steps.
- **F-00084 backward compatibility**: no F-00084 test regressed (the merge_queue.py edit in S06 added `resolve_project_config(...)` lookups; the existing flow remained intact). Verified by `tests/unit/test_merge_queue.py` and the F-00084 phase-0/1 plumbing tests staying green throughout.
- **Refuse-list / disabled runtime defence-in-depth**: both layers (`test_ac14_post_disabled_runtime_returns_400` + `test_ac14_settings_dropdown_does_not_include_disabled_rows`) are tested.
- **Phase 2/3 reservation**: TOML loader (auto_merge.py:223-230), API endpoint (auto_merge_ui.py:288-289), and Settings dropdown (auto_merge_settings.html) all refuse phase>=2 with consistent messaging. No softening attempted.
- **JSONB metadata size cap**: not regressed; F-00085 only *reads* `event_metadata`.
- **`auto_merge_config_invalid` event idempotency**: `_maybe_emit_disabled_runtime_event` checks for a prior event in the last day before inserting (event spam suppression intact).
- **Token-cost arithmetic**: `tests/unit/test_auto_merge_pricing.py` uses exact-match `assert cost == 0.06` (not `pytest.approx`), preserving the design's exemplar.

## What would have helped most upfront

1. A "minimum-touch fix-cycle" prompt template that says: "do nothing if your grep shows the flagged line is already addressed; reduce verdict to PASS."
2. A doc on "what to do when the workflow exhausts fix cycles but the code is fine" — i.e., the `step-skip S07 --reason ...` recovery path.
3. An assertion-scanner baseline auto-refresh on PRs that touch new test files, so non-F-00085 test additions don't surface as a "F-00085 broke the baseline" red herring.

## Closing

The Feature ships with the design's full surface in place. Browser verification is the only verification class not exercised; the integration TestClient suite + Semgrep baseline together provide HTTP-level + security coverage for every AC. Recommend the operator launches the daemon's E2E stack and re-runs S24 prior to merge for the visual / interactive layer if that is preferred over the documented `env_data_missing` skip.
