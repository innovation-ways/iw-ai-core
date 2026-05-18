# CR-00057 — S05 Template Report

## What was done

Completed documentation/config seeding scope for AI Assistant model allowlist:

1. Seeded `projects.toml` with `[projects.iw-ai-core.ai_assistant]` including the 5-model allowlist and `default_model`.
2. Added new operator-facing documentation page at `docs/IW_AI_Core_AI_Assistant_Models.md` covering:
   - allowlist contract (`models`, `default_model`, regex and fail-open semantics)
   - dashboard intersection behavior and 30s project cache
   - provider setup for Anthropic, OpenAI, MiniMax, and Ollama
   - verified Ollama provider JSON shape (`provider.ollama` with `npm`, `name`, `options.baseURL`, `models`) with localhost and `http://iw-dev-01:11434/v1` examples
   - label-honesty note (`anthropic/*` != `claude-code` subscription runtime)
   - operational refresh/debug notes
   - out-of-scope bullets
3. Added Quick Navigation row in `CLAUDE.md` for the new AI Assistant allowlist documentation.

## Files changed

- `projects.toml`
- `docs/IW_AI_Core_AI_Assistant_Models.md` (new)
- `CLAUDE.md`

## Test / quality results

- `make format` ✅
- `make typecheck` ✅
- `make lint` ✅

No code-path tests were added in this step (docs + config seed scope only).

## Issues / observations

- Prompt requested Context7 verification. Context7 MCP was not available in this execution environment, so provider shape was verified against current OpenCode docs (`/docs/providers` and `/docs/config`) and pinned local OpenCode plugin dependency metadata (`.opencode/package.json` showing `@opencode-ai/plugin` `1.15.0`).
