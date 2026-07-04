"""MCP prompt definitions for IW AI Core.

Provides the ``iwcore_workflow_guide`` prompt that gives agents a concise
description of the governed work-item lifecycle so they can drive
orchestration correctly without needing to read internal documentation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastmcp import FastMCP


def workflow_guide() -> str:
    """Return a concise description of the IW AI Core governed workflow.

    This prompt is the agent's primary guide for orchestrating work through
    IW AI Core.  It describes the create → approve → batch → poll → archive
    lifecycle so agents know which MCP tools to call in which order.

    Returns:
        Markdown string with the governed-workflow description.
    """
    return """\
# IW AI Core — Governed Workflow Guide

IW AI Core is an AI orchestration platform.  All engineering work is modelled
as **work items** that flow through a governed lifecycle executed by the daemon.

## Lifecycle

1. **Author the design doc** — use the project's IW skills (e.g. `/iw-new-feature`,
   `/iw-new-incident`, `/iw-new-cr`) directly in the agent's context.  These skills
   create the design doc, allocate the item ID (e.g. `F-00123`), and register the
   item in the DB (status → `draft`).

2. **Register the item** — the skills call `iw register` which persists the
   design doc and workflow steps to the DB.

3. **Approve the item** — after reviewing the design, call `iw approve <item-id>`.
   Status transitions: `draft` → `approved`.  The daemon will pick it up on the
   next poll cycle.

4. **Create a batch** — group one or more approved items together:
   `iw batch-create --items F-00123 ...`.  Status → `planning`.

5. **Approve the batch** — `iw batch-approve <batch-id>`.  Status → `approved`.
   The daemon picks up approved batches and begins launching worktrees.

6. **Poll batch status** — use the `batch_status` MCP tool to monitor progress.
   Batch status transitions: `approved` → `executing` → `completed` (or
   `completed_with_errors` if any item failed).

7. **Poll individual items** — use `work_item_get` to inspect step-level
   progress within a running item.

8. **Resolve errors** — if items stall or fail, use `iw item-retry` (CLI) to
   re-drive recovery.  The daemon resumes from the first non-completed step.

9. **Archive** — after a merged item is confirmed correct, `iw archive <item-id>`
   moves it to the archive tier.

## Key identifiers

- **project_id**: Short slug (e.g. `iw-ai-core`).  Use `project_list` to discover.
- **item_id**: Prefixed sequential ID (`F-NNNNN`, `I-NNNNN`, `CR-NNNNN`, `R-NNNNN`).
- **batch_id**: `BATCH-NNNNN`.

## Read-only tools available

| Tool | Purpose |
|------|---------|
| `project_list` | List all registered projects |
| `work_item_list` | Paginated list of items with optional filters |
| `work_item_get` | Full item + step status |
| `batch_list` | List batches for a project |
| `batch_status` | Full batch + batch-item status |
| `job_list` | Unified background-job view |
| `worktree_status` | Active agent worktrees |
| `daemon_status` | Daemon liveness + operational stats |

All tools are read-only (`readOnlyHint=true`).  Authoring design docs and
issuing approve/batch-create commands is done via the agent's own IW skills
and the `iw` CLI — not via MCP tools.
"""


def register(mcp: FastMCP) -> None:
    """Register the iwcore_workflow_guide prompt on the given FastMCP instance.

    Args:
        mcp: The :class:`fastmcp.FastMCP` server to register the prompt on.
    """
    mcp.prompt(name="iwcore_workflow_guide")(workflow_guide)
