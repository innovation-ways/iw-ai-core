# I-00107: `daemon reload` (SIGHUP) does not apply `.iw-orch.json` changes for an already-running project

**Type**: Issue
**Severity**: Medium
**Created**: 2026-05-22
**Reported By**: sergio (during BATCH-00127 overlap-gate widening, 2026-05-22)
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. **This item adds no migration** — it changes in-memory daemon state handling only; no schema or model changes.

## Description

`./ai-core.sh daemon reload` (SIGHUP) is documented as the way to re-sync a managed project's `.iw-orch.json` into the running daemon. In practice, for an already-running project whose `projects.toml` entry is unchanged, edits to `.iw-orch.json` are silently ignored — the in-memory `ProjectConfig` and `BatchManager` keep using the old values until the daemon is fully restarted. Operators see `"SIGHUP received — triggering project reload"` and `"projects.toml changed — reloading"` in the log and reasonably believe the new config is live, when it is not.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. The daemon is the single-threaded polling loop that owns batch orchestration; `BatchManager.project_config` is the in-memory `ProjectConfig` that `_process_batch` reads for `overlap_block_patterns`, `overlap_allow_patterns`, `max_parallel`, `fix_cycle_max`, browser-verification settings, and the per-project test/quality command catalog. `CLAUDE.md` says: *"the daemon's project_registry.py syncs it [projects.toml + per-project .iw-orch.json] to the DB on SIGHUP (`./ai-core.sh daemon reload`)"* — the bug is that the in-memory `BatchManager`'s `project_config` is NOT refreshed even though the registry re-reads `.iw-orch.json`.

## Steps to Reproduce

1. Pick a managed, enabled project — e.g. `iw-ai-core`.
2. Edit the project's `.iw-orch.json` — for example, append a new glob to `overlap_gate.allow_on_overlap`, or change `max_parallel`.
3. Do NOT touch `projects.toml`.
4. Run `./ai-core.sh daemon reload`. The log shows `SIGHUP received — triggering project reload` followed by `projects.toml changed — reloading`.
5. Wait for the next poll cycle (≤60 s) and observe `item_held_for_scope` events or any other behaviour governed by the changed setting.

**Expected**: The daemon applies the new `.iw-orch.json` settings on the next poll cycle. For the overlap-gate example, the new `allow_on_overlap` globs release items that were previously held; for `max_parallel`, new launches respect the new cap.

**Actual**: The daemon keeps using the OLD in-memory `ProjectConfig`. `item_held_for_scope` events continue to cite the old-flagged globs. The only way to apply the change is `./ai-core.sh daemon restart` — which briefly pauses orchestration across **all** managed projects.

## Root Cause Analysis

The reload path has a gap between *parsing* the new config and *installing* it into the running daemon.

**`orch/daemon/project_registry.py:598-643` — `ProjectRegistry.reload()`** correctly re-reads each project's `.iw-orch.json` via `try_load_projects_toml` → `load_projects_toml` → `_build_project_config` (line 143) → `_parse_overlap_gate` (line 335). The returned `new_projects` dict contains **fresh** `ProjectConfig` objects with the updated overlap patterns / max_parallel / browser_verification.

However, the returned `changes` dict is computed purely from `projects.toml`-level facts (lines 623-640):

```python
for pid in all_ids:
    if pid not in old and pid in new_projects:
        changes[pid] = "added"
    elif pid in old and pid not in new_projects:
        changes[pid] = "removed"
    elif pid in old and pid in new_projects:
        was_enabled = old[pid].enabled
        is_enabled = new_projects[pid].enabled
        if was_enabled and not is_enabled:
            changes[pid] = "disabled"
        elif not was_enabled and is_enabled:
            changes[pid] = "enabled"
        else:
            changes[pid] = "unchanged"
```

For an existing, enabled project whose `projects.toml` entry is unchanged, `changes[pid] = "unchanged"` — regardless of whether `.iw-orch.json` content changed. **The change-detection has no notion of `.iw-orch.json` content drift.**

**`orch/daemon/main.py:621-655` — `Daemon._reload_projects_if_stale()`** then iterates `changes.items()` and only takes action on four change types: `"added"`, `"removed"`, `"disabled"`, `"enabled"`. There is no `"unchanged"` branch — the fresh `ProjectConfig` for an `"unchanged"` project is discarded. Even worse, only the `"added"` branch (line 633) rebuilds `self.managers[project_id] = BatchManager(...)`; `"disabled"`/`"enabled"` update `self.projects[project_id]` but leave `self.managers[project_id]` (the `BatchManager` that holds the live `project_config`) pointing at the **old** ProjectConfig.

Downstream, `_process_batch` (`orch/daemon/batch_manager.py:456-461`) reads `cfg = self.project_config` and uses `cfg.overlap_block_patterns` / `cfg.overlap_allow_patterns`. Because `self.project_config` is the stale object, the gate keeps applying the old patterns.

**Observed evidence (this session, 2026-05-22 ~15:49–15:50 UTC)**: edited `.iw-orch.json` `overlap_gate.allow_on_overlap` to add `**/*.md`, `skills/**`, `.claude/skills/**`, `ai-dev/**`. Ran `./ai-core.sh daemon reload` (log: `projects.toml changed — reloading` at 15:49:04 UTC). The next poll cycle at 15:50:04 UTC still held `CR-00072/73/74/F-00088` on the old-flagged globs (`item_held_for_scope` events with the same `conflicting_globs` list as before). A `./ai-core.sh daemon restart` rebuilt the `BatchManager` from a fresh `ProjectConfig` — the next cycle released the held items and emitted `item_overlap_allowed_by_policy`.

Note: `is_stale()` (`project_registry.py:591-596`) only tracks `projects.toml`'s mtime, not `.iw-orch.json`'s. SIGHUP forces `_mtime=0.0` so the reload path always runs; this is not the bug. The bug is purely in the change-detection + installation step that comes after.

## Affected Components

| Component | Impact |
|-----------|--------|
| `orch/daemon/project_registry.py` (`ProjectRegistry.reload()`) | `changes` dict never reports `.iw-orch.json` content drift — produces `"unchanged"` for projects whose effective `ProjectConfig` actually differs |
| `orch/daemon/main.py` (`Daemon._reload_projects_if_stale()`) | No handler for the (currently `"unchanged"`) drift case; even `disabled`/`enabled` only update `self.projects` and not `self.managers`, leaving the `BatchManager` with stale `project_config` |
| Tests (unit) | No test guards the contract that SIGHUP refreshes `.iw-orch.json`-sourced settings into the running daemon — the regression slipped silently |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | (1) Add a `"changed"` (or equivalent) entry to `ProjectRegistry.reload()`'s `changes` dict when a project's effective `ProjectConfig` differs from the previously held one. (2) In `Daemon._reload_projects_if_stale()`, handle the new case AND fix the `disabled`/`enabled` cases so they also refresh `self.managers[pid]`. Refresh path: update `self.projects[pid]` to the new ProjectConfig and rebuild `self.managers[pid] = BatchManager(pid, new_cfg, self._session_factory, self.config)`. Emit a `daemon_event` (`project_config_reloaded` or similar) for observability. | — |
| S02 | code-review-impl | Review S01 | — |
| S03 | tests-impl | Reproduction + regression tests (unit, no DB). Three primary tests, listed under TDD Approach. | — |
| S04 | code-review-impl | Review S03 | — |
| S05 | code-review-final-impl | Cross-cutting final review | — |
| S06..S12 | qv-gate | lint, format-check, type-check, arch-check, security-sast, unit-tests, integration-tests | — |
| S13 | self-assess-impl | Post-execution self-assessment (project has `self_assess = true`) | — |

Agent slugs: `backend-impl`, `tests-impl`, `code-review-impl`, `code-review-final-impl`, `qv-gate`, `self-assess-impl`. No `frontend-tests` gate (no UI change), no `migration-check` (no migration), no `qv-browser` (backend-only).

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: No migration. Pure in-memory daemon-state fix.

### Code Changes

- **Files to modify**:
  - `orch/daemon/project_registry.py` — extend `reload()` to detect `.iw-orch.json` content drift and report a new change type (e.g. `"changed"`).
  - `orch/daemon/main.py` — extend `_reload_projects_if_stale()` to handle the new change type AND to rebuild `self.managers[pid]` for `disabled`/`enabled` cases too.
- **New test files**:
  - `tests/unit/daemon/test_daemon_config_reload.py` — drives `ProjectRegistry.reload()` and `Daemon._reload_projects_if_stale()` against tmp_path-backed `projects.toml` + `.iw-orch.json` fixtures.
- **Nature of change**: Behavioural fix in daemon-reload control flow. No public API change. The added `"changed"` change-type is internal to `ProjectRegistry.reload()` ↔ `Daemon._reload_projects_if_stale()` and is not part of any persisted contract.

## File Manifest

All files for this work item live under `ai-dev/active/I-00107/`:

| File | Type | Purpose |
|------|------|---------|
| `I-00107_Issue_Design.md` | Design | This document |
| `I-00107_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/I-00107_S01_Backend_prompt.md` | Prompt | S01 backend fix |
| `prompts/I-00107_S02_CodeReview_prompt.md` | Prompt | S02 review of S01 |
| `prompts/I-00107_S03_Tests_prompt.md` | Prompt | S03 reproduction + regression tests |
| `prompts/I-00107_S04_CodeReview_prompt.md` | Prompt | S04 review of S03 |
| `prompts/I-00107_S05_CodeReview_Final_prompt.md` | Prompt | S05 cross-agent final review |
| `prompts/I-00107_S13_SelfAssess_prompt.md` | Prompt | S13 self-assessment |

Reports are created during execution in `ai-dev/active/I-00107/reports/`.

## Test to Reproduce

Test-file location: `tests/unit/daemon/test_daemon_config_reload.py`. This is a **unit** test — `ProjectRegistry` and `Daemon._reload_projects_if_stale()` operate on in-memory state and tmp-path-backed files; no DB is involved. (Existing tests under `tests/unit/daemon/` follow this pattern — e.g. `test_agent_subprocess_env.py`.) The reproduction test fails before the fix because the change-type for a `.iw-orch.json` content edit is `"unchanged"` and no manager rebuild happens.

```python
def test_i00107_reload_rebuilds_batch_manager_when_iw_orch_json_changes(tmp_path):
    """Reproduction: editing a project's .iw-orch.json and triggering reload
    must result in the BatchManager being rebuilt with the new ProjectConfig.

    Fails before fix: change-type is 'unchanged' and self.managers[pid] is the
    same object reference both before and after reload.
    """
    # Arrange: projects.toml with one enabled project pointing at a repo dir
    # that contains an initial .iw-orch.json with allow_on_overlap=["tests/**"].
    projects_toml = tmp_path / "projects.toml"
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_projects_toml(projects_toml, project_id="demo", repo_root=str(repo))
    _write_iw_orch_json(repo, allow_on_overlap=["tests/**"])

    daemon = _build_daemon(projects_toml)
    daemon._reload_projects_if_stale()  # initial load
    pre_manager = daemon.managers["demo"]
    pre_allow = list(pre_manager.project_config.overlap_allow_patterns)

    # Act: edit ONLY .iw-orch.json — projects.toml is untouched.
    _write_iw_orch_json(repo, allow_on_overlap=["tests/**", "**/*.md"])
    daemon.registry._mtime = 0.0  # simulate SIGHUP
    daemon._reload_projects_if_stale()

    # Assert: the BatchManager has been rebuilt with the new ProjectConfig.
    post_manager = daemon.managers["demo"]
    assert post_manager is not pre_manager, (
        "I-00107: reload must replace the BatchManager when .iw-orch.json changes"
    )
    post_allow = list(post_manager.project_config.overlap_allow_patterns)
    assert "**/*.md" in post_allow and "**/*.md" not in pre_allow, (
        "I-00107: overlap_allow_patterns must reflect the edited .iw-orch.json"
    )
```

## Acceptance Criteria

### AC1: `.iw-orch.json` content drift triggers a `BatchManager` rebuild

```
Given a managed, enabled project whose projects.toml entry is unchanged
And whose .iw-orch.json has been edited (e.g. overlap_gate.allow_on_overlap)
When the daemon receives SIGHUP and runs _reload_projects_if_stale()
Then ProjectRegistry.reload() reports a non-"unchanged" change for that project
And self.managers[project_id] is rebuilt with a ProjectConfig that reflects the new .iw-orch.json
And self.projects[project_id] points at the same fresh ProjectConfig
```

### AC2: Next poll cycle uses the new config

```
Given AC1 has fired
When the next _process_batch cycle runs for that project
Then it reads overlap_block_patterns / overlap_allow_patterns / max_parallel / fix_cycle_max
     from the new ProjectConfig (not the stale one)
```

### AC3: `disabled`/`enabled` toggles also refresh the BatchManager

```
Given a managed project whose projects.toml `enabled` flag flips from false → true (or vice versa)
When the daemon reloads
Then self.managers[project_id] is rebuilt to reflect the new state
(not only self.projects[project_id], as today)
```

### AC4: Observability — a daemon event records the refresh

```
Given AC1 or AC3 fires
When the manager is rebuilt
Then a DaemonEvent with event_type="project_config_reloaded" (or equivalent) is written,
     with metadata identifying the project_id and a short summary of what changed
```

### AC5: Regression test exists

```
Given the fix is applied
When the test suite runs
Then tests/unit/daemon/test_daemon_config_reload.py::test_i00107_reload_rebuilds_batch_manager_when_iw_orch_json_changes passes,
     along with the AC3 toggle test and the AC4 event-emission test
```

## Regression Prevention

- Unit test pins the contract that **editing `.iw-orch.json` + SIGHUP** rebuilds the in-memory `BatchManager` with the new `ProjectConfig`. Any future refactor of `ProjectRegistry.reload()` or `Daemon._reload_projects_if_stale()` that drops the content-drift detection will break this test.
- A second unit test pins the `disabled`/`enabled` path — also refreshes `self.managers[pid]`, preventing the silent "self.projects updated but self.managers stale" sub-bug from regressing.
- A third unit test pins the `project_config_reloaded` event emission — gives operators a positive signal in the dashboard that the reload actually applied.
- No structural changes (e.g. extracting a `RefreshManager` class) — the fix is contained to the two existing functions, keeping the diff small and the risk profile low.

## Dependencies

- **Depends on**: None.
- **Blocks**: None. Worked around in BATCH-00127 by performing a full daemon restart.

## Impacted Paths

- `orch/daemon/main.py`
- `orch/daemon/project_registry.py`
- `tests/unit/daemon/test_daemon_config_reload.py`

## TDD Approach

- **Reproducing test**: `tests/unit/daemon/test_daemon_config_reload.py::test_i00107_reload_rebuilds_batch_manager_when_iw_orch_json_changes` — fails before fix (manager is same object reference, allow_patterns unchanged), passes after.
- **Unit tests** (file: `tests/unit/daemon/test_daemon_config_reload.py`):
  - `test_i00107_reload_rebuilds_batch_manager_when_iw_orch_json_changes` — reproduction (above). Asserts both manager-rebuild and new `overlap_allow_patterns` propagation.
  - `test_reload_unchanged_when_iw_orch_json_is_identical` — write `.iw-orch.json`, reload, do NOT edit, reload again. Assert the second reload does NOT rebuild the manager (no needless churn) — i.e. detection is content-based, not "always rebuild".
  - `test_reload_rebuilds_manager_on_enabled_toggle` — flip `enabled` in `projects.toml` from `false` → `true`. Assert `self.managers[pid]` is rebuilt (not only `self.projects[pid]`).
  - `test_reload_emits_project_config_reloaded_event` — patch `_emit_event` (or its DB path) and assert one `project_config_reloaded` (or equivalent) event is emitted, with `entity_id` = the project id and metadata naming the drifted field(s).
  - `test_reload_does_not_refresh_when_only_projects_toml_unchanged_iw_orch_json_unparseable` — write a malformed `.iw-orch.json`, reload, assert the manager is NOT rebuilt and a warning is logged (the existing `try_load_projects_toml` policy — preserve last-known-good — applies the same way to per-project parse failures).

**Targeted run** (per `tests/CLAUDE.md`): `uv run pytest tests/unit/daemon/test_daemon_config_reload.py -v`. Do NOT run `make test-unit` from inside the Tests step — that's the QV gate's job.

## Notes

- Severity is **Medium**: silent operational gap that costs real debugging time when operators rely on the documented reload behaviour. No data loss, no crash, restart is a known workaround — so not High. Already cost ~1h of debugging in this session (BATCH-00127), enough to outweigh Low.
- The chosen fix direction is **make reload actually apply it** (vs. doc-only "restart required"). Live reload matches what `CLAUDE.md` and `./ai-core.sh` help text already promise; flipping the docs to admit the limitation would still leave the operator with the more disruptive restart as the only path.
- The fix rebuilds a `BatchManager` mid-run. The `BatchManager` is effectively stateless per poll cycle — `_process_batch` re-queries the DB each tick — and we already observed a clean rebuild-and-reattach on the live `daemon restart` performed in this session (the running `CR-00075` worktree was re-attached without disruption). Review S05 (CodeReview_Final) should confirm no in-flight state is dropped by the rebuild.
- The `iw_core_instance` row, `merge_queue` state, and any other DB-backed state are unaffected — only the in-memory `BatchManager.project_config` snapshot is replaced.
- A small follow-up improvement (out of scope for this fix): `is_stale()` (`project_registry.py:591-596`) only watches `projects.toml`'s mtime, so an operator who edits `.iw-orch.json` without SIGHUP sees the daemon never reload. SIGHUP forces the reload path so this isn't blocking, but watching the per-project `.iw-orch.json` mtimes too would let `is_stale()` return True on bare edits — file as a follow-up CR if useful.
