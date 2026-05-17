# I-00088: Auto-merge health probe always fails — CLI-shape mismatch with step_executor.sh

**Type**: Issue
**Severity**: Medium
**Created**: 2026-05-17
**Reported By**: sergio (dashboard chip showed `● down` for every project)
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures used by the new integration test are exempt.

## ⛔ Migrations: agents generate, daemon applies

No migrations are added, modified, or removed by this incident.

## Description

The dashboard's auto-merge resolver chip (`P1 opencode/minimax/MiniMax-M2.7 0 attempts ● down`) shows `● down` for every project even though the underlying runtime has never been exercised. The 5-minute health probe that backs this chip dies inside `executor/step_executor.sh` and writes `runtime_reachable=false` to every `auto_merge_health_probe` event. The result is a false alarm: operators cannot tell a real runtime outage from this permanent failure mode, and the only signal we currently have for the auto-merge resolver runtime is broken.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules — in particular the daemon's role (`orch/daemon/`), the executor's contract (`executor/CLAUDE.md`), and the testing rules in `tests/CLAUDE.md` (no live-DB connection, testcontainers only, no mocking of integration-test DBs).

## Steps to Reproduce

1. Bring up the platform: `./ai-core.sh start`.
2. Wait at least one probe interval (5 minutes by default).
3. Open the dashboard at `http://localhost:9900/` and pick any registered project.
4. Look at the auto-merge chip in the page header.
5. Click the chip — the Auto-merge view opens with no real verdicts, just permanent `down` health.
6. Inspect `daemon_events` directly: every `auto_merge_health_probe` row has `metadata->>'runtime_reachable' = 'false'` and `metadata->>'error'` starting with `ERROR: Worktree not found or invalid: --agent`.

**Expected**: The probe invokes the configured runtime (`opencode` / `claude`) with a one-token prompt, sees `OK`, and records `runtime_reachable=true`. The chip reads `● healthy` whenever the runtime is reachable; it only reads `● down` when the failure rate over the last 24 h exceeds `health_failure_rate_threshold_per_day`.

**Actual**: Every probe across every project records `runtime_reachable=false`. The chip reads `● down` permanently. The runtime itself is never contacted.

## Root Cause Analysis

`orch/daemon/auto_merge_health.py:47-62` invokes `executor/step_executor.sh` with **flag-style** arguments:

```python
result = subprocess.run(
    [
        "/bin/bash",
        str(_EXECUTOR_PATH / "step_executor.sh"),
        "--step-type", "auto_merge_resolve",
        "--agent", resolved.cli_tool,
        "--model", resolved.model,
    ],
    input=PROBE_PROMPT,
    ...
)
```

But `executor/step_executor.sh:35-39` reads **positional** arguments:

```bash
ITEM_ID="${1:?Usage: step_executor.sh <item_id> <step_id> <worktree_path> [<cli_tool>] [<project_repo_root>]}"
STEP_ID="${2:?step_id is required}"
WORKTREE_PATH="${3:?worktree_path is required}"
```

So when the probe runs, the script reads `ITEM_ID="--step-type"`, `STEP_ID="auto_merge_resolve"`, `WORKTREE_PATH="--agent"`, then validates the worktree at `executor/step_executor.sh:52-55` and exits with code 2 emitting `ERROR: Worktree not found or invalid: --agent` to stderr. The probe captures that string, writes `runtime_reachable=false` to `daemon_events.metadata`, and 5 minutes later does the exact same thing. There is no scenario in which the current call shape can ever succeed.

The probe should never have called `step_executor.sh` to begin with: that script's job is to run a full work-item step inside a worktree (item id, step id, worktree path, agent commands, DB writes, log capture). The probe needs none of that — it just needs a 1-token round-trip to the configured runtime. The **canonical one-shot helper** for that case already exists at `executor/step_executor_lib.sh:608-628` (`_run_agent_oneshot`), exposed via the direct-dispatch block at `step_executor_lib.sh:635-652` as:

```bash
bash step_executor_lib.sh auto_merge_resolve <agent> <model>   # prompt on stdin → output on stdout
```

This helper is the same code path the real auto-merge resolver uses (`orch/daemon/auto_merge.py:717-736`). The probe should mirror that invocation so the two cannot drift: if `_run_agent_oneshot` ever migrates from `claude --print` to `claude -p`, the probe inherits the change for free, and a "healthy" probe verdict always implies the resolver's call path is actually reachable.

Why the existing tests missed it: `tests/unit/test_auto_merge_health.py` mocks `subprocess.run` itself (`patch("orch.daemon.auto_merge_health.subprocess.run")`) and asserts on the *response*, not the *argv*. The CLI-shape mismatch is invisible at the seam where the existing tests stub.

## Affected Components

| Component | Impact |
|-----------|--------|
| `orch/daemon/auto_merge_health.py` (probe) | Every invocation fails before reaching the runtime. |
| Dashboard auto-merge chip (`dashboard/templates/fragments/auto_merge_status_chip.html`) | Reads `health_state="down"` from the aggregator and renders permanently red. |
| Operator confidence | A real outage of opencode/MiniMax cannot be distinguished from this bug. |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | Backend (`backend-impl`) | Replace `step_executor.sh` invocation in `maybe_run_probe` with `bash step_executor_lib.sh auto_merge_resolve <cli_tool> <model>` — mirror the pattern at `orch/daemon/auto_merge.py:717-736`. Pass the probe prompt on stdin; pass `WORKTREE_PATH=<dummy>` + a sanitised `PATH` in env (same as the resolver). Keep event-metadata shape unchanged. Do NOT touch any file in `executor/`. | — |
| S02 | CodeReview_Backend (`code-review-impl`) | Review S01: argv shape matches `auto_merge.py`'s lib-script invocation (`bash`, `step_executor_lib.sh`, `auto_merge_resolve`, `<cli_tool>`, `<model>`); env is sanitised; event-metadata shape preserved; no scope creep into `executor/`. | — |
| S03 | Tests (`tests-impl`) | (a) Update `tests/unit/test_auto_merge_health.py` to assert on the **command list passed to subprocess.run** — argv must include `step_executor_lib.sh`, `auto_merge_resolve`, `resolved.cli_tool`, and `resolved.model`. (b) Add `tests/integration/test_auto_merge_health_runtime.py` that drops a tiny fake `opencode` (or `claude`) shim on `PATH`, runs the real probe code through the real `step_executor_lib.sh`, and asserts the probe records `runtime_reachable=true` and that the shim saw the prompt + model. | — |
| S04 | CodeReview_Tests (`code-review-impl`) | Review S03: I003 semantic-strength check, the test would have failed against the pre-fix code (the original bug), RED evidence is captured. | — |
| S05 | CodeReview_Final (`code-review-final-impl`) | Cross-step global review: AC traceability, scope adherence, no regression in the existing `auto_merge_health` API surface. | — |
| S06..S10 | QV gates | lint, format-check, typecheck, unit-tests, integration-tests | — |
| S11 | self-assess (`self-assess-impl`) | Project has `self_assess = true` in `projects.toml` — must be the LAST step. | — |

No `Database` step → no migration lock needed. No frontend / template / pipeline / browser-verification steps (user confirmed backend-only verification; chip rendering is unchanged).

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None

### Code Changes

- **Files to modify**: `orch/daemon/auto_merge_health.py`, `tests/unit/test_auto_merge_health.py`
- **Files to add**: `tests/integration/test_auto_merge_health_runtime.py`
- **Nature of change**: Replace one subprocess call site (point at `step_executor_lib.sh` in `auto_merge_resolve` mode, mirroring `orch/daemon/auto_merge.py`); rewrite existing mocked-subprocess unit tests to assert on argv shape; add a real-subprocess integration test against a fake CLI on PATH that runs through the real lib script.

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `I-00088_Issue_Design.md` | Design | This document |
| `I-00088_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions |
| `prompts/I-00088_S01_Backend_prompt.md` | Prompt | S01 backend fix |
| `prompts/I-00088_S02_CodeReview_Backend_prompt.md` | Prompt | S02 review of S01 |
| `prompts/I-00088_S03_Tests_prompt.md` | Prompt | S03 unit + integration tests |
| `prompts/I-00088_S04_CodeReview_Tests_prompt.md` | Prompt | S04 review of S03 |
| `prompts/I-00088_S05_CodeReview_Final_prompt.md` | Prompt | S05 final review |
| `prompts/I-00088_S11_SelfAssess_prompt.md` | Prompt | S11 self-assessment |

## Test to Reproduce

The new integration test lives at `tests/integration/test_auto_merge_health_runtime.py` and uses a **real subprocess** against a fake CLI script — that is the only way to catch the original shape mismatch (mocking `subprocess.run` itself is what hid the bug in the first place). The fake CLI is named `opencode` (or `claude`) and dropped into a `tmp_path` directory that is prepended to `PATH`; the probe shells out to `bash step_executor_lib.sh auto_merge_resolve opencode <model>` (mirroring `auto_merge.py`), and the lib script's `_run_agent_oneshot` resolves `opencode` via the patched `PATH`, hitting the fake.

```python
# tests/integration/test_auto_merge_health_runtime.py
# This test should FAIL against the pre-fix code (the probe shells out to
# step_executor.sh which exits 2 with "Worktree not found or invalid: --agent")
# and PASS after the fix (the probe shells out to step_executor_lib.sh in
# auto_merge_resolve mode, which invokes the fake CLI on PATH, which prints OK).
from __future__ import annotations

import os
import stat
from pathlib import Path
from unittest.mock import MagicMock, patch

from orch.daemon.auto_merge import AutoMergeConfig
from orch.daemon.auto_merge_health import maybe_run_probe


def _write_fake_cli(dir_: Path, name: str, capture_file: Path) -> Path:
    """Write a tiny CLI shim that records its argv + stdin then prints OK."""
    script = dir_ / name
    script.write_text(
        "#!/usr/bin/env bash\n"
        f'echo "argv: $*" > "{capture_file}"\n'
        f'cat >> "{capture_file}"\n'
        'echo "OK"\n'
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return script


def test_probe_invokes_runtime_via_lib_script_and_records_reachable(
    tmp_path: Path, monkeypatch
) -> None:
    capture = tmp_path / "captured.txt"
    _write_fake_cli(tmp_path, "opencode", capture)
    # The lib script's _run_agent_oneshot resolves `opencode` via PATH;
    # prepend tmp_path so the fake shim is found before any real binary.
    # NOTE: the probe sanitises PATH inside subprocess env (mirroring
    # auto_merge.py); the implementation MUST include tmp_path in that
    # sanitised PATH for this test to pass. The probe achieves this by
    # passing the *current* PATH through (or by appending /usr/local/bin
    # etc. to the inherited PATH) — see S01 prompt.
    monkeypatch.setenv("PATH", f"{tmp_path}:{os.environ['PATH']}")

    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.return_value = None  # no prior probe
    with patch("orch.daemon.auto_merge_health.resolve_project_config") as resolve:
        resolve.return_value = MagicMock(
            phase=1, cli_tool="opencode", model="minimax/MiniMax-M2.7"
        )
        maybe_run_probe(db, "proj", AutoMergeConfig.defaults())

    payload = db.add.call_args[0][0].event_metadata
    assert payload["runtime_reachable"] is True, payload  # would FAIL pre-fix
    captured = capture.read_text()
    assert "minimax/MiniMax-M2.7" in captured  # the model reached the runtime
    assert "Reply with the single word OK" in captured  # the prompt reached the runtime
```

The unit-test update under `tests/unit/test_auto_merge_health.py` is described in the Tests prompt; in short: replace the response-shape assertions with argv-shape assertions (`argv` contains `step_executor_lib.sh`, `auto_merge_resolve`, the resolved `cli_tool`, and the resolved `model`) so a future regression of the bug is caught at the unit level too.

## Acceptance Criteria

### AC1: Bug is fixed

```
Given the daemon is running and a project has auto-merge phase=1
When 5 minutes elapse and the health probe fires
Then the probe invokes step_executor_lib.sh in auto_merge_resolve mode
     (mirroring orch/daemon/auto_merge.py), the lib script invokes the
     configured runtime (opencode or claude) and reads OK on stdout,
     the probe records runtime_reachable=true,
     and the chip flips to "● healthy" once the 24h failure window ages past
     the threshold of historical failures.
```

### AC2: Regression test exists

```
Given the fix is applied
When `make test-integration` runs
Then tests/integration/test_auto_merge_health_runtime.py passes and would
     have failed against the pre-fix code (CLI-shape mismatch — step_executor.sh
     exits 2 before any runtime is invoked).
```

### AC3: Unit tests assert on argv shape

```
Given the fix is applied
When `make test-unit` runs
Then tests/unit/test_auto_merge_health.py asserts that the command list
     passed to subprocess.run contains "step_executor_lib.sh",
     "auto_merge_resolve", the resolved cli_tool, and the resolved model —
     not just that runtime_reachable is True.
```

## Regression Prevention

- The new integration test (`test_auto_merge_health_runtime.py`) runs the **real** `subprocess.run` through the real `step_executor_lib.sh` against a fake CLI on `PATH`. Any future change that breaks the argv shape — at the probe layer, at the lib-script dispatch, or at `_run_agent_oneshot` — will fail this test.
- The updated unit tests assert on the argv passed to `subprocess.run`, so the probe→lib-script shape (`bash step_executor_lib.sh auto_merge_resolve <cli_tool> <model>`) is locked at the unit-test level too.
- The probe and the real auto-merge resolver (`orch/daemon/auto_merge.py`) now share the same invocation pattern (`step_executor_lib.sh auto_merge_resolve <agent> <model>`). They cannot drift: if the lib script's `_run_agent_oneshot` migrates from `claude --print` to `claude -p`, both inherit the change atomically.
- The probe no longer shares a code path with `step_executor.sh`, so changes to that script's positional-argument layout can't break the health probe.

## Dependencies

- **Depends on**: None
- **Blocks**: None

## Impacted Paths

- `orch/daemon/auto_merge_health.py`
- `tests/unit/test_auto_merge_health.py`
- `tests/integration/test_auto_merge_health_runtime.py`

## TDD Approach

- **Reproducing test**: `tests/integration/test_auto_merge_health_runtime.py::test_probe_invokes_runtime_via_lib_script_and_records_reachable` — uses a fake `opencode` shim on PATH; would fail pre-fix because the probe shells out to `step_executor.sh` (the wrong script) which exits 2 without ever invoking the runtime.
- **Unit tests**: `tests/unit/test_auto_merge_health.py` — argv-shape assertions for the success, subprocess-error, timeout, and non-blocking RuntimeError paths. Verify the command list passed to `subprocess.run` contains `"step_executor_lib.sh"`, `"auto_merge_resolve"`, the resolved `cli_tool`, and the resolved `model`.
- **Integration tests**: the new `test_auto_merge_health_runtime.py` covers the end-to-end shape with a real `subprocess.run` through the real `step_executor_lib.sh` against a fake CLI script on PATH. Add both a success-path test (shim prints `OK`) and a failure-path test (shim exits non-zero).

## Notes

- **Post-merge chip lag**: even after the fix lands and probes start succeeding, the chip will continue to read `● down` until the 24h failure-rate window ages past the threshold (because the historical failing probe events are still in `daemon_events`). This is expected behaviour and not a fix-time concern. An operator who wants to clear it immediately can `DELETE FROM daemon_events WHERE event_type='auto_merge_health_probe' AND created_at < now()` against the orchestration DB — but that is operational hygiene, not part of this fix.
- **Why the unit suite was green while production was broken**: existing unit tests at `tests/unit/test_auto_merge_health.py` mock `subprocess.run` itself, asserting on the *response* (`runtime_reachable`). The CLI-shape mismatch is at a layer below the mock — invisible. The S03 Tests prompt explicitly calls this out so the new tests don't repeat the mistake.
- **Why mirror `auto_merge.py` instead of shelling out to the binary directly**: the probe exists to verify reachability of the *same code path* the auto-merge resolver uses. The resolver invokes `bash step_executor_lib.sh auto_merge_resolve <agent> <model>` (see `orch/daemon/auto_merge.py:717-736`); reusing that pattern in the probe means (a) the probe and resolver cannot drift on CLI flag shape, (b) a future migration inside `_run_agent_oneshot` (e.g., `claude --print` → `claude -p`) is picked up by both atomically, and (c) a "healthy" probe verdict always implies the resolver's invocation chain is actually reachable end-to-end. Decision revised with sergio on 2026-05-17 after design review surfaced the existing `step_executor_lib.sh auto_merge_resolve` dispatch (which the original draft overlooked).
- **Subprocess env**: the lib script's top-level guard `: "${WORKTREE_PATH:?WORKTREE_PATH must be set before sourcing step_executor_lib.sh}"` (step_executor_lib.sh:36) refuses to run without a `WORKTREE_PATH` env var, even in direct-dispatch mode. The probe MUST pass `WORKTREE_PATH=<placeholder>` (e.g., the probe's own runtime cwd or `/tmp`) — `_run_agent_oneshot` itself does not use it. For `PATH`, the probe inherits the parent (daemon) process's `PATH` so the resolved `opencode` / `claude` binary is discoverable; this is a deliberate, narrow deviation from `auto_merge.py:732-735` (which hardcodes `PATH="/usr/local/bin:/usr/bin:/bin"` because the resolver runs an LLM in tool-use mode and wants a minimal attack surface). The probe's 1-token round-trip has no such concern, and inheriting `PATH` makes the integration test possible (the test prepends `tmp_path` to `PATH` to inject a fake CLI shim — see `## Test to Reproduce`).
