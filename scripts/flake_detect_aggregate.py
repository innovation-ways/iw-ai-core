#!/usr/bin/env python3
"""Aggregate pytest log files from `make test-flake-detect` and report flakes.

A flake is a test whose outcome (PASSED/FAILED) differs across the supplied
log files. Exit 1 if any flake is detected so a nightly cron can alert.

Usage:
    flake_detect_aggregate.py run1.log run2.log run3.log [...]
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

# pytest line format (default -v output): "tests/foo.py::test_bar PASSED [ 12%]"
_TEST_LINE_RE = re.compile(
    r"^(?P<test_id>[\w./:\[\]\-\,]+?::[\w\[\]\-]+)\s+"
    r"(?P<outcome>PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS)\b"
)


def parse_log(path: Path) -> dict[str, str]:
    """Return {test_id: outcome} for tests with a definitive PASSED/FAILED line."""
    outcomes: dict[str, str] = {}
    for line in path.read_text(errors="replace").splitlines():
        m = _TEST_LINE_RE.match(line.strip())
        if m:
            tid = m.group("test_id")
            outcome = m.group("outcome")
            # Last-write-wins is fine — pytest reports each test once per run
            outcomes[tid] = outcome
    return outcomes


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(  # noqa: T201
            "Usage: flake_detect_aggregate.py run1.log run2.log [run3.log ...]",
            file=sys.stderr,
        )
        return 2

    logs = [Path(p) for p in argv[1:]]
    for log in logs:
        if not log.exists():  # noqa: T201
            print(f"ERROR: log file not found: {log}", file=sys.stderr)  # noqa: T201
            return 2

    per_run: list[dict[str, str]] = [parse_log(p) for p in logs]

    # Union of all test ids seen
    all_ids: set[str] = set()
    for run in per_run:
        all_ids.update(run)

    flakes: dict[str, list[str]] = defaultdict(list)
    for tid in sorted(all_ids):
        outcomes = [run.get(tid, "ABSENT") for run in per_run]
        # A flake is a test with both PASSED and FAILED outcomes across runs
        distinct = {o for o in outcomes if o in ("PASSED", "FAILED")}
        if len(distinct) > 1:
            flakes[tid] = outcomes

    n_runs = len(logs)
    print(f"Flake detection over {n_runs} runs of the full suite")  # noqa: T201
    print()  # noqa: T201
    if not flakes:
        print("No flakes detected.")  # noqa: T201
        return 0

    print(f"Found {len(flakes)} flaky test(s):")  # noqa: T201
    for tid, outcomes in flakes.items():
        print(f"  {tid}")  # noqa: T201
        for i, outcome in enumerate(outcomes, start=1):
            print(f"    run {i}: {outcome}")  # noqa: T201
    print()  # noqa: T201
    print(  # noqa: T201
        "Recommendation: file an incident, add "
        '`@pytest.mark.quarantine(reason="I-NNNNN: ...")`'
        ", exclude from merge gate."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
