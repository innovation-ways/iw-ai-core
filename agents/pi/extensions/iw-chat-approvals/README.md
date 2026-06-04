# iw-chat-approvals Pi Extension

Bridges the IW AI Core chat approval policy to Pi's `tool_call` hook, giving the dashboard operator the same permission controls for Pi-backed chat tabs as for OpenCode tabs.

## What it does

On each Pi session start the extension reads `.opencode/opencode.json` from the repo root and caches the `permission` section. On every `tool_call` event it matches the tool and its arguments against the cached policy:

| Policy value | Behaviour |
|---|---|
| `"allow"` | Tool call proceeds immediately (no user interaction). |
| `"deny"` | Tool call is rejected with an error (never reaches the subprocess). |
| `"ask"` | A confirm prompt is sent to the dashboard user via `ctx.ui.confirm`. Approval lets the call proceed; denial rejects it with an error. |

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
    "external_directory": "ask"
  }
}
```

### `external_directory` policy

The `permission.external_directory` key applies to `read_file`, `write_file`, and `list_directory` calls. Missing key defaults to `"allow"`.

## Request id namespace contract

Pi auto-prefixes every `ctx.ui.confirm` request id with the extension name, producing ids of the form:

```
iw-chat-approvals.<rid>
```

The Python event normalizer (`orch/chat/pi/event_normalizer.py`) routes events whose id starts with `iw-chat-approvals.` to the `permission.asked` envelope, making them visible in the dashboard's approval UI panel.

**Any confirm issued by this extension MUST have its id prefixed with `iw-chat-approvals.`**. Pi handles this automatically as long as the extension is loaded under the name `iw-chat-approvals` (the `name` field in `package.json`). Do not rename the extension without updating the Python normalizer.

## Shared policy source of truth

Both the OpenCode runtime and Pi read the same `.opencode/opencode.json` file. This means a single configuration edit propagates to both runtimes — no duplication required.

## How to disable

Remove (or rename) the extension directory from `.pi/extensions/`:

```bash
rm -rf .pi/extensions/iw-chat-approvals
```

Pi will load only extensions present under `.pi/extensions/` at session start.

To disable for a specific project only, remove the directory from that project's repo. The master copy lives in the iw-ai-core platform under `agents/pi/extensions/iw-chat-approvals/` and is re-synced on each `iw sync-agents` run — so only remove it after sync, or add `.pi/extensions/iw-chat-approvals/` to that project's `.gitignore`.

## Best-effort notice

The Pi extension manifest shape (the `subscribe()` API, `hooks.on()` event names, `ctx.ui.confirm` signature) is inferred from CR-00062 design references and `agents/pi/*.md` documentation. It has not been verified against a running Pi binary at the time of authoring. If the Pi SDK contract changes, this file and the Python event normalizer must be updated in lockstep.

Tracking: F-00087 S01.
