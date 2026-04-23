"""Backfill a functional design document for a work item.

Invokes opencode (with the MiniMax-M2.7 model configured in .opencode/opencode.json)
to distil the technical design document into a short, plain-English functional
document written for humans — product owners, support, and engineers onboarding
to the codebase.

Usage:
    uv run python scripts/backfill_functional_doc.py <WORK_ITEM_ID> [--force]

Examples:
    uv run python scripts/backfill_functional_doc.py I-00099
    uv run python scripts/backfill_functional_doc.py F-00055 --force

Exit codes:
    0  success
    2  usage error (bad ID format)
    3  could not resolve current project (.iw-orch.json not found)
    4  work item not found in DB
    5  output file already exists (pass --force to overwrite)
    6  opencode completed but did not produce the expected file
    >0 opencode subprocess exit code
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

from orch.cli.utils import find_project_root
from orch.db.models import WorkItem
from orch.db.session import SessionLocal

ID_PATTERN = re.compile(r"^(F|I|CR)-\d{5}$")

TYPE_LABEL = {
    "F": "Feature",
    "I": "Incident",
    "CR": "Change Request",
}


def _build_prompt(item: WorkItem, output_path: Path) -> str:
    prefix = item.id.split("-", 1)[0]
    type_label = TYPE_LABEL.get(prefix, "Work Item")
    design_doc = (
        item.design_doc_content or ""
    ).strip() or "(no technical design document stored in DB)"
    summary = item.summary or "(none)"

    return f"""You are writing the FUNCTIONAL DESIGN DOCUMENT for work item {item.id}.

A functional design document is written for HUMAN readers — product owners,
support staff, and engineers onboarding to the codebase. It is NOT for an AI
agent to implement against. It captures the REASONING behind the work, the
PROBLEM it solved, and what the user or operator actually EXPERIENCES as a
result. The existing technical design document already covers the implementation;
do not duplicate it.

## Input — Technical Design Document

- Work item: {item.id}
- Type: {type_label}
- Title: {item.title}
- Summary: {summary}

--- TECHNICAL DESIGN BEGIN ---
{design_doc}
--- TECHNICAL DESIGN END ---

## Your Task

Using ONLY the information above, write a functional design document and SAVE IT
(using your Write tool) to this exact path:

    {output_path}

The document must be valid markdown with these exact H1/H2 headings:

    # {item.id} — Functional Design

    ## Why
    Two to four sentences explaining why this work was requested — the problem,
    the trigger (user complaint, incident, new requirement, ...), and the goal.
    Cite motivation from the technical design but phrase it in plain English.

    ## What Changed (for the User)
    Bullet list or short prose describing what a user, operator, or dashboard
    viewer experiences that is different after this work shipped. Focus on
    OBSERVABLE behaviour, not internal mechanics.

    ## How It Behaves
    The functional flow, happy path, and notable edge cases, in plain English.
    A non-engineer reading this should be able to predict what the system does
    in common scenarios.

    ## Out of Scope
    One or two bullets naming things a reader might reasonably assume are part
    of this work but are NOT. Omit this section entirely if the technical
    design does not make out-of-scope items clear.

## Hard Constraints

- DO NOT mention file paths, module names, class names, function names, database
  columns, SQL, or specific API endpoints.
- DO NOT describe implementation steps, migrations, code structure, or test
  strategy.
- DO NOT copy large fragments of the technical design doc verbatim — paraphrase.
- Keep the total document under 500 words.
- If the technical design is empty or thin, add a brief italicised note at the
  top ("_Backfilled from limited technical-design context._") and produce the
  best functional summary you can from the title and summary alone.

## Output

Write the markdown file to {output_path} using your Write tool. Do not echo the
markdown back in chat. Do not ask for confirmation. Just write the file and stop.
"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a functional design doc for a work item via opencode + MiniMax-M2.7."
    )
    parser.add_argument("work_item_id", help='Work item ID, e.g. "I-00099", "F-00055", "CR-00011"')
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the functional doc file if it already exists",
    )
    args = parser.parse_args()

    item_id: str = args.work_item_id
    if not ID_PATTERN.match(item_id):
        print(
            f"ERROR: invalid work item ID '{item_id}' — expected F-NNNNN, I-NNNNN, or CR-NNNNN",
            file=sys.stderr,
        )
        return 2

    found = find_project_root(Path.cwd())
    if not found:
        print(
            "ERROR: could not locate .iw-orch.json — run from inside a managed project",
            file=sys.stderr,
        )
        return 3
    project_id, repo_root = found

    with SessionLocal() as session:
        item = session.get(WorkItem, (project_id, item_id))
        if item is None:
            print(
                f"ERROR: work item {item_id} not found in project {project_id}",
                file=sys.stderr,
            )
            return 4
        session.expunge(item)

    item_dir = repo_root / "ai-dev" / "active" / item_id
    item_dir.mkdir(parents=True, exist_ok=True)
    output_path = item_dir / f"{item_id}_Functional.md"

    if output_path.exists() and not args.force:
        print(
            f"ERROR: {output_path.relative_to(repo_root)} already exists — pass --force to overwrite",
            file=sys.stderr,
        )
        return 5

    if args.force and output_path.exists():
        output_path.unlink()

    prompt = _build_prompt(item, output_path)

    print(f"Generating functional doc for {item_id} ({item.title!r})")
    print(f"  Output: {output_path.relative_to(repo_root)}")
    print("  Model:  minimax/MiniMax-M2.7 (from .opencode/opencode.json)")
    print()

    result = subprocess.run(
        ["opencode", "run", prompt, "--dangerously-skip-permissions"],
        cwd=repo_root,
        stdin=subprocess.DEVNULL,
    )
    if result.returncode != 0:
        print(f"ERROR: opencode exited with code {result.returncode}", file=sys.stderr)
        return result.returncode

    if not output_path.exists():
        print(
            f"ERROR: opencode finished but did not create {output_path.relative_to(repo_root)}",
            file=sys.stderr,
        )
        return 6

    size = output_path.stat().st_size
    print()
    print(f"Wrote {output_path.relative_to(repo_root)} ({size} bytes)")
    print("Review the file, edit if needed, then commit to git — git is the only history.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
