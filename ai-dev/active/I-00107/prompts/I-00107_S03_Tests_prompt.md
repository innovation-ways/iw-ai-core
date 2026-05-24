# I-00107_S03_Tests_prompt

**Work Item**: I-00107 -- daemon reload does not apply `.iw-orch.json` changes for an already-running project
**Step**: S03
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

Standard policy. This step writes **unit** tests — no testcontainer, no docker compose. Read `tests/CLAUDE.md` for the strict DB-isolation rules; this step does not need them.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

No migration. Pure test code.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status I-00107 --json` is authoritative.
- `ai-dev/active/I-00107/I-00107_Issue_Design.md` — Design document (read the **TDD Approach** section in full)
- `ai-dev/active/I-00107/reports/I-00107_S01_Backend_report.md` — S01 step report
- `ai-dev/active/I-00107/reports/I-00107_S02_CodeReview_report.md` — S02 review report
- `orch/daemon/main.py`, `orch/daemon/project_registry.py` — post-S01 source under test
- Existing similar test for reference: `tests/unit/daemon/test_agent_subprocess_env.py`

## Output Files

- `ai-dev/active/I-00107/reports/I-00107_S03_Tests_report.md` — Step report
- `tests/unit/daemon/test_daemon_config_reload.py` — New test file

## Context

You are writing the reproduction + regression test coverage for **I-00107**. S01 has implemented the fix; your tests must:

1. **Reproduce the bug as it existed before the fix** — i.e., the test would FAIL against the pre-S01 code (the `"unchanged"` branch silently dropping the fresh `ProjectConfig`) and PASSES against the current (fixed) code.
2. **Pin all five Acceptance Criteria** from the design's AC1–AC5.
3. **Verify semantic correctness, not just shape** — see the warning below.

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed.
But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert "permissions" in data` (shape only)
- GOOD: `assert "brands:manage" in permissions` (semantic — verifies specific expected value)
- GOOD: `assert "*" not in permissions` (semantic — verifies unwanted value is absent)

For this incident, applying the rule:

- BAD: `assert daemon.managers["demo"] is not None` (manager exists — pre-fix would also pass)
- GOOD: `assert post_manager is not pre_manager` (the manager OBJECT was replaced — pre-fix has same reference)
- GOOD: `assert "**/*.md" in post_manager.project_config.overlap_allow_patterns` AND `"**/*.md" not in pre_manager.project_config.overlap_allow_patterns` (the new value is present in the new config AND was absent in the old — pre-fix has the same patterns in both)

## Requirements

### 1. Create `tests/unit/daemon/test_daemon_config_reload.py`

This is a unit test — no testcontainer, no DB. The daemon's reload path operates on in-memory state and tmp-path-backed files. Use `pytest`, `tmp_path`, and `monkeypatch`. Mock or patch the DB-touching helpers (`sync_project_to_db`, `_session_factory`) so the test does not require a live DB.

Pattern to follow: read `tests/unit/daemon/test_agent_subprocess_env.py` for fixture style and how it constructs daemon objects without booting the full process.

### 2. Implement the five tests named by the design's TDD Approach

Each test must be **able to fail** if its target behaviour regresses. The mandatory five tests, in priority order:

#### 2a. `test_i00107_reload_rebuilds_batch_manager_when_iw_orch_json_changes` (reproduction)

The exact test sketched in the design doc's "Test to Reproduce" section. Mirror that wording verbatim — file structure, asserts, and the `I-00107:` annotation in the assertion message. This is the load-bearing test that proves the bug is fixed.

#### 2b. `test_reload_unchanged_when_iw_orch_json_is_identical` (no-churn)

Write a `.iw-orch.json` with some `allow_on_overlap` list. Run an initial load. Trigger reload WITHOUT editing anything. Assert:

- `daemon.managers[pid]` is the **same object reference** before and after the second reload (`post_manager is pre_manager`).
- No `project_config_reloaded` event was emitted on the second reload (see 2d's patching pattern).

This protects against "always rebuild" regressions that would waste cycles.

#### 2c. `test_reload_rebuilds_manager_on_enabled_toggle` (AC3)

Start with a `projects.toml` entry that has `enabled = false` (or omit it; check how `_build_project_config` treats absent vs explicit false — the test must drive whatever the production code treats as "disabled"). Load. The project should NOT appear in `self.managers`. Edit `projects.toml` to set `enabled = true`. Reload. Assert `self.managers[pid]` is now present with a fresh BatchManager whose `project_config.overlap_allow_patterns` matches the project's current `.iw-orch.json`.

#### 2d. `test_reload_emits_project_config_reloaded_event` (AC4)

Use `monkeypatch` (or `unittest.mock.patch`) on `orch.daemon.main.emit_event` to capture calls. Edit `.iw-orch.json` to add a new allow-pattern. Reload. Assert exactly ONE `emit_event` call with `event_type="project_config_reloaded"`, `entity_id=<pid>`, and a `metadata` dict whose `changed_fields` includes the string `"overlap_allow_patterns"` (or whatever the post-S01 field name is — confirm by reading S01's `files_changed`).

Semantic note: `assert len(emit_event_calls) == 1` (exact count) AND `assert "overlap_allow_patterns" in call.kwargs["metadata"]["changed_fields"]` (specific field name). NOT `assert emit_event.called` (shape only).

#### 2e. `test_reload_does_not_refresh_when_only_projects_toml_unchanged_iw_orch_json_unparseable`

Write a valid initial setup. Load. Capture pre-state. Now write a malformed `.iw-orch.json` (e.g. truncated JSON, syntax error). Reload. Assert:

- `self.managers[pid]` is the **same object reference** as before (no rebuild — the per-project parse fallback returned an effectively-equivalent ProjectConfig, or the comparison itself short-circuited safely).
- No `project_config_reloaded` event was emitted.
- A warning was logged (use `caplog` at WARNING level; assert the warning mentions the project id).

Note: `_build_project_config` (`project_registry.py:128-141`) already logs a warning and falls back to defaults on a malformed `.iw-orch.json`. Your test pins that behaviour — it does NOT add new behaviour.

### 3. No `make test-unit` or `make test-integration` from this step

Per `tests/CLAUDE.md` and the design doc's TDD Approach, run ONLY the new file:

```bash
uv run pytest tests/unit/daemon/test_daemon_config_reload.py -v
```

That is sufficient to prove your tests work. The full unit suite is S11's gate; the full integration suite is S12's gate. Running them here burns this step's budget (see I-00073/S03 post-mortem).

### 4. Do NOT revert source to verify pre-fix RED

Do not `git stash` or `git checkout HEAD~1 -- orch/daemon/*.py` to "verify" the test would have failed pre-fix. That is a design-time exercise that has already been done (the bug was observed live this session — see the design's Root Cause Analysis "Observed evidence" subsection). At-runtime source-reverts are thrash-prone and not part of this skill's contract.

### 5. Style and conventions

- Match the test-naming style of existing `tests/unit/daemon/` tests.
- Use `tmp_path` for filesystem fixtures, not `/tmp/...`.
- Use `monkeypatch.setenv` / `monkeypatch.delenv` — never `os.environ[...] = ...` directly (per `tests/CLAUDE.md` Rule 2).
- Do not call `importlib.reload(orch.config)` (per `tests/CLAUDE.md` Rule 2).

### 6. TDD note

This is a `tests-impl` step. `tests-impl` is **exempt** from the RED-first requirement because the production code already exists (S01). Report `tdd_red_evidence` as `"n/a — tests-impl step adding regression coverage for already-merged S01 fix"`.

## Project Conventions

Read `tests/CLAUDE.md` for the project's testing rules. In particular: NEVER connect to the live DB (port 5433); use testcontainers only when DB access is needed (this step does not need them).

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `completion_status: complete`:

1. **`make format`** — auto-fixes formatting drift on your new file.
2. **`make typecheck`** — must report zero errors in the new file. (Tests are typechecked.)
3. **`make lint`** — must report zero errors in the new file.

Record results in the `preflight` field.

## Test Verification (NON-NEGOTIABLE)

Targeted only:

```bash
uv run pytest tests/unit/daemon/test_daemon_config_reload.py -v
```

All five tests must pass. If any fail, fix them before reporting completion. Do NOT run the full unit or integration suite.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "tests-impl",
  "work_item": "I-00107",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/unit/daemon/test_daemon_config_reload.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "5 passed, 0 failed",
  "tdd_red_evidence": "n/a — tests-impl step adding regression coverage for already-merged S01 fix",
  "blockers": [],
  "notes": ""
}
```
