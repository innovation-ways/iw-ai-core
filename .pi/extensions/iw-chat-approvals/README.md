# iw-chat-approvals Pi Extension

Bridges the IW AI Core chat approval policy to Pi's `tool_call` hook, giving the dashboard operator the same permission controls for Pi-backed chat tabs as for OpenCode tabs.

## What it does

On each Pi session start the extension reads `.opencode/opencode.json` from the repo root and caches the `permission` section. On every `tool_call` event it matches the tool and its arguments against the cached policy:

| Policy value | Behaviour |
|---|---|
| `"allow"` | Tool call proceeds immediately (no user interaction). |
| `"deny"` | Tool call is rejected with an error (never reaches the subprocess). |
| `"ask"` | A confirm prompt is raised via `ctx.ui.confirm`. Approval lets the call proceed; denial blocks it (returns `{ block: true, reason }`). When no UI is available the call is blocked (fail-safe). |

### `bash` tool matching

The policy key `permission.bash` is a pattern → decision map. Patterns are simple globs (`*` and `?` as wildcards). The first matching pattern wins; if no pattern matches, `"allow"` is used as the default.

Example policy in `.opencode/opencode.json`:

```json
{
  "permission": {
    "bash": {
      "rm": "deny",
      "git push*": "ask",
      "*": "allow"
    },
    "external_directory": { "*": "ask" }
  }
}
```

### `external_directory` policy

The `permission.external_directory` key is a pattern → decision map (same glob
semantics as `bash`), matched against the resolved file path. It applies to the
`read`, `write`, `edit`, `ls`, `find`, and `grep` tools, but **only** when the
target path resolves outside the repo root — in-repo file access is always
allowed. A missing key defaults to `"allow"`.

## Approval routing contract

Pi (>=0.79) does **not** namespace `extension_ui_request` ids by extension — the
id is a random UUID. Routing therefore keys on the confirm **title**: this
extension raises `ctx.ui.confirm("iw-chat-approvals", <message>)`, and the tool
name + arguments are packed into the confirm `message` as a JSON envelope
(`{ tool, args, question }`).

The Python event normalizer (`orch/chat/pi/event_normalizer.py`) routes
`extension_ui_request` events with `method == "confirm"` and a title starting
with `iw-chat-approvals` to the `permission.asked` envelope, unpacking the JSON
message to populate the dashboard's approval UI panel. The user's decision is
sent back as an `extension_ui_response` carrying `confirmed: <bool>` (confirm
dialogs read `confirmed`, not `value`).

**Do not change the confirm title without updating the normalizer's
`_IW_APPROVALS_TITLE` constant in lockstep.**

## Shared policy source of truth

Both the OpenCode runtime and Pi read the same `.opencode/opencode.json` file. This means a single configuration edit propagates to both runtimes — no duplication required.

## How to disable

Remove (or rename) the extension directory from `.pi/extensions/`:

```bash
rm -rf .pi/extensions/iw-chat-approvals
```

Pi will load only extensions present under `.pi/extensions/` at session start.

To disable for a specific project only, remove the directory from that project's repo. The master copy lives in the iw-ai-core platform under `agents/pi/extensions/iw-chat-approvals/` and is re-synced on each `iw sync-agents` run — so only remove it after sync, or add `.pi/extensions/iw-chat-approvals/` to that project's `.gitignore`.

## Extension contract

Verified against `@earendil-works/pi-coding-agent` **0.79.0**:

- The module **default-exports a factory** `(api) => void`. The loader rejects a
  module whose default export is not a function with *"Extension does not export
  a valid factory function"*.
- Handlers are registered via `api.on(event, (event, ctx) => …)`. This extension
  listens on `session_start` and `tool_call`.
- A `tool_call` handler vetoes a call by **returning** `{ block: true, reason }`
  (it does not throw). `tool_call` events expose `event.toolName` and
  `event.input`; built-in tool names are `bash`, `read`, `write`, `edit`,
  `grep`, `find`, `ls`.
- User prompts use `ctx.ui.confirm(title, message)`.

If the Pi SDK contract changes, this file, the extension, and the Python event
normalizer must be updated in lockstep.

Tracking: F-00087 S01; contract realignment to Pi 0.79.
