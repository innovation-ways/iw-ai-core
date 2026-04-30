# R-00066 — Integrating Claude Code / OpenCode into a Web Dashboard

**ID**: R-00066
**Date**: 2026-04-30
**Mode**: tech
**Depth**: standard
**Primary Question**: Is it feasible to replace terminal-based Claude Code / OpenCode interactions with a browser-based chat UI inside an existing FastAPI+htmx dashboard?

---

## Executive Summary

The integration is fully feasible and several community projects have already shipped it. The most direct path for this codebase is the **Claude Agent SDK** (`claude-agent-sdk`, Python, released 2026-04-29), which provides an async generator API that maps naturally onto the existing `StreamingResponse` + `text/event-stream` pattern already used in `dashboard/routers/sse.py` and `dashboard/routers/code_qa.py`. The critical policy constraint is that OAuth-backed subscriptions (Claude Pro/Max) cannot be used in third-party tools; only `ANTHROPIC_API_KEY`-based authentication is permitted for custom integrations — which is exactly how this project already operates. OpenCode offers a parallel path via `opencode serve`, which exposes an HTTP/SSE API that a Python client can consume as a proxy. The xterm.js + PTY approach is a viable fallback but adds significant complexity for a project whose patterns already favor SSE streaming over WebSockets.

---

## Finding 1: Claude Code CLI Integration Surface [HIGH]

### Headless / Non-Interactive Mode

Claude Code supports non-interactive execution via the `-p` / `--print` flag, officially named "headless mode" in the docs. Any `claude` invocation can be made non-interactive by adding `-p`:

```bash
claude -p "Find and fix the bug in auth.py" \
  --allowedTools "Read,Edit,Bash" \
  --output-format stream-json \
  --verbose \
  --include-partial-messages
```

Adding `--bare` skips CLAUDE.md auto-discovery, keychain reads, and MCP server loading — ideal for server-side automation where a consistent environment is needed. Bare mode requires `ANTHROPIC_API_KEY` and ignores `CLAUDE_CODE_OAUTH_TOKEN`.

### Output Formats

The `--output-format` flag has three modes:

- `text` — plain text, default, for humans
- `json` — final JSON blob with `result`, `session_id`, and usage metadata; supports `--json-schema` for schema-validated structured output
- `stream-json` — newline-delimited JSON events emitted in real time; combined with `--include-partial-messages`, emits `content_block_delta` / `text_delta` events matching the raw Anthropic streaming API format

Session continuity is managed via `--resume <session_id>`, obtained from the `session_id` field in the init or result JSON. Multi-turn conversations can be orchestrated by capturing and replaying session IDs. ([Claude Code Headless Mode docs](https://code.claude.com/docs/en/headless))

### Agent SDK (Python)

The **Claude Agent SDK** (`pip install claude-agent-sdk`, v0.1.71, released 2026-04-29, Python ≥3.10) is Anthropic's official programmatic interface — the renamed successor to the deprecated `claude-code-sdk`. ([claude-agent-sdk on PyPI](https://pypi.org/project/claude-agent-sdk/))

```python
from claude_agent_sdk import query, ClaudeAgentOptions
from claude_agent_sdk.types import StreamEvent

async for message in query(
    prompt="Explain auth.py",
    options=ClaudeAgentOptions(
        cwd="/path/to/project",       # sets working directory
        allowed_tools=["Read", "Bash"],
        include_partial_messages=True, # enables streaming deltas
        permission_mode="acceptEdits",
    ),
):
    if isinstance(message, StreamEvent):
        event = message.event
        if event.get("type") == "content_block_delta":
            delta = event.get("delta", {})
            if delta.get("type") == "text_delta":
                yield delta["text"]   # stream to SSE
```

The SDK bundles the Claude Code CLI binary — no separate `npm install -g @anthropic-ai/claude-code` is required. It exposes `ClaudeSDKClient` for stateful multi-turn sessions, and `list_sessions()` / `get_session_messages()` / `rename_session()` for session management. ([Agent SDK Python Reference](https://code.claude.com/docs/en/agent-sdk/python)) The `cwd` parameter directs the agent's filesystem operations to any project directory.

For subagent orchestration, tool hooks (`PreToolUse`, `PostToolUse`), MCP server injection, and custom permission callbacks are all available via `ClaudeAgentOptions`. ([Agent SDK Overview](https://code.claude.com/docs/en/agent-sdk/overview))

---

## Finding 2: Anthropic Third-Party Policy [HIGH]

### What the Shutdown Restricted

In April 2026, Anthropic enforced a policy that OAuth tokens from Claude Pro, Max, and Team subscriptions can only be used in two official products: Claude Code and Claude.ai. Any third-party tool routing requests through subscription OAuth — OpenClaw, NanoClaw, and similar harnesses — had access cut off on April 4, 2026. The rationale was preventing "token arbitrage": a Claude Max subscriber ($200/month) could run workloads worth thousands of dollars at API pay-per-token rates through a third-party harness with flat-rate subscription pricing. ([The Register](https://www.theregister.com/2026/02/20/anthropic_clarifies_ban_third_party_claude_access/))

### What is NOT Restricted

**API key usage is explicitly permitted** for any tool, including internal tools. The Anthropic Agent SDK documentation states:

> "Unless previously approved, Anthropic does not allow third party developers to offer claude.ai login or rate limits for their products, including agents built on the Claude Agent SDK. Please use the API key authentication methods described in this document instead."

The MindStudio analysis confirms: "developers can still build on Claude through the official Anthropic API — they just need to pay API costs directly, using API keys, not subscriber credentials" and "tools that use the official Anthropic API with their own API keys are unaffected." ([MindStudio: What Is the OpenClaw Ban?](https://www.mindstudio.ai/blog/anthropic-openclaw-ban-oauth-authentication))

### Application to This Project

An internal dashboard that connects via `ANTHROPIC_API_KEY` (direct API billing) is **fully permitted**. This project's use case — a personal/team internal tool driven by an API key — falls squarely in the permitted category. Authentication precedence in the Claude Code CLI prioritizes `ANTHROPIC_API_KEY` over OAuth credentials when both are present. In `--bare` mode, OAuth is never used; only `ANTHROPIC_API_KEY` applies — which is the correct behavior for a server process. ([Claude Code Authentication docs](https://code.claude.com/docs/en/authentication))

---

## Finding 3: OpenCode Integration Surface [HIGH]

### Server Mode

OpenCode ships a first-class headless HTTP server:

```bash
opencode serve [--port 4096] [--hostname 127.0.0.1] [--cors <origin>]
```

The server exposes an **OpenAPI 3.1** specification at `http://localhost:4096/doc`. ([OpenCode Server docs](https://opencode.ai/docs/server/)) Key API surface:

- **SSE event stream**: `event.subscribe()` — global server-sent events for all session activity
- **Sessions**: create, fork, delete, send prompts (`session.prompt()`), run commands
- **Files**: search, read, directory listings
- **Config**: retrieve/update, manage provider auth

Authentication: set `OPENCODE_SERVER_PASSWORD` and optionally `OPENCODE_SERVER_USERNAME`.

### Non-Interactive CLI Run Mode

```bash
opencode run --format json "Explain this codebase"
opencode run --format json --attach http://localhost:4096 "continue previous"
```

The `--format json` flag emits raw JSON events. `--attach` connects a run command to an already-running `opencode serve` instance. ([OpenCode CLI docs](https://opencode.ai/docs/cli/))

### Python Client Options

The official OpenCode SDK is TypeScript-only. A community Python SDK exists (`opencode-sdk-python` by `anomalyco`, auto-generated via Stainless, MIT licensed) that wraps the REST API. ([opencode-sdk-python](https://github.com/anomalyco/opencode-sdk-python)) For a Python-native dashboard, OpenCode would require either: (a) running as a sidecar process and proxying its SSE API via `httpx.AsyncClient`, or (b) using the community Python SDK. Neither is as clean as the official Claude Agent SDK path.

---

## Finding 4: Terminal Emulator vs Chat-Style Streaming [HIGH]

### Terminal Emulator Approach (xterm.js + WebSocket + PTY)

**How it works**: The server spawns a PTY (pseudo-terminal), executes `claude` or `opencode` interactively inside it, and relays raw terminal bytes over a WebSocket to an [xterm.js](https://github.com/xtermjs/xterm.js) instance in the browser.

**Pros**:
- Handles all interactive prompts natively (tool approval dialogs, TUI redraws)
- Works with any CLI unmodified
- Full terminal fidelity

**Cons**:
- Significant frontend weight (~200KB bundle before addons)
- Requires WebSocket — htmx's SSE extension is better supported than WebSocket in htmx
- Raw PTY bytes include ANSI escape codes — not clean for a styled chat UI
- Does not fit the existing htmx + SSE pattern
- Python PTY libraries (`ptyprocess`, `pexpect`) require threading bridges with asyncio

### Chat-Style Streaming (SSE + subprocess stdout or Agent SDK)

**How it works**: The backend calls `claude -p --output-format stream-json --include-partial-messages` or uses the Agent SDK's `async for message in query(...)` loop, and pipes parsed JSON deltas into a FastAPI `StreamingResponse`. ([FastAPI SSE tutorial](https://fastapi.tiangolo.com/tutorial/server-sent-events/))

**Pros**:
- Direct architectural match with the existing dashboard: `code_qa.py` and `sse.py` already use this exact pattern
- No additional frontend JS framework — htmx SSE extension or `EventSource` handles it ([htmx SSE extension](https://four.htmx.org/docs/extensions/sse))
- Tool call events can be formatted as styled UI elements ("Using Bash..." indicators) instead of raw escape codes
- Session IDs exposed as structured JSON fields — clean multi-turn management
- Agent SDK is a native asyncio async generator — consumed directly in a FastAPI async route without threading

**Cons**:
- Interactive approval dialogs require explicit configuration (`permission_mode="acceptEdits"` or `"dontAsk"`)
- Does not replicate the full TUI experience (session browsing, slash-command menus)

### Fit Assessment

The chat-style streaming approach is the right choice for this project. The codebase already has two working examples of the exact pattern. The Agent SDK's async generator maps directly onto the existing `StreamingResponse` pattern. xterm.js + PTY is appropriate only if the goal is to replicate the exact interactive terminal, including TUI panels and slash-command menus.

---

## Finding 5: Prior Art [HIGH]

Multiple community projects have shipped exactly this integration:

### 1. claude-code-webui (`sugyan/claude-code-webui`)
**Stack**: TypeScript backend + React/Vite frontend
**Integration**: Spawns `claude` subprocess with `--output-format stream-json --verbose --include-partial-messages`. Raw JSON streaming passed directly to the frontend. Session IDs extracted and passed as `resume` options on subsequent turns. Project directory is a UI-selectable parameter. ([GitHub](https://github.com/sugyan/claude-code-webui)) **This is the closest analog to what this project needs.**

### 2. CloudCLI — claudecodeui (`siteboon/claudecodeui`)
**Stack**: React/Vite + Node.js backend
**Integration**: Reads `~/.claude/` to discover existing sessions. Session browser and environment manager, not a new-session launcher. ([GitHub](https://github.com/siteboon/claudecodeui))

### 3. Agentrove (`Mng-dev-ai/claudex`)
**Stack**: React/Vite + **FastAPI backend** + SQLAlchemy + PostgreSQL/Redis
**Integration**: Launches agents through ACP adapter subprocess wrappers. Per-workspace Docker isolation. Supports Claude Code, OpenCode, Codex via the same interface. The **FastAPI + PostgreSQL + per-project workspace isolation** architecture is directly analogous to IW AI Core. ([GitHub](https://github.com/Mng-dev-ai/claudex))

### 4. opcode (`winfunc/opcode`)
**Stack**: Desktop GUI (Electron-style)
**Integration**: Interactive Claude Code session management with custom agent support. ([GitHub](https://github.com/winfunc/opcode))

### Key Insight from Prior Art

All projects that implement actual chat (not just monitoring) use either subprocess with `--output-format stream-json` or Agent SDK wrapping. None of the reviewed projects use xterm.js + PTY for the chat interface. The PTY approach is used only by projects that need a general-purpose terminal.

---

## Recommendations

### 1. Primary: Implement using the Claude Agent SDK with SSE streaming

Install `claude-agent-sdk` (Python ≥3.10, v0.1.71) and create a new FastAPI router (`dashboard/routers/agent_chat.py`) following the exact pattern of `code_qa.py`. The `query()` async generator maps directly to a `StreamingResponse` with `media_type="text/event-stream"`. Use `ClaudeAgentOptions(cwd=project.repo_path, permission_mode="acceptEdits", include_partial_messages=True)` to direct the agent at a project directory without interactive permission prompts. Expose `session_id` from the `SystemMessage(subtype="init")` event as an SSE event, store it in the browser, and pass it back as a `resume` parameter for multi-turn conversations. The frontend needs only the htmx SSE extension plus minimal vanilla JS for accumulating streaming tokens — no new framework required.

### 2. Secondary: Add OpenCode via `opencode serve` sidecar

For workloads where OpenCode is preferred, run `opencode serve --port 4096` as a sidecar managed by the daemon. The FastAPI router proxies SSE events from `http://localhost:4096/events` to the browser using `httpx.AsyncClient` inside a `StreamingResponse`. The OpenCode HTTP API is stable and documented via OpenAPI 3.1.

### 3. Risk: Tool approval dialogs require explicit permission configuration

By default, Claude Code running non-interactively will pause for approval on certain tool uses. Use `permission_mode="acceptEdits"` + a curated `allowed_tools` list as the baseline. Implementing the `AskUserQuestion` callback to forward approval prompts to the browser is possible with the SDK but significantly more complex — treat it as a future enhancement, not a baseline requirement.

---

## Limitations

- **`claude-agent-sdk` alpha status**: Released April 29, 2026 (one day before this research). Classified as "3 - Alpha" on PyPI. Its API surface may change in v0.2+; the deprecated `claude-code-sdk` migration path is documented but new SDK production stability in async web server contexts is not yet established by the community.

- **Session persistence model**: The Agent SDK stores session JSONL files under `~/.claude/`. Implications for multi-user access or concurrent sessions from the same dashboard instance were not tested. The `session_store` option (external session backend) exists but documentation coverage is thin.

- **OpenCode Python client maturity**: The `opencode-ai` PyPI package and `anomalyco/opencode-sdk-python` are both community-maintained. Their update cadence relative to the OpenCode server was not verified. An `httpx` proxy against the OpenAPI spec avoids this dependency.

- **Concurrent session isolation under load**: Running multiple agent sessions (one per project, potentially concurrent) from the same FastAPI process means multiple asyncio tasks each driving a subprocess. Interaction between multiple `query()` calls under load was not benchmarked.

- **Authentication for the dashboard server context**: `ANTHROPIC_API_KEY` must be available as an environment variable to the uvicorn process. The `--bare` flag on subprocess invocations prevents keychain access, ensuring only the env-var API key is used — correct behavior for a server, but requires explicit configuration.

---

## Sources

| # | Title | Credibility | URL |
|---|-------|-------------|-----|
| 1 | Claude Code Headless Mode / Programmatic Use | Official Anthropic docs | https://code.claude.com/docs/en/headless |
| 2 | Claude Agent SDK Overview | Official Anthropic docs | https://code.claude.com/docs/en/agent-sdk/overview |
| 3 | Agent SDK Python Reference | Official Anthropic docs | https://code.claude.com/docs/en/agent-sdk/python |
| 4 | Stream Responses in Real-Time (Agent SDK) | Official Anthropic docs | https://code.claude.com/docs/en/agent-sdk/streaming-output |
| 5 | Claude Code Authentication | Official Anthropic docs | https://code.claude.com/docs/en/authentication |
| 6 | claude-agent-sdk on PyPI | Package registry | https://pypi.org/project/claude-agent-sdk/ |
| 7 | OpenCode Server docs | Official OpenCode docs | https://opencode.ai/docs/server/ |
| 8 | OpenCode CLI docs | Official OpenCode docs | https://opencode.ai/docs/cli/ |
| 9 | OpenCode SDK docs | Official OpenCode docs | https://opencode.ai/docs/sdk/ |
| 10 | Anthropic clarifies ban on third-party tool access | The Register | https://www.theregister.com/2026/02/20/anthropic_clarifies_ban_third_party_claude_access/ |
| 11 | What Is the OpenClaw Ban? (OAuth vs API Key analysis) | MindStudio blog | https://www.mindstudio.ai/blog/anthropic-openclaw-ban-oauth-authentication |
| 12 | Anthropic blocks third-party Claude Code subscriptions | Hacker News | https://news.ycombinator.com/item?id=46549823 |
| 13 | VentureBeat: Anthropic cracks down on unauthorized Claude usage | VentureBeat | https://venturebeat.com/technology/anthropic-cracks-down-on-unauthorized-claude-usage-by-third-party-harnesses |
| 14 | claude-code-webui (sugyan) | GitHub community project | https://github.com/sugyan/claude-code-webui |
| 15 | claudecodeui / CloudCLI (siteboon) | GitHub community project | https://github.com/siteboon/claudecodeui |
| 16 | Agentrove / claudex (Mng-dev-ai) — FastAPI + agent integration | GitHub community project | https://github.com/Mng-dev-ai/claudex |
| 17 | xterm.js GitHub | Official xterm.js | https://github.com/xtermjs/xterm.js |
| 18 | FastAPI SSE tutorial | FastAPI official docs | https://fastapi.tiangolo.com/tutorial/server-sent-events/ |
| 19 | htmx SSE extension | htmx docs | https://four.htmx.org/docs/extensions/sse |
| 20 | opencode-sdk-python (community Python client) | GitHub | https://github.com/anomalyco/opencode-sdk-python |
| 21 | awesome-claude-code-toolkit | GitHub | https://github.com/rohitg00/awesome-claude-code-toolkit |
