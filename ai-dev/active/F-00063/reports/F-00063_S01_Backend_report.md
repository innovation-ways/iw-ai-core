# F-00063 S01 — Backend Step Report

**Work item**: F-00063 — Stale Process & Migration Detector
**Step**: S01 (backend-impl)
**Status**: complete
**Branch**: main (developed directly per user instruction)

## Summary

Implemented the full backend foundation of the Stale Process & Migration Detector following TDD (RED → GREEN → REFACTOR). All staleness logic lives in the new `orch/staleness/` package; no DB schema changes. The dashboard self-restart helper script and the `iw-ai-core` seed entry in `projects.toml` are in place. The HTTP routes, HTML templates, and additional integration coverage are out of scope here — they belong to S03/S04/S07.

The step was executed in three sub-passes (turn budget exhaustion forced two hand-offs):

1. First backend-impl pass — wrote all 5 unit-test modules under `tests/unit/staleness/` (RED), then implemented `__init__.py`, `config.py`, `detection.py`, `git_lookup.py`.
2. Second backend-impl pass — implemented `alembic_check.py`, `service.py`, and the `parse_project_staleness` validation hook in `orch/daemon/project_registry.py`. All 83 staleness unit tests turned green.
3. Mechanical wrap-up (in-orchestrator) — created `bin/restart-dashboard.sh` (chmod +x, verified), seeded `projects.toml` with `daemon`/`dashboard` services + alembic block for `iw-ai-core` only, then a quality-fix-impl pass to clear 31 lint findings + 4 mypy errors.

## Files Touched

### New source files

- `orch/staleness/__init__.py` — package init; re-exports `compute_project_staleness` and `parse_project_staleness`.
- `orch/staleness/config.py` — dataclasses (`ServiceDetect`, `ServiceConfig`, `AlembicConfig`, `ProjectStalenessConfig`) and `parse_project_staleness(raw: dict) -> ProjectStalenessConfig`. Validates required fields; raises `ValueError` with clear messages on misconfiguration. Returns an empty result when neither key is present (the opt-out signal).
- `orch/staleness/detection.py` — detection engine: `find_running_pid` (port/pidfile/pgrep, with cwd cross-check inside `repo_root`), `find_running_container` (docker), `read_process_start_time` (parses `/proc/<pid>/stat` field 22 + `/proc/uptime` + `SC_CLK_TCK`), `read_container_start_time`, `is_cwd_under`. All shell-outs use `subprocess.run(check=False, capture_output=True, text=True, timeout=2.0)` and never raise — they return `None` and log on failure.
- `orch/staleness/git_lookup.py` — `find_commit_at(repo_root, ts)` runs `git log --first-parent main --before=@<epoch> -1 --format=%H`; `commits_since(repo_root, since_sha, watch_paths, ignore_paths)` runs `git log <sha>..main` with gitignore-style include pathspecs and `:(exclude)` exclusions; negated `!`-prefixed `watch_paths` translate to additional `:(exclude)` entries. 5s timeout; returns `[]` and logs on failure.
- `orch/staleness/alembic_check.py` — `check_alembic(repo_root, alembic_cfg_path, db_url_env) -> AlembicStatus`. Status enum: `up_to_date | stale | unreachable | no_config`. When `db_url_env` is `None`, the alembic subprocess inherits the parent environment unchanged (the iw-ai-core dogfood case). When set, the named env var is required (returns `unreachable` if missing) and is also exposed as `IW_ALEMBIC_DB_URL` for project env.py files that look for it. 10s timeout; psql connection failures → `unreachable` with stderr in `error`.
- `orch/staleness/service.py` — `compute_project_staleness(project_id) -> ProjectStalenessResult`. Re-reads `projects.toml` fresh on every call (Invariant 6: no caching). Looks up project by id; returns empty result if no services and no alembic. Per-service flow: detect → if not running, mark `not_running` and skip git lookup; if `hot_reload=True`, mark `hot_reload_skipped`; else compute start_time → start_commit → commits_since → `stale` or `up_to_date`. `is_stale = any(s.status == "stale") or alembic.status == "stale"`. `actions` derived from configured commands (`["restart", "start", "stop"]` subset).

### Modified source files

- `orch/daemon/project_registry.py` — added `_validate_staleness_config(project_id, entry)` invoked from `_build_project_config`. Best-effort sanity validation only: logs a warning and continues on parse failure. Does NOT change `ProjectConfig` shape and does NOT store the parsed staleness config — it is read on demand at compute time.

### New script

- `bin/restart-dashboard.sh` (executable, 0755) — detached helper used by the dashboard restart endpoint to re-spawn itself: sleeps 1s for HTTP response flush, sends SIGTERM to the old PID with a 10s grace window, then SIGKILL fallback, then `exec ./ai-core.sh dashboard start`. The caller is responsible for detaching via `setsid`/`nohup`.

### Config seed

- `projects.toml` — appended under `[projects.iw-ai-core]`:
  - `[[projects.iw-ai-core.services]]` for `daemon` (pidfile detect: `.daemon.pid`; restart: `./ai-core.sh daemon restart`; watch `orch/**` + `executor/**`).
  - `[[projects.iw-ai-core.services]]` for `dashboard` (pidfile detect: `.dashboard.pid`; restart: `bin/restart-dashboard.sh`; watch `dashboard/**` + `orch/**`).
  - `[projects.iw-ai-core.alembic]` with `config = "alembic.ini"`. `db_url_env` intentionally omitted (the iw-ai-core alembic env.py already resolves the URL via `orch.config.get_db_url()` from the inherited environment). No staleness blocks added for `innoforge`, `cv`, or `Podforger` — those are intentionally opt-out.

### New test files

- `tests/unit/staleness/__init__.py`
- `tests/unit/staleness/test_config.py` — parser covers all four `detect.type` values, missing-field validation, `hot_reload` flag, watch/ignore path lists, command optionality.
- `tests/unit/staleness/test_detection.py` — `/proc` reads via `tmp_path`-backed mock filesystem, mocked `ss`/`docker`/`pgrep` outputs, cwd-outside-repo rejection, multiple-match warning, stale pidfile, dead-PID handling.
- `tests/unit/staleness/test_git_lookup.py` — temporary git repo created via `subprocess` in fixture; verifies `find_commit_at` picks the correct commit and the path-filtered log honours include + `:(exclude)` patterns.
- `tests/unit/staleness/test_alembic_check.py` — current vs heads comparison with mocked alembic; multiple unapplied revisions list; current==heads → `up_to_date`; missing env var → `unreachable`; psql connection refused → `unreachable`.
- `tests/unit/staleness/test_service.py` — orchestrator behavior: missing config returns empty result; stale service produces commits list; alembic stale produces revisions list; combined ordering; `hot_reload=True` short-circuits to `hot_reload_skipped`; `is_stale` aggregation.

## Verification

| Gate | Command | Result |
|------|---------|--------|
| Staleness unit tests | `uv run pytest tests/unit/staleness/ -q` | **83 passed** |
| Full unit suite | `make test-unit` | **1842 passed, 2 skipped** |
| Lint | `make lint` | **exit 0** |
| Typecheck | `make typecheck` | **exit 0** (188 source files) |

## Notes

- **TDD compliance**: all five test modules were written before the corresponding implementations. The two impl files written in the second pass (`alembic_check.py`, `service.py`) had their test files pre-written by the first pass, so they were genuinely RED-before-GREEN.
- **Quality cleanup**: 31 lint findings + 4 mypy errors were resolved in a quality-fix pass, all confined to `orch/staleness/` and `tests/unit/staleness/`. No pre-existing files outside the staleness package were modified during cleanup.
- **Pre-existing uncommitted work in the tree was left untouched** per user instruction (OSS-publish skill edits, `dashboard/routers/oss.py`, `orch/oss/*`, `orch/db/migrations/versions/bd4ed52cad71_i_00042_add_batch_item_status_labels.py`, `tests/integration/test_batch_item_status_enum_drift.py`, several `tests/integration/test_oss_*.py`).
- **`ai-core.sh` not modified**: existing `dashboard start/stop/restart` semantics are intact. The new `bin/restart-dashboard.sh` is invoked directly by the dashboard restart endpoint (S03) and shells out to `./ai-core.sh dashboard start` for the respawn.
- **No DB schema changes**: per design, the feature is fully stateless and live-computed. No alembic revision was generated.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "F-00063",
  "completion_status": "complete",
  "files_changed": [
    "orch/staleness/__init__.py",
    "orch/staleness/config.py",
    "orch/staleness/detection.py",
    "orch/staleness/git_lookup.py",
    "orch/staleness/alembic_check.py",
    "orch/staleness/service.py",
    "orch/daemon/project_registry.py",
    "bin/restart-dashboard.sh",
    "projects.toml",
    "tests/unit/staleness/__init__.py",
    "tests/unit/staleness/test_config.py",
    "tests/unit/staleness/test_detection.py",
    "tests/unit/staleness/test_git_lookup.py",
    "tests/unit/staleness/test_alembic_check.py",
    "tests/unit/staleness/test_service.py"
  ],
  "tests_passed": true,
  "test_summary": "83 staleness unit tests passed; full unit suite 1842 passed, 2 skipped",
  "blockers": [],
  "notes": "Step ran across two backend-impl passes plus an orchestrator-driven mechanical wrap-up (script + projects.toml seed + report) and a quality-fix-impl pass for lint/typecheck. All gates (lint, typecheck, unit tests) green. No DB migration written — feature is stateless by design."
}
```
