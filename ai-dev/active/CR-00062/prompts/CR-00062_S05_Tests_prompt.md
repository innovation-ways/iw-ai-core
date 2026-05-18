# CR-00062_S05_Tests_prompt

**Work Item**: CR-00062 — Add Pi (pi.dev) as a third agent runtime
**Step**: S05
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

Testcontainer fixtures (`tests/integration/conftest.py`) are your primary tool here and are the allowed exception. No `docker compose up/down/restart`, no `kill/stop/rm`, no `volume rm / prune`, no `system / container / image prune`. Read-only `docker ps / inspect / logs` allowed. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

S01 owns the migration. You consume its schema via testcontainers in your integration tests — `tests/integration/conftest.py` already runs `alembic upgrade head` against the testcontainer. Do NOT run alembic against the live orch DB.

## Input Files

- Runtime step state: `uv run iw item-status CR-00062 --json`
- Design doc: `ai-dev/active/CR-00062/CR-00062_CR_Design.md`
- S01 / S03 / S04 reports:
  - `ai-dev/active/CR-00062/reports/CR-00062_S01_Database_report.md`
  - `ai-dev/active/CR-00062/reports/CR-00062_S03_Pipeline_report.md`
  - `ai-dev/active/CR-00062/reports/CR-00062_S04_Backend_report.md`
- Existing testing conventions: `tests/CLAUDE.md`, `docs/IW_AI_Core_Testing_Strategy.md`, `skills/iw-ai-core-testing/SKILL.md`
- Patterns to mirror:
  - `tests/conftest.py` (autouse session-scope DB rules)
  - `tests/integration/conftest.py` (testcontainer fixtures, FTS DDL hook, `monkeypatch` over `importlib.reload`)
  - any existing test that exercises argv-builders (search `_build_fix_launch_argv`, `_build_agent_command` in `tests/`)

## Output Files

- `tests/unit/test_pi_runtime_dispatch.py` (new)
- `tests/unit/test_sync_agents_pi.py` (new)
- `tests/unit/test_project_registry_allowlist.py` (new)
- `tests/integration/test_pi_dispatch_end_to_end.py` (new)
- `ai-dev/active/CR-00062/reports/CR-00062_S05_Tests_report.md`

## Context

You are implementing S05 of CR-00062 — the test layer that proves S01/S03/S04 wired Pi correctly across all surfaces. Your tests are the **structural correctness gate** for the change (the QV gates at S12/S13 just re-run them at suite scale). Read the design doc's *TDD Approach* and *Acceptance Criteria* AC1, AC2, AC3, AC4, AC6 for the assertions your tests must cover.

## Requirements

### 1. `tests/unit/test_pi_runtime_dispatch.py`

Parametrize across `cli_tool ∈ {"opencode", "claude", "pi"}` and assert argv shape for each dispatch site:

- `orch/daemon/batch_manager._build_initial_command()` (or whatever the actual builder is named — verify by grep) — assert `pi` produces argv starting with `["pi", "-p", ...]`, claude with `["claude", "-p", ...]`, opencode with `["opencode", "run", ...]`.
- `orch/daemon/fix_cycle._build_fix_launch_argv()` — assert `pi` returns `["/bin/sh", "-c", inner]` (NOT `["script", "-qec", inner, "/dev/null"]` — that wrapper is opencode-only).
- `orch/daemon/fix_cycle._build_fix_inner_command()` (or equivalent) — assert `pi` inner command starts with `pi -p "$(cat ...)" --model ...`.
- `orch/daemon/doc_job_poller._build_agent_command()` — assert `pi` produces `[f'pi -p "/{skill} doc-job {job.id}"']` (no `--dangerously-skip-permissions` or `--permission-mode bypassPermissions` flag).
- `orch/doc_service._build_command()` (or equivalent) — assert `pi` arm form.

Also include a **negative test**: passing `cli_tool="<typo>"` to each builder raises `ValueError` (S03 added explicit `raise ValueError(f"Unknown cli_tool: …")` in the doc-job and doc-service builders).

Target: 12+ assertions across 6+ test functions.

### 2. `tests/unit/test_sync_agents_pi.py`

Tests for the `AgentSyncResult` field and `sync_agents_and_commands()` behaviour:

- `test_agent_sync_result_has_pi_agents_synced_field` — instantiate `AgentSyncResult()`, assert `pi_agents_synced == 0`.
- `test_sync_creates_pi_agents_directory` — use `tmp_path` to build a fake `platform_root` with a single `agents/pi/dummy.md` file; call `sync_agents_and_commands(project_path, platform_root)`; assert `result.pi_agents_synced == 1` and `(project_path / ".pi" / "agents" / "dummy.md").read_text() == <fixture content>`.
- `test_sync_pi_idempotent` — call sync twice, assert second call produces identical files (byte-by-byte) and the same count.
- `test_sync_total_count_includes_pi` — fixture with N pi agents + M claude agents + K opencode agents; assert all three counters plus the printed total match expected.

Target: 4+ test functions, 6+ assertions.

### 3. `tests/unit/test_project_registry_allowlist.py`

Tests for the new `_VALID_CLI_TOOLS` allowlist in `orch/daemon/project_registry.py`:

- `test_valid_cli_tool_opencode_loads` — project entry with `cli_tool="opencode"` loads successfully (returns a `ProjectConfig`).
- `test_valid_cli_tool_claude_loads` — same with `"claude"`.
- `test_valid_cli_tool_pi_loads` — same with `"pi"`.
- `test_invalid_cli_tool_typo_skipped` — project entry with `cli_tool="pii"` → `_load_project_config()` returns `None` and `caplog` captures a warning naming the project id and the bad value.
- `test_missing_cli_tool_defaults_to_opencode` — entry with no `cli_tool` key falls back to `"opencode"` (existing behaviour preserved).
- `test_iw_orch_json_cli_tool_fallback_validated` — fallback via `.iw-orch.json` ALSO goes through the allowlist (a typo in `.iw-orch.json` is rejected the same way).

Target: 6+ test functions.

### 4. `tests/integration/test_pi_dispatch_end_to_end.py`

End-to-end integration test against a stub `pi` binary on `PATH`. Pattern:

a) **Fixture: stub-pi binary**

```python
@pytest.fixture
def stub_pi_binary(tmp_path, monkeypatch):
    stub = tmp_path / "bin" / "pi"
    stub.parent.mkdir(parents=True, exist_ok=True)
    stub.write_text('#!/usr/bin/env bash\necho "STUB_PI_MARKER_$$"\nexit 0\n')
    stub.chmod(0o755)
    monkeypatch.setenv("PATH", f"{stub.parent}{os.pathsep}{os.environ['PATH']}")
    return stub
```

b) **Tests**

- `test_pi_step_launch_invokes_stub` — register a fake project with `cli_tool="pi"`; invoke `step_executor.sh` (via subprocess) for a minimal step; assert the step log contains the `STUB_PI_MARKER_` prefix.
- `test_pi_fix_cycle_invokes_stub` — exercise the fix-cycle launch path with `cli_tool="pi"`; assert the fix log contains the marker AND the fix-cycle did NOT use the `script -qec` PTY wrapper (verify by absence of `script:` errors in stderr or by reading `_build_fix_launch_argv("pi", ...)` directly).
- `test_pi_auto_merge_oneshot_pipes_stdin` — call `step_executor_lib.sh auto_merge_resolve pi <model>` with a prompt on stdin; assert stdout contains the marker.
- `test_pi_doc_job_launches_pi_print_mode` — enqueue a `DocGenerationJob` for a project with `cli_tool="pi"`; let `doc_job_poller` build the command; assert the command shape starts with `pi -p "/{skill} doc-job {job.id}"`.

c) **Catalogue lookup test** (AC2)

- `test_pi_catalogue_resolves_minimax_and_codex` — using the testcontainer DB seeded by S01's migration, call `agent_runtime/resolver.resolve_runtime()` with `(cli_tool="pi", model="minimax/MiniMax-M2.7")` and `("pi", "openai/gpt-5.3-codex")`; assert both return rows with the expected `display_name`, `enabled=True`, `is_default=False`, `sort_order` 25 and 26.

Target: 5+ test functions, 10+ assertions.

### 5. Stub-binary platform compatibility

If the stub-PATH mechanism fails on a particular platform (e.g., the test runner's PATH lookup is hermetic), mark the affected test with `@pytest.mark.skipif(condition, reason="...")` and **document the reason in the test docstring**. Do NOT silently skip without reason — `tests/CLAUDE.md` and `skills/iw-ai-core-testing/SKILL.md` both flag silent skips as a red flag.

## Project Conventions

Read `tests/CLAUDE.md` (testcontainer-only for live DB, `monkeypatch.delenv()` over `importlib.reload(orch.config)`, FTS DDL hook after `Base.metadata.create_all()`, `DaemonEvent.event_metadata` not `metadata`, no mocking the DB in integration tests). Read `skills/iw-ai-core-testing/SKILL.md` for the test red-flag checklist — your tests will be reviewed against it at S06.

## TDD Requirement

This step is the test step itself. Pre-fix RED evidence for the `pi` dispatch branches and the `pi_agents_synced` field is **owned by S03 and S04** — those prompts already require the implementing agent to capture an `AssertionError` / `AttributeError` BEFORE adding the production branch and to record it in `tdd_red_evidence`. **DO NOT** `git checkout HEAD~1`, `git stash`, or otherwise revert previously-shipped source files at runtime to manufacture a RED run — that pattern causes thrash and timeouts and is explicitly forbidden by the project's tests-impl conventions.

For your `tdd_red_evidence` field, record `"n/a — pre-fix RED captured by S03/S04 prompts; this step adds the durable test surface"`, and in the report's Notes section list which sites' RED evidence you verified by reading the S03 and S04 reports.

If during your work you discover a test you wrote already fails against the current S03/S04 implementation (i.e., an S03/S04 regression that slipped through), capture the failing test id and assertion line in `tdd_red_evidence` instead — that IS a legitimate RED finding for this step and should be reported as a blocker so S07 can fix it.

## ⚠️ Semantic Correctness Warning (I003 lesson)

**A passing test that asserts the wrong thing is worse than no test.** For every parametrized argv assertion in `test_pi_runtime_dispatch.py`, verify the assertion encodes the *exact* argv shape the design specifies — not just "contains 'pi'" or "doesn't raise". For example, asserting `"pi" in argv[0]` would pass for a misbuilt command like `["pi-broken", "-p", ...]`; assert `argv[0] == "pi"` and `argv[1] == "-p"` and the full positional structure instead. Same rule for the `--model` flag — assert the resolved model value matches the catalogue row, not just that any `--model` is present.

When a test passes on first run with no prior RED, treat it as suspicious until you can show the assertion fires GREEN on the production code path AND would have fired RED on a plausible bug (mentally substitute a wrong cli_tool branch and confirm the assertion would catch it).

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck`
3. `make lint`

## Test Verification (NON-NEGOTIABLE)

Run **only the test files you wrote** (per CR-00023's tests-impl rule):

```bash
uv run pytest tests/unit/test_pi_runtime_dispatch.py tests/unit/test_sync_agents_pi.py tests/unit/test_project_registry_allowlist.py tests/integration/test_pi_dispatch_end_to_end.py -v
```

Do **NOT** run `make test-unit` or `make test-integration` — those are S12/S13 QV gates.

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "tests-impl",
  "work_item": "CR-00062",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/unit/test_pi_runtime_dispatch.py",
    "tests/unit/test_sync_agents_pi.py",
    "tests/unit/test_project_registry_allowlist.py",
    "tests/integration/test_pi_dispatch_end_to_end.py"
  ],
  "preflight": {
    "format": "ok|fixed",
    "typecheck": "ok",
    "lint": "ok"
  },
  "tests_passed": true,
  "test_summary": "N passed, 0 failed",
  "tdd_red_evidence": "<captured RED→GREEN evidence or n/a note>",
  "blockers": [],
  "notes": "any test marked skipif and the reason; any test that uncovered an S03/S04 regression and the fix that was needed"
}
```
