# CR-00015_S05_Tests_prompt

**Work Item**: CR-00015 — Remove docker-compose db service foot-gun
**Step**: S05
**Agent**: tests-impl

---

## Input Files

- `ai-dev/active/CR-00015/CR-00015_CR_Design.md` — Design (AC1–AC4)
- Reports from S01, S03
- `tests/conftest.py`, `tests/CLAUDE.md`
- `docker-compose.yml` (stub) and `docker-compose.bootstrap.yml` (new)
- `ai-core.sh`

## Output Files

- `ai-dev/active/CR-00015/reports/CR-00015_S05_Tests_report.md`
- `tests/integration/test_compose_split.py` — new test file (Python with `subprocess.run` is preferred over pure bash tests for consistency with the rest of the suite)

## Context

Formal test coverage for the compose split. Shell-level verification: the root compose file has no `db` service, the bootstrap file does, volume name is stable, and `ai-core.sh db start` no-ops when DB is already up.

## Requirements

### 1. Test file location and marker

Create `tests/integration/test_compose_split.py`. Use `@pytest.mark.integration` on every test in the file. Imports: `subprocess`, `json`, `os`, `pathlib`, `pytest`.

### 2. Tests to write

#### `test_root_compose_has_no_db_service`

```python
def test_root_compose_has_no_db_service():
    result = subprocess.run(
        ["docker", "compose", "config", "--format", "json"],
        capture_output=True, text=True, cwd=PROJECT_ROOT,
    )
    assert result.returncode == 0, f"compose config failed: {result.stderr}"
    config = json.loads(result.stdout)
    services = config.get("services", {})
    assert "db" not in services, f"Root compose has a 'db' service — should be in bootstrap only. Services: {list(services)}"
```

#### `test_bootstrap_compose_has_db_service`

```python
def test_bootstrap_compose_has_db_service():
    result = subprocess.run(
        ["docker", "compose", "-f", "docker-compose.bootstrap.yml", "config", "--format", "json"],
        capture_output=True, text=True, cwd=PROJECT_ROOT,
    )
    assert result.returncode == 0, f"bootstrap config failed: {result.stderr}"
    config = json.loads(result.stdout)
    assert "db" in config["services"]
    db = config["services"]["db"]
    assert db["image"].startswith("postgres:15")
    assert db["container_name"] == "iw-ai-core-db"
```

#### `test_bootstrap_volume_name_stable_across_cwd`

Most important test — exercises the foot-gun scenario. Run `docker compose -f docker-compose.bootstrap.yml config` from the project root and from a temporary directory; assert the computed volume name is identical (`iw-ai-core_pgdata`) in both cases. This proves the `name: iw-ai-core` top-level key pins the project name regardless of cwd.

```python
def test_bootstrap_volume_name_stable_across_cwd(tmp_path):
    # Copy the bootstrap file to a temp dir
    bootstrap = PROJECT_ROOT / "docker-compose.bootstrap.yml"
    shutil.copy(bootstrap, tmp_path / "docker-compose.bootstrap.yml")

    def get_volume_name(cwd: Path) -> str:
        result = subprocess.run(
            ["docker", "compose", "-f", "docker-compose.bootstrap.yml", "config", "--format", "json"],
            capture_output=True, text=True, cwd=cwd,
        )
        config = json.loads(result.stdout)
        # Compose reports volumes as {name: {...}} where name is the full expanded volume name.
        return list(config["volumes"].keys())[0]

    assert get_volume_name(PROJECT_ROOT) == get_volume_name(tmp_path) == "iw-ai-core_pgdata"
```

Note: this requires docker to be available in the test environment. If CI doesn't have docker, mark the test with `@pytest.mark.skipif(not _docker_available(), reason="docker not available")` using a helper. On local dev machines, it will run.

#### `test_ai_core_db_start_noops_when_db_ready`

Start the test with a mock for `db_ready()` returning true. Since `ai-core.sh` is bash, invoke it as a subprocess and check its exit code + stdout. Use an env var stub to control `db_ready`:

```python
def test_ai_core_db_start_noops_when_db_ready():
    # If the live DB is accepting connections, ai-core.sh db start MUST NOT call docker.
    # We verify by snapshotting container count before and after, and parsing stdout.
    before = subprocess.run(["docker", "ps", "-q"], capture_output=True, text=True).stdout.strip()
    result = subprocess.run(
        ["./ai-core.sh", "db", "start"],
        capture_output=True, text=True, cwd=PROJECT_ROOT,
    )
    after = subprocess.run(["docker", "ps", "-q"], capture_output=True, text=True).stdout.strip()

    assert result.returncode == 0
    # Note: "already accepting connections" is the exact phrase the hardened cmd_db prints
    assert "already accepting connections" in result.stdout or "already accepting" in result.stdout
    assert before == after, "ai-core.sh started or removed a container when DB was already up"
```

This test has a hard precondition that the live DB IS up — gate it with a skip if unreachable:

```python
def _db_reachable() -> bool:
    return subprocess.run(
        ["nc", "-z", "-w2", "localhost", os.environ.get("IW_CORE_DB_PORT", "5433")],
        capture_output=True,
    ).returncode == 0

@pytest.mark.skipif(not _db_reachable(), reason="live DB not reachable")
def test_ai_core_db_start_noops_when_db_ready():
    ...
```

### 3. Do NOT touch the live DB

- No test may `docker stop postgres`, `docker kill`, `docker rm`, `docker volume rm`, or any destructive operation.
- No test may invoke `./ai-core.sh db start` expecting it to actually create a container — all tests that run that command require the DB to ALREADY be up (skip otherwise).
- No test writes to `/opt/postgres/data`.

### 4. Helper constants

```python
from pathlib import Path
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
```

### 5. Fixture reuse

If any existing fixture already checks Docker availability or runs `docker compose config`, reuse it. Don't duplicate.

## Project Conventions

- Integration tests in `tests/integration/`.
- `@pytest.mark.integration` required.
- No live-DB operations (`tests/CLAUDE.md` rule) — specifically, `test_ai_core_db_start_noops_when_db_ready` is READ-ONLY; it just checks behavior.
- `subprocess.run` with `capture_output=True, text=True` style.

## TDD Verification

Write tests BEFORE running them. They must fail against pre-CR code (where the root compose has `db` and the bootstrap file doesn't exist). Document in the report that you verified this by a `git stash` or equivalent.

## Test Verification (NON-NEGOTIABLE)

1. `make test-integration` — all new tests pass.
2. `make lint` — pass.
3. Tests run cleanly twice in a row (no state leaked).

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "tests-impl",
  "work_item": "CR-00015",
  "completion_status": "complete",
  "files_changed": ["tests/integration/test_compose_split.py"],
  "tests_passed": true,
  "test_summary": "4 passed, 0 failed, skipped-if-no-docker",
  "blockers": [],
  "notes": ""
}
```

## Lifecycle commands

```bash
uv run iw step-start CR-00015 --step S05
# write tests ...
uv run iw step-done CR-00015 --step S05 --report ai-dev/active/CR-00015/reports/CR-00015_S05_Tests_report.md
```
