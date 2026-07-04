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
You can drive the **entire** lifecycle — author, approve, batch, monitor,
recover — through the MCP tools listed below.  You do not need to shell out to
the `iw` CLI for any of it.

## Lifecycle (which tool to call, in order)

1. **Author the design doc** — use the project's IW skills (e.g. `/iw-new-feature`,
   `/iw-new-incident`, `/iw-new-cr`) directly in your own context.  These skills
   produce the design doc + workflow manifest.  Then register it:

2. **Register the item** — `work_item_register` (writes the item to the DB,
   status → `draft`).  Pass the design doc via `design_doc_path` /
   `design_doc_content` and steps via `manifest_path` / `manifest_steps`.
   Use `dry_run=True` first to preview without writing.  If you need a fresh ID,
   call `work_item_next_id` (allocates e.g. `CR-00042`).

3. **Approve the item** — `work_item_approve`.  Status: `draft` → `approved`.

4. **Create a batch** — `batch_create` with the list of approved `item_ids`.
   Status → `planning`.  Use `dry_run=True` to preview the execution-group plan.

5. **Approve the batch** — `batch_approve`.  Status → `approved`.  The daemon
   picks it up on its next poll (default every 60 s) and launches worktrees.

6. **Poll batch status** — `batch_status`.  Transitions: `approved` →
   `executing` → `completed` (or `completed_with_errors` if any item failed).
   `job_list` and `worktree_status` give complementary background views.

7. **Poll individual items** — `work_item_get` for step-level progress.

8. **Resolve errors** — the daemon runs its own fix-cycles automatically.  If an
   item still dead-ends (`failed`/`stalled`), call `item_retry` to re-drive it
   from the first non-completed step.  Pause/resume a running batch with
   `batch_control`.

9. **Confirm the merge** — the daemon squash-merges automatically.  If a merge
   gate is configured, release it with `approve_merge`.

10. **Archive** — after a merged item is confirmed correct, `work_item_archive`
    moves it to the archive tier.

## Key identifiers

- **project_id**: Short slug (e.g. `iw-ai-core`).  Use `project_list` to discover.
- **item_id**: Prefixed sequential ID (`F-NNNNN`, `I-NNNNN`, `CR-NNNNN`, `R-NNNNN`).
- **batch_id**: `BATCH-NNNNN`.

## Read-only tools (always available)

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

## Write tools (present only when the server has writes enabled)

Write tools register only when the server is launched with
`IW_CORE_MCP_ENABLE_WRITE_TOOLS=true`.  If you don't see them, the operator has
kept the server read-only.  Each tool carries a **blast-radius tier** that sets
its default approval policy:

| Tier | Default | Tools |
|------|---------|-------|
| 1 | allow | `work_item_next_id`, `work_item_register` |
| 2 | ask | `work_item_approve`, `batch_create`, `batch_approve`, `batch_control`, `item_retry` |
| 3 | deny | `approve_merge`, `batch_cancel`, `work_item_archive`, `work_item_cancel` |

Defaults can be overridden per project + per tool by the operator
(`iw mcp policy set <project> <tool> allow|ask|deny`), so the effective decision
you get may differ from the table above.

## Approval handshake (for `ask` / gated tools)

When a tool's effective policy is **ask**, calling it without an
`approval_token` returns an `approval_required` envelope containing a `token`
instead of executing.  To proceed:

1. A human runs `iw mcp approve <token>` (or `iw mcp deny <token>`).
2. You **retry the same tool call** with `approval_token` set to that token.

When the policy is **allow**, the tool executes immediately with no token.
When it is **deny**, the call is refused and no token can release it.
Tier-2/3 tools also accept `dry_run=True` (where applicable) so you can preview
side-effects before requesting approval.
"""


def register(mcp: FastMCP) -> None:
    """Register the iwcore_workflow_guide prompt on the given FastMCP instance.

    Args:
        mcp: The :class:`fastmcp.FastMCP` server to register the prompt on.
    """
    mcp.prompt(name="iwcore_workflow_guide")(workflow_guide)
