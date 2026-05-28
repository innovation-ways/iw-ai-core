"""Test-health snapshot service for CR-00086.

Reads four source artefacts (mutation JSON, coverage XML, flaky log,
assertion baseline) and writes snapshots to the test_health_snapshots table.
"""

from __future__ import annotations

import json
import logging
import subprocess
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from orch.db.models import TestHealthSnapshot

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Mutation JSON parser — dispatches on CR-00080 vs. CR-00059 shape
# ---------------------------------------------------------------------------


def _parse_mutation_json(artifact_path: Path) -> tuple[float, dict[str, object]] | None:
    """Parse mutation JSON artefact; handle both CR-00080 (new) and CR-00059 (legacy) shapes.

    Returns (score, meta) or None if the file cannot be parsed.
    """
    if not artifact_path.exists():
        return None
    try:
        payload = json.loads(artifact_path.read_text())
    except json.JSONDecodeError:
        logger.warning("Could not parse mutation JSON at %s", artifact_path)
        return None

    # CR-00080 shape: score is a top-level float
    if "score" in payload and isinstance(payload.get("score"), (int, float)):
        score = float(payload["score"])
        meta: dict[str, object] = {
            "total": payload.get("total"),
            "mutated": payload.get("mutated"),
            "killed": payload.get("killed"),
            "passed": payload.get("passed"),
            "skipped": payload.get("skipped"),
            "runtime_seconds": payload.get("runtime_seconds"),
            "source_shape": "cr-00080",
        }
        return score, meta

    # CR-00059 shape: score is under metrics.mutation_score
    metrics: dict[str, object] = payload.get("metrics", {})
    score_val = metrics.get("score")
    if score_val is not None and isinstance(score_val, (int, float)):
        score = float(score_val)
        meta = {
            "total_mutations": metrics.get("total_mutations"),
            "mutations_killed": metrics.get("mutations_killed"),
            "mutations_timeout": metrics.get("mutations_timeout"),
            "mutations_error": metrics.get("mutations_error"),
            "elapsed_seconds": payload.get("summary", {}).get("elapsed_seconds"),
            "source_shape": "cr-00059",
        }
        return score, meta

    logger.warning("Unrecognised mutation JSON shape at %s", artifact_path)
    return None


def _read_mutation_score(repo_root: Path) -> tuple[float, dict[str, object]] | None:
    """Find and parse the latest mutation JSON artefact under repo_root."""
    # Look for tests/output/mutation/mutation.json (CR-00080 artefact)
    candidate = repo_root / "tests" / "output" / "mutation" / "mutation.json"
    if candidate.exists():
        return _parse_mutation_json(candidate)
    logger.warning("Mutation artefact not found: %s", candidate)
    return None


# ---------------------------------------------------------------------------
# Coverage reader
# ---------------------------------------------------------------------------


def _read_coverage_pct(
    coverage_json_path: Path, pyproject_path: Path
) -> tuple[float, dict[str, object]] | None:
    """Parse coverage JSON artefact and return (overall_line_pct, meta) or None."""
    if not coverage_json_path.exists():
        logger.warning("Coverage artefact not found: %s", coverage_json_path)
        return None
    try:
        data = json.loads(coverage_json_path.read_text())
    except json.JSONDecodeError:
        logger.warning("Could not parse coverage JSON at %s", coverage_json_path)
        return None

    totals: dict[str, object] = data.get("totals", {})
    overall_line_pct = totals.get("percent_covered")
    if overall_line_pct is None or not isinstance(overall_line_pct, (int, float)):
        logger.warning("coverage.json has no percent_covered at %s", coverage_json_path)
        return None

    # Read fail_under threshold from pyproject.toml
    threshold = 0
    if pyproject_path.exists():
        try:
            import tomllib

            with pyproject_path.open("rb") as f:
                config = tomllib.load(f)
            threshold = int(config["tool"]["coverage"]["report"]["fail_under"])
        except Exception:
            pass  # pyproject.toml without fail_under — threshold stays 0

    meta: dict[str, object] = {
        "branch_pct": totals.get("branch_percent_covered"),
        "statements_covered": totals.get("num_statements_covered"),
        "threshold": threshold,
        "source_path": str(coverage_json_path),
    }
    return float(overall_line_pct), meta


# ---------------------------------------------------------------------------
# Flaky-test reader — JSON artefact (primary) or script invocation (fallback)
# ---------------------------------------------------------------------------


def _read_flaky_count(
    repo_root: Path, *, flake_summary_json: Path | None = None
) -> tuple[float, dict[str, object]] | None:
    """Count flaky tests via direct JSON artefact or script fallback.

    The JSON file has the shape:
        {"flakes": [{"test_id": "...", "outcomes": ["PASSED", "FAILED"]}, ...]}
    """
    if flake_summary_json is not None and flake_summary_json.exists():
        try:
            data = json.loads(flake_summary_json.read_text())
            flakes: list[dict[str, object]] = data.get("flakes", [])
            flake_count = len(flakes)
            meta: dict[str, object] = {
                "source": "flake_summary_json",
                "flake_count": flake_count,
                "flakes": [f.get("test_id") for f in flakes if f.get("test_id")],
            }
            return float(flake_count), meta
        except Exception as exc:
            logger.warning("Could not parse flake summary JSON %s: %s", flake_summary_json, exc)
            return None

    log_dir = repo_root / "tests" / "output"
    log_files = [
        log_dir / "flake-detect-run1.log",
        log_dir / "flake-detect-run2.log",
        log_dir / "flake-detect-run3.log",
    ]

    if not any(f.exists() for f in log_files):
        logger.warning("No flake-detect log files found under %s", log_dir)
        return None

    script = repo_root / "scripts" / "flake_detect_aggregate.py"
    if not script.exists():
        logger.warning("flake_detect_aggregate.py not found at %s", script)
        return None

    try:
        result = subprocess.run(
            ["python3", str(script)] + [str(f) for f in log_files],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except subprocess.TimeoutExpired:
        logger.warning("flake_detect_aggregate.py timed out")
        return None
    except Exception as exc:
        logger.warning("flake_detect_aggregate.py invocation failed: %s", exc)
        return None

    flake_count = 0
    for line in result.stdout.splitlines():
        if line.startswith("Found ") and " flaky test(s):" in line:
            with suppress(IndexError, ValueError):
                flake_count = int(line.split()[1])

    meta = {
        "source": "flake_detect_aggregate_script",
        "script_exit_code": result.returncode,
        "script_stdout_lines": result.stdout.splitlines(),
        "script_stderr": result.stderr[:500] if result.stderr else None,
    }
    return float(flake_count), meta


# ---------------------------------------------------------------------------
# Assertion baseline reader
# ---------------------------------------------------------------------------


def _read_baseline_size(baseline_path: Path) -> tuple[float, dict[str, object]] | None:
    """Count non-comment, non-blank lines in the assertion baseline file.

    Lines starting with '#' are comments and are excluded.
    """
    if not baseline_path.exists():
        logger.warning("Assertion baseline not found: %s", baseline_path)
        return None

    lines = baseline_path.read_text().splitlines()
    entry_lines = [line for line in lines if line.strip() and not line.strip().startswith("#")]
    count = len(entry_lines)

    meta: dict[str, object] = {
        "total_lines": len(lines),
        "entry_lines": count,
        "comment_lines": sum(1 for line in lines if line.strip().startswith("#")),
        "blank_lines": sum(1 for line in lines if not line.strip()),
    }
    return float(count), meta


# ---------------------------------------------------------------------------
# Top-level read_sources
# ---------------------------------------------------------------------------


def read_sources(
    repo_root: str,
    *,
    flake_summary_json: Path | None = None,
) -> dict[str, tuple[float, dict[str, object]] | None]:
    """Read all four test-health artefact sources for the given repo root.

    Returns a dict with keys:
      - mutation_score
      - coverage_pct
      - flaky_test_count
      - assertion_baseline_size

    Each value is either (value, meta) or None if the source is absent/unparseable.
    Logs exactly one WARNING per missing/unparseable source. Never raises.
    """
    root = Path(repo_root)

    result: dict[str, tuple[float, dict[str, object]] | None] = {}

    result["mutation_score"] = _read_mutation_score(root)

    cov_json = root / "tests" / "output" / "coverage" / "coverage.json"
    pyproject = root / "pyproject.toml"
    result["coverage_pct"] = _read_coverage_pct(cov_json, pyproject)

    result["flaky_test_count"] = _read_flaky_count(root, flake_summary_json=flake_summary_json)

    baseline_path = root / "tests" / "assertion_free_baseline.txt"
    result["assertion_baseline_size"] = _read_baseline_size(baseline_path)

    return result


# ---------------------------------------------------------------------------
# Database operations
# ---------------------------------------------------------------------------


def _truncate_to_minute(dt: datetime) -> datetime:
    """Truncate a datetime to the minute (for idempotency grouping)."""
    return dt.replace(second=0, microsecond=0)


def capture_snapshot(
    session: Session,
    project_id: str,
    metric: str,
    value: float,
    meta: dict[str, object],
) -> TestHealthSnapshot:
    """Upsert a test-health snapshot for (project_id, metric, ts_minute).

    Re-running within the same minute with identical inputs is a no-op:
    the existing row is returned unchanged.
    """
    now = datetime.now(UTC)
    ts_minute = _truncate_to_minute(now)

    existing = session.execute(
        select(TestHealthSnapshot).where(
            TestHealthSnapshot.project_id == project_id,
            TestHealthSnapshot.metric == metric,
            TestHealthSnapshot.ts == ts_minute,
        )
    ).scalar_one_or_none()

    if existing is not None:
        return existing

    snapshot = TestHealthSnapshot(
        project_id=project_id,
        ts=ts_minute,
        metric=metric,
        value=value,
        meta=meta,
    )
    session.add(snapshot)
    session.flush()
    return snapshot


def latest(session: Session, project_id: str) -> dict[str, TestHealthSnapshot]:
    """Return the most recent snapshot per metric for a project.

    Returns a dict mapping metric name -> TestHealthSnapshot row.
    """
    subq = (
        select(
            TestHealthSnapshot.metric,
            func.max(TestHealthSnapshot.ts).label("max_ts"),
        )
        .where(TestHealthSnapshot.project_id == project_id)
        .group_by(TestHealthSnapshot.metric)
        .subquery()
    )

    stmt = (
        select(TestHealthSnapshot)
        .join(
            subq,
            (TestHealthSnapshot.metric == subq.c.metric) & (TestHealthSnapshot.ts == subq.c.max_ts),
        )
        .where(TestHealthSnapshot.project_id == project_id)
    )

    rows = session.scalars(stmt).all()
    return {row.metric: row for row in rows}


def trend(
    session: Session,
    project_id: str,
    metric: str,
    limit: int = 30,
) -> list[TestHealthSnapshot]:
    """Return the last `limit` snapshots for a given metric, newest first."""
    stmt = (
        select(TestHealthSnapshot)
        .where(
            TestHealthSnapshot.project_id == project_id,
            TestHealthSnapshot.metric == metric,
        )
        .order_by(TestHealthSnapshot.ts.desc())
        .limit(limit)
    )
    return list(session.scalars(stmt).all())
