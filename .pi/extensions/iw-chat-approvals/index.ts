/**
 * iw-chat-approvals — Pi extension that bridges the IW AI Core chat
 * approval policy to Pi's tool_call hook (F-00087).
 *
 * Policy source of truth: `.opencode/opencode.json` in the repo root.
 * This file is shared with the OpenCode runtime so both runtimes
 * enforce the same user-configured permissions without duplication.
 *
 * Confirm request id namespace:
 *   Pi auto-prefixes ctx.ui.confirm request ids with the extension name
 *   ("iw-chat-approvals."), so every confirm issued by this extension
 *   has an id of the form "iw-chat-approvals.<rid>".  The Python event
 *   normalizer (orch/chat/pi/event_normalizer.py) routes events whose
 *   id starts with "iw-chat-approvals." to the permission.asked envelope,
 *   making them visible in the dashboard's approval UI.
 *
 * NOTE (best-effort): the Pi extension manifest shape (subscribe(), ctx.ui,
 * hook names) is inferred from CR-00062 references and agents/pi/*.md docs.
 * If the Pi SDK changes this contract, this file needs to be updated.
 */

import * as fs from "fs";
import * as path from "path";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Permission {
  bash?: Record<string, "allow" | "ask" | "deny">;
  external_directory?: "allow" | "ask" | "deny";
}

interface OpenCodeConfig {
  permission?: Permission;
}

interface ToolCallEvent {
  tool: string;
  args: Record<string, unknown>;
  ctx: {
    repoRoot?: string;
    ui: {
      confirm(opts: {
        tool: string;
        args: Record<string, unknown>;
        question: string;
      }): Promise<boolean>;
    };
  };
}

// ---------------------------------------------------------------------------
// Policy cache — loaded once per session, keyed by repoRoot
// ---------------------------------------------------------------------------

const _policyCache = new Map<string, Permission>();

function _loadPolicy(repoRoot: string): Permission {
  const cached = _policyCache.get(repoRoot);
  if (cached !== undefined) {
    return cached;
  }
  const configPath = path.join(repoRoot, ".opencode", "opencode.json");
  let policy: Permission = {};
  try {
    const raw = fs.readFileSync(configPath, "utf-8");
    const parsed: OpenCodeConfig = JSON.parse(raw);
    policy = parsed.permission ?? {};
  } catch (err) {
    if ((err as NodeJS.ErrnoException).code === "ENOENT") {
      // Missing file — fail-safe: all "allow"
      policy = {};
    } else {
      // Malformed JSON or unexpected error — fail-safe: all "ask"
      // (conservative: surfaces to user rather than silently allowing)
      policy = {
        bash: { "*": "ask" },
        external_directory: "ask",
      };
      console.warn(
        "[iw-chat-approvals] Failed to parse opencode.json; defaulting to ask-all:",
        err
      );
    }
  }
  _policyCache.set(repoRoot, policy);
  return policy;
}

// ---------------------------------------------------------------------------
// Tool-call policy resolution
// ---------------------------------------------------------------------------

function _resolveBashDecision(
  args: Record<string, unknown>,
  bashPolicy: Record<string, "allow" | "ask" | "deny">
): "allow" | "ask" | "deny" {
  // Extract the command word from args.command (first space-delimited token).
  const command = typeof args.command === "string" ? args.command.trim() : "";
  const commandWord = command.split(/\s+/)[0] ?? "";

  // Walk policy keys in definition order; first glob match wins.
  for (const [pattern, decision] of Object.entries(bashPolicy)) {
    if (_globMatch(commandWord, pattern) || _globMatch(command, pattern)) {
      return decision;
    }
  }
  // No match — default allow.
  return "allow";
}

/**
 * Minimal glob matching: supports "*" as wildcard, "?" as single-char wildcard.
 * Pi does not depend on any external glob library, so we implement inline.
 */
function _globMatch(str: string, pattern: string): boolean {
  // Escape regex special chars except * and ?
  const regexStr = pattern
    .replace(/[.+^${}()|[\]\\]/g, "\\$&")
    .replace(/\*/g, ".*")
    .replace(/\?/g, ".");
  return new RegExp(`^${regexStr}$`).test(str);
}

// ---------------------------------------------------------------------------
// Extension entry point
// ---------------------------------------------------------------------------

let _sessionPolicy: Permission | null = null;

export function subscribe(hooks: {
  on(
    event: "session_start" | "tool_call",
    handler: (event: unknown) => Promise<void> | void
  ): void;
}): void {
  hooks.on("session_start", (event: unknown) => {
    const ev = event as { repoRoot?: string };
    const repoRoot = ev.repoRoot ?? process.cwd();
    // Invalidate any cached policy so each new session re-reads from disk
    // (picks up edits to .opencode/opencode.json made since last session).
    _policyCache.delete(repoRoot);
    _sessionPolicy = _loadPolicy(repoRoot);
  });

  hooks.on("tool_call", async (event: unknown) => {
    const ev = event as ToolCallEvent;
    const policy = _sessionPolicy ?? {};

    let decision: "allow" | "ask" | "deny" = "allow";

    if (ev.tool === "bash") {
      const bashPolicy = policy.bash ?? {};
      decision = _resolveBashDecision(ev.args, bashPolicy);
    } else if (
      ev.tool === "read_file" ||
      ev.tool === "write_file" ||
      ev.tool === "list_directory"
    ) {
      decision = policy.external_directory ?? "allow";
    }
    // All other tools: default "allow"

    if (decision === "allow") {
      return;
    }

    if (decision === "deny") {
      throw new Error(
        `[iw-chat-approvals] Tool call denied by policy: ${ev.tool}(${JSON.stringify(ev.args)})`
      );
    }

    // decision === "ask" — surface to user via Pi confirm UI.
    // Pi auto-prefixes the request id with "iw-chat-approvals." which is
    // how the Python event normalizer routes it to permission.asked.
    const question = `Allow tool "${ev.tool}" with args: ${JSON.stringify(ev.args, null, 2)}?`;
    const approved = await ev.ctx.ui.confirm({ tool: ev.tool, args: ev.args, question });
    if (!approved) {
      throw new Error(
        `[iw-chat-approvals] Tool call denied by user: ${ev.tool}(${JSON.stringify(ev.args)})`
      );
    }
  });
}
