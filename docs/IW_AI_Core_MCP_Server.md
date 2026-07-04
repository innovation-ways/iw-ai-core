# IW AI Core — MCP Server (Agent Control Layer)

This document explains the **MCP (Model Context Protocol) server** that exposes IW AI Core to autonomous LLM agents — most notably the local **Hermes** agents. It is the operator + integration guide: what the server is, how to run and register it, the full tool catalogue, the policy/approval model, and the security posture. The design rationale lives in research doc [R-00165](research/R-00165-agent-control-mcp-server.md).

> **One-line summary.** Point an MCP client (Hermes) at `iw-mcp` over stdio, and an agent can drive the full work-item lifecycle — create → approve → batch → run → monitor → confirm → archive — through typed, self-describing tools, under a configurable Deny→Ask→Allow policy with a full audit trail.

---

## 1. What this is (and what AI CORE is)

**IW AI Core** is an AI-development orchestration platform. A background **daemon** polls PostgreSQL, picks up approved **batches** of **work items** (Features `F-`, Incidents `I-`, Change Requests `CR-`, Research `R-`), runs LLM agents in isolated git worktrees, and squash-merges results to `main`. Humans normally drive it through a web dashboard and the `iw` CLI.

The **MCP server** (`orch/mcp/`) is a second, agent-facing skin over the **same service layer** the `iw` CLI uses (`orch/services/`). It does **not** duplicate business logic — every tool is a thin wrapper that calls a service function and returns the same structured data the CLI's `--json` mode returns. This is the "one service layer, two skins" design.

```
Hermes (MCP client)  ──stdio JSON-RPC──►  iw-mcp (FastMCP server)
                                              │  tools → orch/services/*  ──► PostgreSQL (orch DB, :5433)
iw CLI (operator)    ───────────────────────►┘  (same service functions)
```

Why MCP rather than "just the CLI"? For a local agent the CLI is efficient, but MCP adds four things a CLI cannot: **typed self-describing tool discovery** (Hermes learns the surface with no hand-maintained skill file), a **native human-in-the-loop approval primitive** (elicitation), **machine-readable risk annotations** (`readOnlyHint`/`destructiveHint`), and a clean path to remote/multi-client use. See R-00165 §5 for the full argument.

---

## 2. Running the server

The server speaks **stdio** (the client launches it as a subprocess) — the right transport for same-host use. Two equivalent entry points:

```bash
iw-mcp            # console-script entry point (pyproject [project.scripts])
iw mcp serve      # same thing, as an iw subcommand
```

It connects to the orchestration DB using the standard `orch.config` settings (read from `.env`), under the same `iw_cli_orch_bridge` the CLI uses, so the live-DB guard permits it. The app DB role (`iw_orch`) is intentionally **non-superuser** — keep it that way; it is the authoritative least-privilege backstop.

**Read-only by default.** Write tools are **not registered** unless you opt in:

```bash
export IW_CORE_MCP_ENABLE_WRITE_TOOLS=true   # exposes the create/approve/batch/… tools
```

With the flag unset, only the 8 read tools are exposed — a safe first deployment that lets Hermes *observe* the platform before it can *change* it (the PagerDuty `--enable-write-tools` pattern).

---

## 3. Registering the server with Hermes

Hermes reads `~/.hermes/config.yaml`. Add the server under `mcp_servers`. Because Hermes launches the subprocess and passes only a filtered environment, run it through `uv` pinned to the repo directory so it finds the project venv and `.env`:

```yaml
mcp_servers:
  iwcore:
    command: "uv"
    args: ["--directory", "/home/sergiog/dev/iw-doc-plan/main/iw-ai-core", "run", "iw-mcp"]
    env:
      # Optional: enable write tools for this agent (default: read-only)
      IW_CORE_MCP_ENABLE_WRITE_TOOLS: "true"
    enabled: true
    timeout: 300
    tools:
      # RECOMMENDED allowlist — start with the smallest set. Add write tools
      # deliberately. Hermes exposes tools to the model as mcp_iwcore_<tool>.
      include:
        - project_list
        - work_item_list
        - work_item_get
        - batch_list
        - batch_status
        - job_list
        - worktree_status
        - daemon_status
        - workflow_guide      # the governed-workflow MCP prompt
      exclude: []
```

After editing, reload inside a Hermes session with `/reload-mcp`, and smoke-test with `hermes mcp test iwcore`. Tools appear to the model as **`mcp_iwcore_<tool>`** (e.g. `mcp_iwcore_batch_status`). There is also an MCP **prompt**, `iwcore_workflow_guide`, that teaches the governed lifecycle on demand.

> **Defense in depth.** The `tools.include` allowlist is a *client-side* lever. The server *also* enforces the write-enable flag and the policy engine server-side, so an agent cannot execute a gated action just because a tool is in its list.

---

## 4. Tool catalogue

Tools are grouped by **blast-radius tier** (R-00165 §5.6). Each tier has a default policy (see §5). Names below are the raw tool names; Hermes sees them prefixed `mcp_iwcore_`.

### Tier 0 — read-only (always available, `readOnlyHint: true`)

| Tool | Purpose |
|------|---------|
| `project_list` | List registered projects (use the `id` as `project_id` elsewhere). |
| `work_item_list` | List work items, filtered by status/type/phase, cursor-paginated (cap 50). |
| `work_item_get` | Full status of one item + its steps (same shape as `iw item-status --json`). |
| `batch_list` | List batches for a project, optional status filter. |
| `batch_status` | Full status of one batch + its items (poll this to watch execution). |
| `job_list` | Unified background-job view (batches, doc-gen, code-index, research). |
| `worktree_status` | Active agent worktrees for a project (DB-derived). |
| `daemon_status` | Daemon liveness + poll/step/batch stats. |

### Tier 1 — reversible writes (default **allow**, audited)

| Tool | Purpose |
|------|---------|
| `work_item_next_id` | Allocate the next sequential ID for a type (e.g. `I-00042`). |
| `work_item_register` | Register a work item (idempotent). Accepts **file paths** *or* **inline** `design_doc_content` + `manifest_steps`. `dry_run=true` returns a preview without writing. |

### Tier 2 — consequential / triggers execution (default **ask**, `destructiveHint` where apt)

| Tool | Purpose |
|------|---------|
| `work_item_approve` | draft → approved (eligible for batching). |
| `batch_create` | Plan a batch from approved item IDs. |
| `batch_approve` | Queue a batch for the daemon (async — poll `batch_status`). |
| `batch_control` | Pause/resume a batch (`action="pause"|"resume"`). |
| `item_retry` | Re-drive a dead-ended item after the root cause is fixed. |

### Tier 3 — irreversible / high blast radius (default **deny**, `destructiveHint: true`)

| Tool | Purpose |
|------|---------|
| `approve_merge` | Approve a batch item's merge to `main`. |
| `batch_cancel` | Cancel a batch and (optionally) reset its items. |
| `work_item_archive` | Archive a completed item (Tier-1 DB + Tier-2 `.tar.zst`). |
| `work_item_cancel` | Cancel a single non-batch item. |

**Async execution.** `batch_approve` does not run the batch synchronously — it marks the batch approved and the daemon picks it up on its next poll (default 60 s). The agent should **poll `batch_status`** until a terminal status. Never expect a batch to complete within one tool call.

---

## 5. The policy model — configurable autonomy

Every gated tool call resolves to one of three decisions before it runs:

- **allow** — execute immediately (audited).
- **ask** — require a human approval (see §6).
- **deny** — refuse with a clear error.

The effective decision is resolved in **priority order** (first match wins):

1. **DB override** — an `mcp_policies` row for `(project_id, tool_name)`, set via `iw mcp policy set`.
2. **`projects.toml`** — a `[projects.<id>.mcp_policy]` block folded into `Project.config`.
3. **Built-in tier default** — Tier 0/1 → allow, Tier 2 → ask, Tier 3 → deny.

### Configuring per project (static)

```toml
[projects.iw-ai-core.mcp_policy]
default = "ask"            # fallback for any gated tool
tier2 = "allow"            # let this agent run the create→approve→batch flow autonomously
work_item_archive = "ask"  # but still gate archiving
approve_merge = "deny"     # never let the agent merge to main
```

Keys may be a **tool name**, a **tier** (`tier1`/`tier2`/`tier3`), or `default`. Precedence: exact tool > tier > default. Values: `allow` / `ask` / `deny`. Reload with `./ai-core.sh daemon reload` (SIGHUP) so the registry syncs it to `Project.config`.

### Configuring at runtime (overrides)

```bash
iw mcp policy set iw-ai-core batch_approve allow   # highest-priority override
iw mcp policy list iw-ai-core
```

**Dialling autonomy.** The default posture is safe (Tier-2 asks, Tier-3 denies). To let Hermes run the full lifecycle unattended, set Tier-2 to `allow` and choose which Tier-3 actions (if any) it may take; keep `approve_merge`/`work_item_archive` gated for a human unless you have high confidence in CORE's automated merge gates.

---

## 6. The approval flow (human-in-the-loop)

When a tool resolves to **ask**, the server needs a human decision. It supports two paths (chosen automatically — the "graceful" model):

**A. Approval-required return (the path Hermes uses).** Hermes's harness does not implement MCP elicitation, so the tool returns an envelope instead of executing:

```json
{
  "status": "approval_required",
  "approval_token": "kJ3…",
  "tool": "batch_approve",
  "expires_in_seconds": 3600,
  "how_to_approve": "A human must run `iw mcp approve kJ3…` (or deny with `iw mcp deny kJ3…`), then retry this tool call passing approval_token=kJ3…."
}
```

A human then decides, and the agent retries with the token:

```bash
iw mcp approvals                 # list pending requests
iw mcp approve kJ3…              # or: iw mcp deny kJ3…
```

The agent re-invokes the same tool with `approval_token="kJ3…"`; the server redeems the token (one-time, TTL-bounded) and executes. Tokens expire after `IW_CORE_MCP_APPROVAL_TTL_SECONDS` (default 3600).

**B. MCP elicitation (for clients that support it).** If the client advertises elicitation, the server prompts for confirmation mid-call via `ctx.elicit`; on accept it executes, on decline it refuses. Nothing depends on this — clients without elicitation (Hermes) transparently fall back to path A.

---

## 7. Security posture

The server wraps a production orchestration DB with partly-irreversible actions, so it is built defensively even though it runs locally (R-00165 §5.8):

- **Read-only by default** — write tools absent from the catalogue unless `IW_CORE_MCP_ENABLE_WRITE_TOOLS=true`.
- **Least privilege at the DB role** — `iw_orch` is non-superuser; this is the authoritative backstop that survives any prompt-injection.
- **Tiered gates** — Tier-3 (irreversible) defaults to deny; the most destructive operations (force-reset, bulk delete, raw DB ops) are **not exposed over MCP at all** — they remain operator-only in the CLI.
- **Untrusted tool output** — work-item text, logs, and commit messages returned by tools are attacker-influenceable. Treat them as untrusted content; do not let a tool result auto-authorise another destructive tool. This is why gates are enforced **server-side**, not by client-side tool annotations (which are only hints).
- **Audit everything** — every write/gated tool call writes an append-only `mcp_audit_log` row (tool, scrubbed arguments, decision, outcome, error). Secrets in arguments are redacted before storage.

---

## 8. Configuration reference

| Env var | Default | Purpose |
|---------|---------|---------|
| `IW_CORE_MCP_ENABLE_WRITE_TOOLS` | `false` | Expose Tier-1/2/3 write tools. Off = read-only server. |
| `IW_CORE_MCP_APPROVAL_TTL_SECONDS` | `3600` | Lifetime of an approval token before it expires. |
| (all standard `IW_CORE_DB_*`) | — | Orchestration DB connection (read from `.env`). |

---

## 9. `iw mcp` command reference

```
iw mcp serve                                  Launch the MCP server over stdio
iw mcp approve <token> [--by <who>]           Approve a pending approval request
iw mcp deny <token> [--by <who>]              Deny a pending approval request
iw mcp approvals [--status <s>] [--json]      List approval requests
iw mcp policy set <project> <tool> <decision> Upsert a per-tool policy override (allow|ask|deny)
iw mcp policy list [<project>] [--json]        List policy overrides
```

---

## 10. Related documents

- [R-00165 — Exposing IW AI Core to Autonomous Agents (MCP vs CLI)](research/R-00165-agent-control-mcp-server.md) — the research and design rationale.
- [Hermes onboarding skill](hermes/iw-ai-core/SKILL.md) — the drop-in `SKILL.md` that teaches a Hermes agent what AI CORE is and the governed workflow.
- [`IW_AI_Core_CLI_Spec.md`](IW_AI_Core_CLI_Spec.md) — the full `iw` CLI reference (includes `iw mcp`).
- [`IW_AI_Core_Architecture.md`](IW_AI_Core_Architecture.md) — the platform architecture.
