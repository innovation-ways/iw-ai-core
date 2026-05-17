# I-00088_S03_Tests_prompt

**Work Item**: I-00088 — Auto-merge health probe always fails — CLI-shape mismatch with step_executor.sh
**Step**: S03
**Agent**: Tests (`tests-impl`)

---

## ⛔ Docker is off-limits

You MUST NOT touch docker container/volume/network state. Testcontainer
fixtures spun up by pytest are exempt (they self-label and self-destruct).

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This step adds NO migrations. Read-only `alembic history / current / show`
is OK.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00088 --json`
- `ai-dev/active/I-00088/I-00088_Issue_Design.md` — Design document (READ FIRST, especially the "Test to Reproduce" section)
- `ai-dev/work/I-00088/reports/I-00088_S01_Backend_report.md` — S01 report (lists which existing tests are now red)
- `ai-dev/work/I-00088/reports/I-00088_S02_CodeReview_report.md` — S02 review
- `orch/daemon/auto_merge_health.py` — current (post-S01) implementation
- `tests/unit/test_auto_merge_health.py` — existing tests; you will REWRITE the response-shape assertions to argv-shape assertions
- `tests/CLAUDE.md` and `skills/iw-ai-core-testing/SKILL.md` — testing rules; read both

## Output Files

- `ai-dev/work/I-00088/reports/I-00088_S03_Tests_report.md`

## Context

S01 fixed the probe to invoke `bash step_executor_lib.sh auto_merge_resolve
<cli_tool> <model>` (mirroring `orch/daemon/auto_merge.py:717-736`), reading
the prompt from stdin and expecting `OK` on stdout. The lib script's
`_run_agent_oneshot` resolves the runtime (`opencode` / `claude`) via `PATH`.
Two test layers need to lock the fix in:

1. **Unit layer** (`tests/unit/test_auto_merge_health.py`) — assert on the
   **argv** passed to `subprocess.run`, not just the response. The original
   bug was invisible because the tests mocked `subprocess.run` itself and
   only checked the response. Fix that.
2. **Integration layer** (NEW: `tests/integration/test_auto_merge_health_runtime.py`) —
   run the **real** `subprocess.run`, which spawns the **real**
   `step_executor_lib.sh`, which resolves a **fake** `opencode` (or `claude`)
   shim on `PATH` that echoes `OK`. This catches CLI-shape regressions
   end-to-end across all three layers (probe → lib script → CLI binary).

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed.
But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert "permissions" in data` (shape only)
- GOOD: `assert "brands:manage" in permissions` (semantic — verifies specific expected value)
- GOOD: `assert "*" not in permissions` (semantic — verifies unwanted value is absent)

Applied to this incident:

- BAD: `assert payload["runtime_reachable"] is True` (passes even if the probe
  never actually invoked the runtime — the bug we are fixing)
- GOOD: `assert "step_executor_lib.sh" in run.call_args.args[0][1]` (verifies
  the probe targets the right script — the resolver's canonical entry point —
  not `step_executor.sh`)
- GOOD: `assert "auto_merge_resolve" in run.call_args.args[0]` (verifies the
  direct-dispatch step type reached the lib script)
- GOOD: `assert resolved.cli_tool in run.call_args.args[0]` and
  `assert resolved.model in run.call_args.args[0]` (verifies cli_tool +
  model both reached the dispatch)
- BEST (integration): `assert "minimax/MiniMax-M2.7" in capture.read_text()`
  AND `assert "Reply with the single word OK" in capture.read_text()`
  (verifies the model + prompt reached a real subprocess through the real
  `step_executor_lib.sh` via real PATH lookup)

## Requirements

### 1. Rewrite the unit tests

In `tests/unit/test_auto_merge_health.py`, every test that asserts on
`payload["runtime_reachable"]` after mocking `subprocess.run` MUST also
assert on the **argv** passed to `subprocess.run`. The argv assertion is
the one that would have caught the original bug.

Concretely, for each test that mocks `subprocess.run`:

- Capture `run.call_args` (or use `run.call_args.args[0]` for positional
  argv / `run.call_args.kwargs` for kwargs like `input`, `timeout`, `env`).
- Assert: `argv[0] == "bash"`.
- Assert: `argv[1].endswith("step_executor_lib.sh")` (the canonical lib script
  — not `step_executor.sh`).
- Assert: `argv[2] == "auto_merge_resolve"` (the direct-dispatch step type).
- Assert: `argv[3] == resolved.cli_tool` (e.g., `"opencode"`).
- Assert: `argv[4] == resolved.model` (e.g., `"openai/gpt-5.3-codex"`).
- Assert: the probe prompt (`"Reply with the single word OK."`) appears in
  the `input` kwarg.
- Assert: `kwargs["env"]["WORKTREE_PATH"]` is non-empty (the lib script's
  top-level `WORKTREE_PATH:?` guard would otherwise refuse to run).
- For the `opencode` vs `claude` test (`test_probe_uses_resolved_per_project_runtime`),
  assert the argv[3] value tracks `resolved.cli_tool` (so the dispatch carries
  the per-project CLI choice through to the lib script).

Keep the existing assertions on `payload["runtime_reachable"]`,
`payload["error"]`, and `payload["cli_tool"]` / `payload["model"]` — they
still verify event-metadata shape. Just **add** the argv assertions; don't
delete the existing ones.

Tests to keep / rewrite (do NOT delete):

- `test_probe_skipped_when_recent_event_exists` — unchanged
- `test_probe_skipped_when_phase_0` — unchanged
- `test_probe_fires_when_no_recent_event` — add argv assertions
- `test_probe_records_failure_on_subprocess_error` — add argv assertions
- `test_probe_records_failure_on_timeout` — keep
- `test_probe_uses_resolved_per_project_runtime` — make this the *primary*
  shape test; assert the argv tracks `cli_tool`
- `test_probe_subprocess_timeout_capped` — keep
- `test_probe_non_blocking_does_not_raise` — keep

### 2. Add the integration test (NEW FILE)

Create `tests/integration/test_auto_merge_health_runtime.py` per the
"Test to Reproduce" section in `I-00088_Issue_Design.md`. The test must:

- Write a tiny fake CLI shim into `tmp_path`, named `opencode` (and/or
  `claude`), that captures its argv + stdin to a file then prints `OK`.
- Make the shim executable.
- Prepend `tmp_path` to `PATH` via `monkeypatch.setenv("PATH", f"{tmp_path}:{os.environ['PATH']}")`.
  This relies on the probe inheriting `PATH` from the parent process via
  `os.environ.get("PATH", ...)` in its env dict (see S01 prompt). If the
  probe ever hardcodes `PATH`, this test will fail and that is the correct
  outcome — flag it back to the test author so the probe + test agree.
- Patch `orch.daemon.auto_merge_health.resolve_project_config` to return a
  config with `phase=1`, `cli_tool="opencode"`, `model="minimax/MiniMax-M2.7"`.
- Use a `MagicMock` for `db` (matching the existing unit-test pattern) —
  the test does NOT need the testcontainer DB; it only exercises the
  probe → lib-script → fake-CLI chain.
- Call the real `maybe_run_probe`.
- Assert: `db.add.call_args[0][0].event_metadata["runtime_reachable"] is True`.
- Assert: the capture file contains `"minimax/MiniMax-M2.7"` (model reached
  the fake CLI via real PATH lookup, which means the lib-script dispatch
  worked end-to-end).
- Assert: the capture file contains the probe prompt string
  (`"Reply with the single word OK."`) — the prompt flowed through stdin
  from the probe → bash → lib script → fake CLI.

Add a second test for the failure path: write a fake `opencode` shim that
exits 1 without printing `OK`, and assert `runtime_reachable is False`, plus
`payload["error"]` is non-empty. This proves the failure path also goes
through real PATH lookup and the lib-script dispatch.

**Test location rationale**: this test exercises a real subprocess (in fact
three layers of subprocess: Python → bash → fake CLI) and matches the
testcontainer-adjacent style of `tests/integration/`. It does not need the
testcontainer DB itself — the DB session is a `MagicMock` — but it does need
a real `subprocess.run` against the real `step_executor_lib.sh` and a real
binary on `PATH`, which is integration-test territory, not unit-test
territory.

### 3. RED proof for the integration test

Before reporting `tests_passed: true`:

1. Run **only** the new integration test against the post-S01 code:
   ```bash
   uv run pytest tests/integration/test_auto_merge_health_runtime.py -v
   ```
   It must pass.
2. **Manual mental RED check**: trace what would happen if the probe still
   called `/bin/bash step_executor.sh --step-type ...` (the pre-S01 state):
   `step_executor.sh` would exit 2 with `ERROR: Worktree not found or invalid: --agent`
   before any runtime is invoked; the fake `opencode` shim on PATH wouldn't
   be touched; the capture file wouldn't exist; `runtime_reachable` would
   be `False`; and the test would fail. Document this in `notes`. Do NOT
   `git stash` or revert source files at runtime — design-time mental
   reasoning is sufficient here (see iw-new-incident skill rule on this).

### 4. Targeted verification only

Do NOT run `make test-integration` or `make test-unit` in this step.
Run only the file(s) you touched:

```bash
uv run pytest tests/unit/test_auto_merge_health.py tests/integration/test_auto_merge_health_runtime.py -v
```

The QV gates (S09 unit-tests, S10 integration-tests) own full-suite execution.

## Project Conventions

Read `tests/CLAUDE.md` and `skills/iw-ai-core-testing/SKILL.md`:

- Never connect to the live DB (port 5433) — the integration test uses
  `MagicMock` for the DB session, which is fine because it is exercising
  the *subprocess* path, not DB code.
- The repo uses pytest with `pytest-randomly` ON by default. Your tests
  MUST be order-independent. Use `monkeypatch` (not raw `os.environ`) and
  `tmp_path` (not hard-coded `/tmp`) so cleanup is automatic.
- Assertion strength rule: every assertion must be one that would fail if
  the production code regressed. See `skills/iw-ai-core-testing/SKILL.md` §0.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `completion_status: complete`:

1. `make format` — auto-fixes formatting drift.
2. `make typecheck` — zero errors involving the files you touched.
3. `make lint` — zero errors.

## Test Verification (NON-NEGOTIABLE)

Only run the test files you authored / modified:

```bash
uv run pytest tests/unit/test_auto_merge_health.py tests/integration/test_auto_merge_health_runtime.py -v
```

Do NOT run `make test-unit` / `make test-integration`. Those are S09 / S10's
job and duplicating them here burns this step's timeout budget (I-00073/S03
post-mortem).

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "tests-impl",
  "work_item": "I-00088",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/unit/test_auto_merge_health.py",
    "tests/integration/test_auto_merge_health_runtime.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "n/a — dedicated coverage step; production code already exists post-S01",
  "blockers": [],
  "notes": "Manual reasoning: the new integration test would fail against pre-S01 code because the shim wouldn't be invoked and runtime_reachable would be False. Documented in the test file's module docstring."
}
```
