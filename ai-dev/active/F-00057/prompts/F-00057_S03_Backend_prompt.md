# F-00057_S03_Backend_prompt

**Work Item**: F-00057 — `iw oss` CLI + DB persistence
**Step**: S03
**Agent**: backend-impl

---

## Input Files

- `ai-dev/active/F-00057/F-00057_Feature_Design.md` — Design document
- `ai-dev/active/F-00057/reports/F-00057_S01_Database_report.md` — S01 (migration + ORM)
- `ai-dev/active/F-00057/reports/F-00057_S02_CodeReview_report.md` — S02 review verdict

## Output Files

- `ai-dev/active/F-00057/reports/F-00057_S03_Backend_report.md` — Step report
- `orch/oss/__init__.py` (new)
- `orch/oss/scanner.py` (new)
- `orch/oss/persistence.py` (new)
- `orch/oss/tool_probe.py` (new)
- `orch/oss/config_writer.py` (new)

## Context

You are building the backend service module that wraps the `iw-oss-publish` skill's Python orchestrator (`.claude/skills/iw-oss-publish/scripts/scan.py`) and persists its results to the DB tables created in S01. The CLI (S05) will call into this module.

Read `orch/db/session.py` and one existing service module (e.g., `orch/doc_service.py` or similar) to match patterns.

## Requirements

### 1. `orch/oss/scanner.py` — subprocess orchestration

Expose an async function:

```python
async def run_scan(
    project: Project,
    mode: str = "scan",
    *,
    session_factory: Callable[[], Session],
    skill_scan_path: Path,  # injected — caller resolves to iw-ai-core's canonical
                            # .claude/skills/iw-oss-publish/scripts/scan.py
) -> OssScan:
    """Run the iw-oss-publish orchestrator against project.repo_path.

    - Creates an oss_scan row with status='pending' and captures head_sha
      (via `git rev-parse HEAD` in the project dir) BEFORE starting the subprocess.
    - Starts a subprocess: `python3 {skill_scan_path} --target {project.repo_path}
      --mode {mode} --no-tool-check`
    - Streams stdout/stderr; on completion reads
      `{project.repo_path}/.iw/oss-publish-findings.json` and calls
      persistence.persist_findings() to populate oss_finding + oss_tool_run rows.
    - Sets oss_scan.status='complete', exit_code, pill_color (per invariant #3
      in the design doc), summary_json, completed_at.
    - On subprocess error (non-2 exit), sets status='error', error_message.
    - Returns the updated OssScan row.
    """
```

Use `asyncio.create_subprocess_exec` — NOT `subprocess.run`. Do not block the event loop.

### 2. `orch/oss/persistence.py` — DB writes

```python
def persist_findings(
    session: Session,
    scan: OssScan,
    findings_json: dict,
) -> None:
    """Parse the findings JSON emitted by scripts/scan.py and insert
    OssFinding + OssToolRun rows. Commit once at the end. The shape of
    findings_json is documented in .claude/skills/iw-oss-publish/references/output_format.md.
    """

def compute_pill_color(summary: dict) -> str:
    """Per invariant #3: must_fail > 0 OR must_human_required > 0 → red,
    else should_fail > 0 OR should_human_required > 0 → yellow,
    else green."""

def compute_summary_counts(findings: list[dict]) -> dict:
    """Roll up counts by (severity, status). Returns the shape
    consumed by oss_scan.summary_json."""
```

All DB writes MUST go through SQLAlchemy ORM (no raw SQL). A single commit per scan.

### 3. `orch/oss/tool_probe.py` — tool availability

```python
def probe_tier1() -> dict[str, ToolStatus]:
    """Check Tier-1 tools from the skill. Returns dict:
    {tool_name: ToolStatus(installed: bool, version: str | None, install_cmd: str)}

    Source the tool list from .claude/skills/iw-oss-publish/scripts/lib/tools.py's TIER1
    (single source of truth). Because the skill directory contains a hyphen
    (`iw-oss-publish`) it cannot be imported via a dotted path — load it via
    `importlib.util.spec_from_file_location(...)` given the absolute path
    resolved from the iw-ai-core project root. Do NOT mutate `sys.path`.

    install_cmd per tool is the one-liner from references/tools.md.
    """
```

### 4. `orch/oss/config_writer.py` — write `.iw/oss-publish.toml`

```python
def write_project_config(project: Project, *, force: bool = False) -> Path:
    """Write a resolved .iw/oss-publish.toml to project.repo_path/.iw/.
    Returns the path.

    Behavior:
    - File absent          → render and write, return path.
    - File present, content identical to rendered default → no-op, return path.
    - File present, content differs (user-edited)         → raise
      `ConfigFileExistsError` unless `force=True`, in which case overwrite.

    Use the skill's template `.iw-oss-publish.toml.j2` rendered with defaults from
    .claude/skills/iw-oss-publish/scripts/lib/config.py's DEFAULTS, overridden by
    any project-specific values (project.name → project_name, etc.).

    Resolve the skill path from iw-ai-core's canonical location (never the
    synced-to-project copy)."""
```

### 5. `orch/oss/__init__.py`

Re-export the public surface: `run_scan`, `probe_tier1`, `write_project_config`.

## Project Conventions

Read the project's `CLAUDE.md` and `orch/` docs:

- Architecture: service layer uses SQLAlchemy ORM via `orch/db/session.py`'s session factory. Do NOT import `orch/db/session.py` at module top level — inject the factory to keep tests independent.
- Async: subprocess calls use asyncio. If the CLI entry point is sync (click), wrap with `asyncio.run()` at the CLI layer (S05), not here.
- Logging: use the project's logger pattern.

## TDD Requirement

Follow TDD:

1. **RED**: Write failing tests first:
   - `tests/integration/test_oss_scanner.py::test_run_scan_against_fixture_repo`
   - `tests/integration/test_oss_persistence.py::test_persist_findings_round_trip`
   - `tests/integration/test_oss_persistence.py::test_compute_pill_color_all_cases`
   - Unit test for `tool_probe.probe_tier1` with mocked `shutil.which`.
   - Unit test for `config_writer.write_project_config` with tmp_path.
2. **GREEN**: Minimal impl.
3. **REFACTOR**.

Tests that S07 will add later are higher-level (full CLI → DB); your tests at this step exercise the service module APIs directly.

## Test Verification (NON-NEGOTIABLE)

1. Run `make test-unit` — must pass.
2. Run `make test-integration` — must pass.
3. Run `make lint` — must pass.
4. Run `uv run mypy orch/oss/` — must pass.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "backend-impl",
  "work_item": "F-00057",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/oss/__init__.py",
    "orch/oss/scanner.py",
    "orch/oss/persistence.py",
    "orch/oss/tool_probe.py",
    "orch/oss/config_writer.py",
    "tests/integration/test_oss_scanner.py",
    "tests/integration/test_oss_persistence.py",
    "tests/unit/test_oss_tool_probe.py",
    "tests/unit/test_oss_config_writer.py"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
