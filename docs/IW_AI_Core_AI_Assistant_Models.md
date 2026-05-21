# IW AI Core — AI Assistant Model Allowlist

This page defines how IW AI Core limits the dashboard AI Assistant model dropdown per project, and how to configure OpenCode providers so allowlisted models are actually reachable. It is operator-facing guidance for `projects.toml` and `~/.config/opencode/opencode.json` setup.

## The allowlist contract

Each project may define an optional model allowlist block in `projects.toml`:

```toml
[projects.<project_id>.ai_assistant]
models = [
  "provider/model",
]
default_model = "provider/model"
default_runtime = "pi"
```

| Field | Type | Required | Rules |
|---|---|---|---|
| `models` | array of strings | yes (if block exists) | Each entry must match `^[a-z0-9._-]+/[A-Za-z0-9._:/-]+$` (for example `anthropic/claude-opus-4-7`, `ollama/gemma4:26b`). |
| `default_model` | string | no | If present, it must also be present in `models`. |
| `default_runtime` | string | no | One of `opencode` \| `pi`. Runtime a new chat tab uses when there is no active tab to inherit from. Absent or invalid → `opencode`. Each runtime resolves its own default model — the Pi runtime's default comes from `agent_runtime_options`, not `default_model`. |

Fail-open behavior is intentional: if a project has no `[projects.<project_id>.ai_assistant]` block (or no `project_id` is supplied), chat config falls back to the full OpenCode provider/model list.

## How the dashboard uses it

For each request, the dashboard intersects the project's allowlist with OpenCode `/config/providers`, and caches the result by `project_id` for 30 seconds.

## Configuring OpenCode providers

OpenCode config lives at `~/.config/opencode/opencode.json` (or `.jsonc`). Configure provider credentials via `/connect`, then optionally pin provider options and model aliases in config.

### 1) Anthropic

1. Run `opencode`.
2. Run `/connect` and select **Anthropic**.
3. Confirm models with `opencode models`.

Optional provider block:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "anthropic": {
      "options": {
        "baseURL": "https://api.anthropic.com/v1"
      }
    }
  }
}
```

### 2) OpenAI

1. Run `/connect` and select **OpenAI**.
2. Authenticate or provide API key.
3. Confirm models with `opencode models`.

### 3) MiniMax

1. Run `/connect` and select **MiniMax**.
2. Provide API key.
3. Confirm models with `opencode models`.

### 4) Ollama

Verified OpenCode provider shape (docs for current OpenCode schema in use; local plugin dependency is `@opencode-ai/plugin` `1.15.0`):

```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "ollama": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "Ollama (local)",
      "options": {
        "baseURL": "http://localhost:11434/v1"
      },
      "models": {
        "gemma4:26b": {
          "name": "Gemma4 26B"
        }
      }
    }
  }
}
```

#### Example A — laptop localhost Ollama

```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "ollama": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "Ollama (local)",
      "options": {
        "baseURL": "http://localhost:11434/v1"
      },
      "models": {
        "gemma4:26b": {
          "name": "Gemma4 26B"
        }
      }
    }
  }
}
```

#### Example B — IW AI Core production Ollama endpoint

```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "ollama": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "Ollama (iw-dev-01)",
      "options": {
        "baseURL": "http://iw-dev-01:11434/v1"
      },
      "models": {
        "gemma4:26b": {
          "name": "Gemma4 26B"
        }
      }
    }
  }
}
```

## Label honesty

`anthropic/*` allowlist entries route through OpenCode's Anthropic provider credentials (API-key-based provider integration). They do **not** route through the standalone `claude-code` CLI subscription. If the dropdown shows a Claude model label, treat it as an OpenCode provider/model route, not as "Claude Code" runtime routing.

## Operational notes

- **Refresh sequence after edits**:
  1. Update `projects.toml` and save.
  2. Reload daemon project registry (SIGHUP; example: `./ai-core.sh daemon reload`).
  3. Wait up to 30 seconds for chat-config cache expiry.
- **Remove a model**: delete it from `models` in `projects.toml`, reload daemon, wait for cache expiry.
- **Debug: model missing from dropdown**:
  1. Check dashboard logs for the warning about dropped allowlist entries.
  2. Run `opencode models` on the same machine and verify provider/model exists.
  3. Verify `~/.config/opencode/opencode.json` provider config (`baseURL`, model ID spelling, credentials).

## Out of scope

- No schema migration or new table — allowlist is in existing `Project.config` JSONB data.
- No automatic host-level OpenCode config mutation — operators edit `~/.config/opencode/opencode.json` manually.
- No cross-project forced rollout — projects without `[projects.<project_id>.ai_assistant]` continue using fail-open behavior.
