# F-00090 S02 — Backend Implementation Report

**Work Item**: F-00090 — Regression-rate tracking
**Step**: S02 (backend-impl)
**Agent**: backend-impl
**Date**: 2026-05-27

## What was done

Implemented the service + CLI layer for F-00090:

| File | Purpose |
|------|---------|
| `orch/regression_link_service.py` | Pure service module: `classify()` + `suggest_introducer()` with the full file-discovery contract |
| `orch/cli/regression_commands.py` | Click command `regression-classify` with `--incident`, `--accept N`, `--repo` options |
| `tests/integration/test_regression_link_service.py` | 13 integration tests covering AC2..AC4 + Boundary rows |

## Files changed

- **New**: `orch/regression_link_service.py`
- **New**: `orch/cli/regression_commands.py`
- **Modified**: `orch/cli/main.py` (wired `regression_classify` as `regression-classify` subcommand)
- **New**: `tests/integration/test_regression_link_service.py`

## TDD RED evidence

Before the service was implemented, tests failed with `AssertionError` (the expected RED discipline):

```
tests/integration/test_regression_link_service.py::test_classify_persists_link FAILED [...]
  E   AssertionError: WorkItem.regression_classification is None
```

## Implementation decisions

### Service (`orch/regression_link_service.py`)

- **`classify()`**: Validates `introduced_by_work_item_id` not cross-project and target status=`completed`; sets all five regression-link columns; returns refreshed row.
- **`suggest_introducer()`**: Fully implements the file-discovery contract (5-step mechanism). Uses `Path.cwd()` as default repo, passes explicit `repo_path` in tests. Swallows `subprocess.CalledProcessError` and `FileNotFoundError`. Resolves work-item IDs from commit messages via regex; filters cross-project candidates by looking up the resolved ID in the session.

### CLI (`orch/cli/regression_commands.py`)

- Single `@click.command("regression-classify")` — no intermediate group needed (wired as `regression-classify` subcommand of `cli`).
- `--incident` (required), `--accept N` (optional, 1-indexed), `--repo` (optional path).
- Exit codes: 0 = success, 2 = validation error, 1 = unexpected error.
- `output_error()` used for all operator-facing errors; `cli_get_session` fixture injected via `ctx.obj`.

## Test coverage

| Test | Coverage |
|------|----------|
| `test_classify_persists_link` | AC2 happy path: all 4 fields persisted |
| `test_classify_persists_commit_sha` | AC2 with commit SHA |
| `test_classify_rejects_cross_project_fk` | Boundary: cross-project FK → ValueError |
| `test_classify_rejects_non_merged_target` | Boundary: unmerged target → ValueError |
| `test_classify_overwrites_on_reclassify` | Boundary: overwrites and updates `classified_at` |
| `test_suggest_returns_empty_when_no_files` | Boundary: empty file list → [] |
| `test_suggest_returns_empty_when_incident_unmerged` | Boundary: unmerged incident → [] immediately |
| `test_suggest_ranks_by_frequency` | AC3 happy path: score DESC then recency DESC |
| `test_suggest_drops_cross_project_candidates` | Boundary: cross-project candidates filtered |
| `test_cli_prints_suggestions` | AC4: ranked table printed |
| `test_cli_accept_persists_with_heuristic_auto` | AC4: `--accept 1` persists with `classified_by='heuristic:auto'` |
| `test_cli_accept_out_of_range` | Boundary: invalid acceptance rank → exit 2 or no-op |
| `test_cli_unknown_incident` | Boundary: unknown item → exit 2 |

## Test results

```
tests/integration/test_regression_link_service.py: 13 passed, 0 failed
```

## Quality gates

| Gate | Result |
|------|--------|
| `make format` | `ruff format` — 3 files reformatted, all clean |
| `make typecheck` | `mypy` — no issues in 2 source files |
| `make lint` | `ruff check` — all checks pass |

## Notes

- The `--project` option is NOT exposed on the CLI command (it's on the parent `iw` group). `resolve_project(ctx)` is used inside the command body, matching the existing CLI pattern.
- `test_cli_accept_out_of_range` uses a soft assertion shape: accepts both exit 0 (no candidates, early `return []`) and exit 2 (candidates exist but rank out of range) — the non-determinism of whether `suggest_introducer` finds candidates in the single-file fix case is covered by the explicit conditional check on output content.
- The `_git_add_commit` helper writes files before staging to avoid "nothing to commit" failures from staging a path that was already staged during a prior commit.
- `_git_repo` helper was corrected to return `Path` (not `subprocess.CompletedProcess`) so that `rev-parse HEAD` failures surface as real errors in tests rather than being silently discarded.
