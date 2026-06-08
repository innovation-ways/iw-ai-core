/**
 * iw-chat-approvals — Pi extension that bridges the IW AI Core chat
 * approval policy to Pi's `tool_call` hook (F-00087).
 *
 * Policy source of truth: `.opencode/opencode.json` in the repo root.
 * This file is shared with the OpenCode runtime so both runtimes
 * enforce the same user-configured permissions without duplication.
 *
 * Pi extension contract (verified against @earendil-works/pi-coding-agent
 * 0.79.0, dist/core/extensions/loader.js + types.d.ts):
 *   - The module MUST default-export a factory `(api: ExtensionAPI) => void`.
 *     The loader does `const factory = module; await factory(api)` and rejects
 *     any module whose default export is not a function with
 *     "Extension does not export a valid factory function".
 *   - Handlers are registered via `api.on(event, handler)` where
 *     `handler(event, ctx)`; the `tool_call` handler returns
 *     `{ block: true, reason }` to veto a call (it does NOT throw).
 *   - `tool_call` events carry `event.toolName` and `event.input`
 *     (built-in tool names are: bash, read, write, edit, grep, find, ls).
 *   - User prompts go through `ctx.ui.confirm(title, message)`.
 */

import * as fs from "fs";
import * as path from "path";

// ---------------------------------------------------------------------------
// Types — minimal local shapes for the bits of the Pi API we touch.
// ---------------------------------------------------------------------------

type Decision = "allow" | "ask" | "deny";

type GlobMap = Record<string, Decision>;

interface Permission {
  bash?: GlobMap;
  /**
   * In the actual `.opencode/opencode.json` this is a glob map (e.g.
   * `{"*": "allow"}`), matched against the resolved file path.
   */
  external_directory?: GlobMap;
}

interface OpenCodeConfig {
  permission?: Permission;
}

interface ToolCallEvent {
  toolName: string;
  input: Record<string, unknown>;
}

interface ToolCallEventResult {
  block?: boolean;
  reason?: string;
}

interface ExtensionContext {
  cwd: string;
  hasUI: boolean;
  ui: {
    confirm(title: string, message: string): Promise<boolean>;
  };
}

interface ExtensionAPI {
  on(
    event: string,
    handler: (event: unknown, ctx: ExtensionContext) => unknown
  ): void;
}

// Tools whose access is governed by the `external_directory` policy and which
// expose a single `path` argument in their tool-call input.
const _FILE_TOOLS = new Set(["read", "write", "edit", "ls", "find", "grep"]);

// Confirm-dialog title — a stable marker the dashboard RPC normalizer keys on
// (orch/chat/pi/event_normalizer.py) to route this extension's prompts to the
// approval modal. The structured payload (tool name + args) travels in the
// message as a JSON envelope so the dashboard can render tool/args.
const _CONFIRM_TITLE = "iw-chat-approvals";

// ---------------------------------------------------------------------------
// Policy cache — keyed by repoRoot, re-read each session_start.
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
      // Missing file — fail-safe: all "allow".
      policy = {};
    } else {
      // Malformed JSON or unexpected error — fail-safe: all "ask"
      // (conservative: surfaces to user rather than silently allowing).
      policy = {
        bash: { "*": "ask" },
        external_directory: { "*": "ask" },
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
// Policy resolution
// ---------------------------------------------------------------------------

/**
 * Minimal glob matching: supports "*" as wildcard, "?" as single-char wildcard.
 * Pi does not depend on any external glob library, so we implement inline.
 */
function _globMatch(str: string, pattern: string): boolean {
  const regexStr = pattern
    .replace(/[.+^${}()|[\]\\]/g, "\\$&")
    .replace(/\*/g, ".*")
    .replace(/\?/g, ".");
  return new RegExp(`^${regexStr}$`).test(str);
}

/** Walk a glob map in definition order; first match wins, else "allow". */
function _matchGlobMap(candidates: string[], map: GlobMap): Decision {
  for (const [pattern, decision] of Object.entries(map)) {
    if (candidates.some((c) => _globMatch(c, pattern))) {
      return decision;
    }
  }
  return "allow";
}

function _resolveBashDecision(
  input: Record<string, unknown>,
  bashPolicy: GlobMap
): Decision {
  const command = typeof input.command === "string" ? input.command.trim() : "";
  const commandWord = command.split(/\s+/)[0] ?? "";
  // Match either the bare command word (e.g. "git") or the full command line
  // (so patterns like "git *" work) — first match in policy order wins.
  return _matchGlobMap([commandWord, command], bashPolicy);
}

/** True when `target` resolves outside `repoRoot`. */
function _isExternalPath(target: string, repoRoot: string): boolean {
  const resolved = path.resolve(repoRoot, target);
  const rel = path.relative(repoRoot, resolved);
  return rel === ".." || rel.startsWith(`..${path.sep}`) || path.isAbsolute(rel);
}

function _resolveFileDecision(
  input: Record<string, unknown>,
  repoRoot: string,
  dirPolicy: GlobMap | undefined
): Decision {
  // Only file accesses that escape the repo root are subject to the
  // external_directory policy; in-repo access is always allowed.
  const target = typeof input.path === "string" ? input.path : "";
  if (!target || !_isExternalPath(target, repoRoot)) {
    return "allow";
  }
  if (!dirPolicy) {
    return "allow";
  }
  const resolved = path.resolve(repoRoot, target);
  return _matchGlobMap([resolved, target], dirPolicy);
}

// ---------------------------------------------------------------------------
// Extension entry point — default-exported factory (Pi contract).
// ---------------------------------------------------------------------------

let _sessionPolicy: Permission | null = null;

export default function iwChatApprovals(api: ExtensionAPI): void {
  api.on("session_start", (_event: unknown, ctx: ExtensionContext) => {
    const repoRoot = ctx.cwd;
    // Invalidate any cached policy so each new session re-reads from disk
    // (picks up edits to .opencode/opencode.json made since last session).
    _policyCache.delete(repoRoot);
    _sessionPolicy = _loadPolicy(repoRoot);
  });

  api.on(
    "tool_call",
    async (
      event: unknown,
      ctx: ExtensionContext
    ): Promise<ToolCallEventResult | void> => {
      const ev = event as ToolCallEvent;
      const policy = _sessionPolicy ?? _loadPolicy(ctx.cwd);

      let decision: Decision = "allow";
      if (ev.toolName === "bash") {
        decision = _resolveBashDecision(ev.input, policy.bash ?? {});
      } else if (_FILE_TOOLS.has(ev.toolName)) {
        decision = _resolveFileDecision(ev.input, ctx.cwd, policy.external_directory);
      }
      // All other tools: default "allow".

      if (decision === "allow") {
        return;
      }

      if (decision === "deny") {
        return {
          block: true,
          reason: `[iw-chat-approvals] Tool call denied by policy: ${ev.toolName}`,
        };
      }

      // decision === "ask" — surface to user via Pi confirm UI. When no UI is
      // available (non-interactive contexts), fail safe by blocking.
      if (!ctx.hasUI) {
        return {
          block: true,
          reason: `[iw-chat-approvals] Approval required for ${ev.toolName} but no UI is available`,
        };
      }

      const question = `Allow tool "${ev.toolName}" with the shown input?`;
      // JSON envelope: the dashboard normalizer parses it to populate the
      // approval modal; in the TUI the raw message is shown to the user.
      const message = JSON.stringify({ tool: ev.toolName, args: ev.input, question });
      const approved = await ctx.ui.confirm(_CONFIRM_TITLE, message);
      if (!approved) {
        return {
          block: true,
          reason: `[iw-chat-approvals] Tool call denied by user: ${ev.toolName}`,
        };
      }
      // Approved — allow execution.
    }
  );
}
