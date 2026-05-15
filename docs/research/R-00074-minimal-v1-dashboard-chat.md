# R-00074 — Minimal v1 Dashboard Chat: OpenCode and Pi Reconsidered

| Field | Value |
|-------|-------|
| ID | R-00074 |
| Date | 2026-05-14 |
| Mode | tech |
| Editorial category | technical |
| Status | draft |

**Primary question** — For the corrected minimal v1 scope (FastAPI relay + chat panel + HTML rendering of the runtime's existing permission prompts + abort button — *no* new safeguard policy, *no* new state tables, *no* plan-only mode), what is the smallest honest integration with OpenCode, what is the smallest honest integration with Pi, and which is genuinely easier for *this* scope?

---

## Executive Summary

R-00073 §14 layered a `research_session_state` table, a named risk-policy with LOW/MED/HIGH classification, `Last-Event-ID`-replayed event-log persistence, an `idempotency_key` migration to `iw next-id`, and a `plan_only` mode on top of OpenCode's already-built-in permission system. **That was conservative engineering imported from multi-tenant SaaS incident reports** (notably [Replit / SaaStr July 2025](https://www.theregister.com/2025/07/21/replit_saastr_vibe_coding_incident/)) and **does not match this project's actual risk surface**: single user, single session, repo-bounded directory, local orch DB on 127.0.0.1:5433, and a skill (`/iw-research`) the user already runs from the CLI today with no safeguards beyond OpenCode's defaults.

Under the corrected scope, **minimal v1 is five components**, none of them safeguard additions:

1. **Subprocess manager** that spawns the chosen runtime once, on `127.0.0.1`, owned by the FastAPI dashboard.
2. **Backend↔runtime client** (httpx+httpx-sse for OpenCode, asyncio subprocess + LF-only JSONL reader for Pi).
3. **FastAPI relay** that holds the upstream connection and broadcasts events to browser SSE — so a tab refresh doesn't kill an in-flight `/iw-research` run.
4. **Chat panel template** (htmx + a small inline JS for an `EventSource`, matching the existing pattern in [`dashboard/routers/code_qa.py`](dashboard/routers/code_qa.py)).
5. **Approval modal** that renders the runtime's existing permission/approval event as HTML and POSTs the user's choice back.

No new DB tables. No new CLI flags. No risk-classification policy. No plan-only flag. Permissions are configured in `opencode.json` (or a Pi extension for the equivalent), exactly the way the CLI is configured today.

**For this scope, OpenCode is still the right v1 pick, but the margin over Pi is materially smaller than R-00072 §10 suggested.** The decisive remaining factor is **permission ergonomics**: OpenCode's permission system is config-only (`"permission": { "bash": "ask", "edit": "ask" }` in `opencode.json`), and approval events arrive on the SSE bus we already need to consume — zero extra code on our side. Pi has no built-in permission system; to get equivalent behavior we'd ship a ~30–50-line TypeScript extension under `.pi/extensions/` that intercepts `tool_call` and emits an `extension_ui_request: confirm` to the RPC stream. That's small but it's a second language and toolchain we currently don't need.

The other R-00072 §10 axes (sandbox defaults, ecosystem, MCP) **don't carry weight under the minimal scope** because we're not using them: no container, no MCP server registered, no third-party UI to crib from beyond the seven OpenCode web UIs surveyed in R-A. The remaining differentiator collapses to "config-only permissions vs a small extension" — a real but recoverable cost.

**Recommended v1 prototype**: ~400 lines of Python + minimal templates against `opencode serve`. The whole thing fits in five new files plus one new `opencode.json` permission block. The Pi alternative is roughly the same Python footprint plus the extension and the LF-only JSONL reader, and is a sensible post-v1 spike if we ever want to test Pi's smaller context-budget claim against our actual usage.

---

## Background

R-00071 (OpenCode) and R-00072 (Pi) evaluated runtime choices for a "full execution with safeguards" v1. R-00073 surveyed 10 systems and produced a §14 design that layered defense-in-depth safeguards on top of the runtime's existing capabilities. **The user correctly identified that those layered safeguards are not needed for a single-user dashboard wrapping a tool the user already runs from the CLI.** This research re-scopes the v1 to the minimum viable surface — the genuine plumbing required to move `/iw-research` from terminal to browser — and re-checks the OpenCode-vs-Pi comparison against that surface.

---

## Findings

### 1. Minimal v1 surface — five components, nothing more [HIGH]

The genuine functional delta between "use the CLI" and "use the dashboard chat" is:

| Component | Why it's needed | Equivalent in CLI |
|-----------|-----------------|-------------------|
| **Subprocess manager** | The dashboard owns the runtime's lifecycle | User runs `opencode` / `pi` |
| **Backend↔runtime client** | FastAPI talks to the runtime; the browser doesn't | Terminal talks directly |
| **FastAPI relay** | Tab refresh / Wi-Fi drop should not kill an in-flight run; relay holds the upstream connection | Terminal stays open |
| **Chat panel template** | UI for typing prompts and seeing streamed output | Terminal renders text |
| **Approval modal** | The runtime's `[y/n]?` prompt becomes an HTML modal | Terminal renders `[y/n]?` |

That's it. Everything else from R-00073 §14 — the policy table, event-log persistence, plan-only mode, idempotency_key on `iw next-id` — is **future growth**, not v1 requirement. The current `/iw-research` CLI usage works with no policy table or plan-only mode; the dashboard version doesn't need them either.

### 2. Minimal OpenCode integration [HIGH]

**Files** (target footprint: ~400 lines Python + ~150 lines templates):

```
orch/research_chat/
  __init__.py                # 5 lines
  opencode_runtime.py        # ~100 lines — Popen + health-poll + kill on shutdown
  opencode_client.py         # ~100 lines — httpx-sse aconnect_sse + REST helpers
  event_relay.py             # ~100 lines — broadcasts upstream SSE → N browser SSE
  filters.py                 # ~50 lines — what event types to forward to browser

dashboard/routers/
  research_chat.py           # ~100 lines — endpoints below

dashboard/templates/
  pages/research_chat.html   # ~100 lines — htmx + EventSource + approval modal
  fragments/research_message.html  # ~30 lines — htmx-replacable message card
  fragments/research_approval.html # ~30 lines — modal markup

.opencode/
  config.json (patch)        # +10 lines — permission block (see below)

.env                         # +2 vars: IW_CORE_OPENCODE_PORT, IW_CORE_OPENCODE_PASSWORD
```

**FastAPI routes** (anchored to the existing patterns in `dashboard/routers/sse.py` and `dashboard/routers/code_qa.py`):

```
GET   /project/{pid}/research-chat                 → page (chat panel)
POST  /api/research-chat                            → create OpenCode session, return sid
GET   /api/research-chat/{sid}/stream               → SSE relay to browser
POST  /api/research-chat/{sid}/prompt               → forwards to /session/<sid>/prompt_async
POST  /api/research-chat/{sid}/abort                → forwards to /session/<sid>/abort
POST  /api/research-chat/{sid}/permissions/{rid}    → forwards to /session/<sid>/permissions/<rid>
```

**Runtime spawn (`opencode_runtime.py`)**:

```python
import asyncio, os, secrets, signal
from pathlib import Path

class OpencodeRuntime:
    def __init__(self, repo_root: Path, port: int = 4096):
        self.repo_root = repo_root
        self.port = port
        self.password = secrets.token_urlsafe(32)
        self.proc: asyncio.subprocess.Process | None = None

    async def start(self) -> None:
        env = {**os.environ, "OPENCODE_SERVER_PASSWORD": self.password}
        self.proc = await asyncio.create_subprocess_exec(
            "opencode", "serve",
            "--hostname", "127.0.0.1",
            "--port", str(self.port),
            cwd=str(self.repo_root),
            env=env,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
            # Linux: die with parent (PR_SET_PDEATHSIG)
            preexec_fn=lambda: __import__("ctypes").CDLL("libc.so.6").prctl(1, signal.SIGTERM),
        )
        await self._wait_healthy()

    async def _wait_healthy(self, timeout: float = 10.0) -> None:
        # poll GET /global/health until 200 or timeout
        ...

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    async def stop(self) -> None:
        if self.proc and self.proc.returncode is None:
            self.proc.terminate()
            await self.proc.wait()
```

**Client (`opencode_client.py`)** — minimal surface, using [httpx-sse's `aconnect_sse` + `aiter_sse`](https://pypi.org/project/httpx-sse/):

```python
import httpx
from httpx_sse import aconnect_sse

class OpencodeClient:
    def __init__(self, base_url: str, password: str):
        auth = httpx.BasicAuth("opencode", password)
        self.client = httpx.AsyncClient(base_url=base_url, auth=auth, timeout=None)

    async def create_session(self) -> str:
        r = await self.client.post("/session", json={})
        r.raise_for_status()
        return r.json()["id"]

    async def prompt(self, sid: str, text: str, model: str | None = None) -> None:
        await self.client.post(
            f"/session/{sid}/prompt_async",
            json={"parts": [{"type": "text", "text": text}], "model": model},
        )

    async def abort(self, sid: str) -> None:
        await self.client.post(f"/session/{sid}/abort")

    async def reply_permission(self, sid: str, rid: str, response: str, remember: bool = False) -> None:
        await self.client.post(
            f"/session/{sid}/permissions/{rid}",
            json={"response": response, "remember": remember},
        )

    async def stream_events(self, last_event_id: str | None = None):
        headers = {}
        if last_event_id:
            headers["Last-Event-ID"] = last_event_id
        async with aconnect_sse(self.client, "GET", "/event", headers=headers) as es:
            async for sse in es.aiter_sse():
                yield sse  # has .event, .data, .id, .retry, .json()
```

**Relay (`event_relay.py`)** — single per-session relay that fans out to N browser SSE listeners; matches the existing `routers/sse.py` shape:

```python
import asyncio, json
from collections import deque

class SessionRelay:
    """One per OpenCode session. Holds upstream SSE; broadcasts to browser SSEs."""

    def __init__(self, client, sid: str, buffer_size: int = 256):
        self.client = client
        self.sid = sid
        self.subscribers: list[asyncio.Queue] = []
        self.buffer: deque = deque(maxlen=buffer_size)  # in-memory replay
        self._upstream_task: asyncio.Task | None = None

    async def start(self) -> None:
        self._upstream_task = asyncio.create_task(self._run_upstream())

    async def _run_upstream(self) -> None:
        async for sse in self.client.stream_events():
            payload = {"event": sse.event, "data": sse.data, "id": sse.id}
            self.buffer.append(payload)
            for q in list(self.subscribers):
                try:
                    q.put_nowait(payload)
                except asyncio.QueueFull:
                    pass

    async def subscribe(self, last_event_id: str | None = None):
        q: asyncio.Queue = asyncio.Queue(maxsize=1024)
        # replay buffered events newer than last_event_id
        for p in self.buffer:
            if last_event_id is None or p["id"] > last_event_id:
                q.put_nowait(p)
        self.subscribers.append(q)
        try:
            while True:
                yield await q.get()
        finally:
            self.subscribers.remove(q)
```

**FastAPI router (`dashboard/routers/research_chat.py`)** — mirrors the existing pattern in `code_qa.py`:

```python
@router.get("/api/research-chat/{sid}/stream")
async def stream(sid: str, request: Request):
    relay = _relay_for(sid)
    last_id = request.headers.get("Last-Event-ID")

    async def gen():
        async for payload in relay.subscribe(last_event_id=last_id):
            data = json.dumps(payload["data"]) if payload["data"] else ""
            yield f"event: {payload['event']}\ndata: {data}\nid: {payload['id']}\n\n"
            if await request.is_disconnected():
                return

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

**`opencode.json` permission block** — this is the entire safeguard model:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "permission": {
    "*": "ask",
    "read": "allow",
    "glob": "allow",
    "grep": "allow",
    "webfetch": "allow",
    "websearch": "allow",
    "external_directory": "deny"
  }
}
```

Three lines of meaningful policy: ask before anything write/edit/bash, allow reads + web research (the skill needs these), deny external directories. Everything else inherits OpenCode's defaults.

**Browser-side** (~150 lines of HTML/JS, htmx + plain `EventSource` per the dashboard's existing pattern documented in `dashboard/CLAUDE.md`):

```javascript
const es = new EventSource(`/api/research-chat/${sid}/stream`);
es.addEventListener("message.part.updated", (e) => { /* append to chat */ });
es.addEventListener("tool.execute.before", (e) => { /* render tool card */ });
es.addEventListener("tool.execute.after",  (e) => { /* complete tool card */ });
es.addEventListener("permission.asked",    (e) => { /* show approval modal */ });
es.addEventListener("session.idle",        (e) => { /* enable Send button */ });
es.onerror = (e) => { /* show "reconnecting…" pill; EventSource auto-retries */ };
```

**That's the entire v1.** No new DB tables. No new CLI flags. No policy. Browser tab refresh → `EventSource` reconnects → relay replays the buffered events from the in-memory `deque`. OpenCode crash → subprocess manager restarts → relay's upstream loop reconnects via `aconnect_sse` (which retries on `httpx.ReadError`).

### 3. Minimal Pi integration [HIGH]

**Files** (target footprint: ~350 lines Python + ~40 lines TypeScript + ~150 lines templates):

```
orch/research_chat/
  __init__.py                # 5 lines
  pi_runtime.py              # ~120 lines — asyncio subprocess + LF-only JSONL reader
  pi_client.py               # ~80 lines  — send commands, parse responses, route extension_ui_request
  event_relay.py             # ~100 lines — same shape as OpenCode's relay
  filters.py                 # ~50 lines

dashboard/routers/
  research_chat.py           # ~100 lines

dashboard/templates/         # same as OpenCode

.pi/extensions/iw-research-confirm/
  package.json               # ~10 lines
  index.ts                   # ~40 lines — tool_call → ctx.ui.confirm()

~/.pi/agent/settings.json    # +1 line: skills array includes ~/.claude/skills if desired
```

**Subprocess + LF-only JSONL reader (`pi_runtime.py`)**:

```python
import asyncio, json
from pathlib import Path

class PiRuntime:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.proc: asyncio.subprocess.Process | None = None

    async def start(self) -> None:
        self.proc = await asyncio.create_subprocess_exec(
            "pi", "--mode", "rpc",
            cwd=str(self.repo_root),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

    async def send(self, cmd: dict) -> None:
        line = (json.dumps(cmd) + "\n").encode("utf-8")
        self.proc.stdin.write(line)
        await self.proc.stdin.drain()

    async def events(self):
        """LF-only reader. Cannot use `async for line in proc.stdout`
        because asyncio's default StreamReader splits on \\n only,
        which is what we want — BUT we still strip trailing \\r."""
        reader = self.proc.stdout
        buf = bytearray()
        while True:
            chunk = await reader.read(65536)
            if not chunk:
                return
            buf.extend(chunk)
            while True:
                nl = buf.find(b"\n")
                if nl < 0:
                    break
                raw = bytes(buf[:nl])
                del buf[:nl + 1]
                if raw.endswith(b"\r"):
                    raw = raw[:-1]
                if not raw:
                    continue
                try:
                    yield json.loads(raw)
                except json.JSONDecodeError:
                    pass  # log and skip malformed line
```

**Client (`pi_client.py`)** — sends commands, routes `extension_ui_request` events to the dashboard's approval modal:

```python
import asyncio

class PiClient:
    def __init__(self, runtime: PiRuntime):
        self.runtime = runtime
        self.pending_ui: dict[str, asyncio.Future] = {}

    async def prompt(self, text: str) -> None:
        await self.runtime.send({"type": "prompt", "message": text})

    async def abort(self) -> None:
        await self.runtime.send({"type": "abort"})

    async def reply_ui(self, rid: str, value: dict) -> None:
        await self.runtime.send({"type": "extension_ui_response", "id": rid, **value})

    async def events(self):
        async for ev in self.runtime.events():
            yield ev
```

**Pi extension (`.pi/extensions/iw-research-confirm/index.ts`)** — the equivalent of OpenCode's permission config:

```typescript
import type { Plugin } from "@earendil-works/pi-coding-agent";

const NEEDS_CONFIRM = /^(iw\s+(register|doc-update)|edit|write|rm\b|git\s+(reset|push|commit))/;

export default (async (pi) => {
  return {
    "tool_call": async (input, output, ctx) => {
      const argline = JSON.stringify(input.args ?? {});
      if (input.tool === "bash" && NEEDS_CONFIRM.test(input.args?.command ?? "")) {
        const ok = await ctx.ui.confirm(
          `Allow: ${input.args.command}`,
          "This step has side effects.",
        );
        if (!ok) throw new Error("blocked by user");
      } else if (input.tool === "edit" || input.tool === "write") {
        const ok = await ctx.ui.confirm(
          `Allow ${input.tool} to ${input.args?.filePath ?? "<unknown>"}`,
          "This step has side effects.",
        );
        if (!ok) throw new Error("blocked by user");
      }
    },
  };
}) satisfies Plugin;
```

When this extension calls `ctx.ui.confirm(...)`, Pi emits an `extension_ui_request` event with `{ id, method: "confirm", title, message }` on stdout ([Pi RPC docs](https://github.com/badlogic/pi-mono/blob/main/packages/coding-agent/docs/rpc.md)). The Python client relays it to the browser as `event: permission.asked` (renaming for parity with OpenCode), the user clicks, the dashboard POSTs back to `/api/research-chat/<sid>/permissions/<rid>`, the client sends `{"type": "extension_ui_response", "id": rid, "confirmed": true|false}` on stdin, Pi resumes and the extension either continues or throws.

The browser-side code is **identical to the OpenCode variant** — same `EventSource`, same approval modal, same POST endpoint. The only difference is which Python module the FastAPI router talks to behind the scenes.

### 4. What from R-00073 §14 we *keep* vs *drop* under the minimal scope [HIGH]

| §14 item | v1? | Reasoning |
|----------|-----|-----------|
| FastAPI relay holding upstream connection | **KEEP** | Mandatory plumbing; tab refresh must not kill an in-flight run. |
| In-memory ring buffer (256 events) in the relay | **KEEP** | Tab refresh replay; small, no DB persistence. |
| Approval modal rendering for permission events | **KEEP** | This is *surfacing* OpenCode/Pi's existing safety, not adding new safety. |
| `research_event_log` DB table | **DROP** | Useful for cross-restart audit; not needed for v1. OpenCode persists session state on disk; that's our audit trail. |
| `research_session_state` DB table | **DROP** | Was for the homegrown checkpoint policy; we don't have a policy. |
| Risk-classification policy (`POLICY` table mapping bash patterns → low/medium/high) | **DROP** | OpenCode's `permission` block in `opencode.json` is the policy. Pi's extension is the policy. Both already exist at the right layer. |
| `WAITING_FOR_CONFIRMATION` agent state | **DROP** | Implicit in OpenCode's `permission.asked` event semantics. We're not adding our own. |
| `plan_only` session flag + dashboard toggle | **DROP** | Conservative anti-Replit-incident addition; not needed for a single-user repo-bounded skill. Defer to a v2 if scope grows. |
| `idempotency_key` migration to `iw next-id` | **DROP from this work** | Real latent issue but exists today in CLI usage; file as a separate small CR if/when it bites. |
| `Last-Event-ID` semantics (header + ring buffer replay) | **KEEP, simplified** | Browser `EventSource` sends `Last-Event-ID` automatically on reconnect; relay's in-memory deque is enough. No DB. |
| Heartbeat + watchdog | **KEEP** | OpenCode emits a 30 s heartbeat already; relay restarts upstream on `httpx.ReadError`. ~10 lines. |
| Per-step git snapshot rollback | **KEEP (via OpenCode default)** | We don't implement it; OpenCode does. |
| Sandbox container per session | **DROP** | Repo-bounded working directory + `external_directory: deny` is enough for v1. Document the upgrade path. |
| `Plan` / `Sources` / `Draft` dedicated panels | **NICE-TO-HAVE** | v1 can just render in the chat; panels are a UX polish, not a safeguard. |

**Net**: out of 14 §14 components, we keep 4 (relay, ring buffer, modal, heartbeat) and the runtime's own defaults handle the rest.

### 5. OpenCode default permission block — the whole safeguard layer [HIGH]

The complete v1 safety configuration for OpenCode lives in `.opencode/config.json`:

```json
{
  "permission": {
    "*": "ask",
    "read": "allow",
    "glob": "allow",
    "grep": "allow",
    "webfetch": "allow",
    "websearch": "allow",
    "external_directory": "deny"
  }
}
```

That's it. Six lines of policy. The behavior:

- `read`, `glob`, `grep`, `webfetch`, `websearch` execute silently — the skill needs them for research.
- `edit`, `write`, `bash`, `task` (any unlisted tool) fall through to `"*": "ask"` and emit `permission.asked` on the SSE bus.
- `external_directory: "deny"` blocks any tool from writing outside the session's `directory` (which we set to repo root on session create).

The user can later add `remember: true` patterns by clicking "always allow" in the dashboard's approval modal; OpenCode persists that to `.opencode/config.json`'s `permission` block automatically (a documented behavior).

### 6. Pi minimum config — extension carries the policy [HIGH]

Pi has no built-in `permission` block. The equivalent is the ~40-line extension shown in §3. The Pi extension:

- Reads exactly like our `opencode.json` policy block — same patterns, same allow/deny semantics, but expressed in TypeScript.
- Is auto-discovered from `.pi/extensions/iw-research-confirm/` at startup.
- Has the slight cost of introducing a TypeScript file (and `bun install` at Pi startup) to a Python-only repo. Manageable but real.

If we want approval prompts to be **off by default** (trust the agent fully), the Pi path becomes very slightly *smaller* than OpenCode: just don't ship the extension. For our use case we want at least `iw register` and `edit` to prompt, so the extension is required.

### 7. Reconnect under the minimal model — in-memory ring buffer is enough [HIGH]

For our scope (single user, single session), persisted event logs are over-engineering. The minimal sufficient behavior:

- **Relay holds the upstream connection** for as long as the OpenCode/Pi process is alive. This is what survives browser tab refresh.
- **In-memory `deque(maxlen=256)`** of the last 256 events per session in the relay. Browser reconnects → `EventSource` automatically sends `Last-Event-ID` header → relay replays only the events newer than that ID.
- **OpenCode's 30 s heartbeat + httpx-sse's `httpx.ReadError`** detection in the relay's upstream loop. On error, retry with backoff (300 ms → 3 s) up to a small budget; surface a "reconnecting…" pill in the chat panel.
- **No persistence to DB.** If the FastAPI dashboard process restarts, the in-memory buffer is gone — that's acceptable for v1. The user sees the chat panel reload and may need to ask the agent "what did you just do?" — OpenCode's `GET /session/<sid>/messages` is available if we want to render the full transcript on page-load (we should).

**When this isn't enough**: only if we want to expose a "what happened while I was offline overnight" audit view in the dashboard. That's a v2 feature, not a v1 blocker.

### 8. Re-scored head-to-head for the minimal scope [HIGH]

The R-00072 §10 matrix weighed factors that don't all carry weight under the minimal scope. Here is the re-scored version, axes ordered by what actually matters for v1:

| Axis | OpenCode | Pi | Winner for minimal v1 |
|------|----------|----|----------------------|
| **Permission prompts: setup cost** | 6 lines of `opencode.json` config | 40 lines of TypeScript extension + `bun install` at runtime startup | **OpenCode** — meaningful delta. |
| **Python-backend ergonomics** | httpx + httpx-sse, HTTP+SSE — debuggable with `curl`, OpenAPI spec at `/doc` | asyncio subprocess + LF-only JSONL reader (one careful function); no curl, no spec | **OpenCode** — debuggability matters. |
| **Lines of code (Python)** | ~400 LOC across 5 files | ~350 LOC across 5 files + extension | **Tied** — Pi marginally smaller, OpenCode marginally simpler per line. |
| **Languages we have to maintain** | Python | Python + TypeScript (the extension) | **OpenCode**. |
| **Runtime complexity to debug** | One subprocess + one HTTP port + one password env var | One subprocess + stdio | **Pi** — fewer moving parts. |
| **Resource footprint** | Bun + Hono server; ~50–100 MB RSS | Node + minimal harness; lower (per [author's claim](https://mariozechner.at/posts/2025-11-30-pi-coding-agent/)) | **Pi** — minor. |
| **Skill compatibility with existing `skills/iw-research/`** | Reads `.opencode/skills/` and `.claude/skills/` (we sync to both) | Reads `.pi/skills/`, `.agents/skills/`, configurable to read `~/.claude/skills/` | **Tied** — both work as-is. |
| **OpenCode-specific MCP support** | Yes (local + remote + OAuth) | No (rejected by author) | **Tied for v1** — we don't use MCP in v1. |
| **Ecosystem / reference embeddings** | 7+ web UIs (1 at 177★) + VS Code extension + Go SDK | 1 reference (21★, 7 commits) + Lit web components | **Tied for v1** — we don't crib from either; we're building exactly the small amount we need. |
| **Sandbox defaults** | None by default; permission system + repo-bounded `directory` + `external_directory: deny` | None by default; only the extension we ship | **Tied for v1** — we're not containerizing in v1. |
| **Version stability** | v1.14.x (one known SSE regression — version-pin) | v0.74; pre-1.0; very active dev | **OpenCode** — slightly more mature. |
| **Future swap cost** | Replace pi_runtime/pi_client with opencode equivalents | Same in reverse | **Tied** — swap is ~300 LOC either direction. |

**Net for minimal v1**: OpenCode wins on three axes that matter (permission setup, Python ergonomics, languages), ties on six, loses on two minor axes (resource footprint, fewer-moving-parts). The **decisive factor** is the permission-prompt setup cost: OpenCode's config-only approach is materially less code/toolchain than Pi's extension approach, *especially when our use case explicitly wants prompts for `iw register` / `edit`*.

If our use case were "no prompts, trust the agent fully," Pi would be the simpler pick. It isn't.

### 9. Skill-portability angle — runtime swap is genuinely cheap now [HIGH]

Because v1 doesn't add any state tables, policy code, or plan-only modes, the runtime-swap surface is the smallest it can be:

- `opencode_runtime.py` ↔ `pi_runtime.py` — different subprocess invocation, different stream protocol.
- `opencode_client.py` ↔ `pi_client.py` — different request shape, different event names.
- `event_relay.py` — **unchanged** (events are normalized to `{event, data, id}` triples before broadcast).
- `dashboard/routers/research_chat.py` — **unchanged** (talks to the relay, not the runtime).
- Templates — **unchanged**.
- `skills/iw-research/SKILL.md` — **unchanged**; both runtimes load it.
- Permission config — `opencode.json` ↔ `.pi/extensions/iw-research-confirm/`.

Swap cost: ~300 LOC of Python + a ~40-line TypeScript extension if moving from OpenCode to Pi, or removing the extension if moving the other way. ~1 day of work. **We are not locked in by picking OpenCode for v1.**

### 10. Recommended v1 prototype outline [HIGH]

The deliverable from this research is a concrete starting point for the next agent (design doc author / `frontend-impl` / `backend-impl`) to build against. Below is that outline.

**Stack**: OpenCode (per §8) via subprocess + httpx + httpx-sse + FastAPI's `StreamingResponse` + htmx + plain `EventSource`. The existing `dashboard/routers/sse.py` and `dashboard/routers/code_qa.py` are the canonical patterns to mirror.

**File tree (additions only)**:

```
orch/research_chat/
  __init__.py
  opencode_runtime.py
  opencode_client.py
  event_relay.py
  filters.py

dashboard/routers/research_chat.py
dashboard/templates/pages/research_chat.html
dashboard/templates/fragments/research_message.html
dashboard/templates/fragments/research_approval.html

.opencode/config.json          # patch: permission block
.env.example                   # +IW_CORE_OPENCODE_PORT=4096
```

**Configuration touch-points**:

- `orch/config.py` — add `opencode_port: int = 4096` to the config dataclass; read from env.
- `dashboard/app.py` — register the new router; in lifespan, call `OpencodeRuntime.start()` and `.stop()`.
- `.opencode/config.json` — add the permission block from §5.
- `Makefile` — no change; `make css` will pick up new Tailwind classes from new templates.

**Behavior contract**:

| User action | Backend | Browser |
|-------------|---------|---------|
| Opens `/project/<pid>/research-chat` | Lazy-creates an OpenCode session if none exists | Renders chat panel + sets up `EventSource` |
| Types prompt, clicks Send | `POST /api/research-chat/<sid>/prompt` → `client.prompt(sid, text)` | Optimistically shows user message |
| Agent streams response | Relay forwards `message.part.updated` events | `EventSource` listener appends token deltas to the active message card |
| Agent calls `iw next-id` | OpenCode runs it (low-risk, allowed via `permission` config) | `tool.execute.before/after` events render a "Tool: bash" card |
| Agent calls `iw register R-NNNNN ...` | OpenCode emits `permission.asked` with the bash command | Browser renders approval modal |
| User clicks Allow | `POST /api/research-chat/<sid>/permissions/<rid>` → `client.reply_permission(...)` | Modal closes; tool proceeds |
| Agent finishes | OpenCode emits `session.idle` | Send button re-enabled |
| User clicks Cancel mid-run | `POST /api/research-chat/<sid>/abort` | UI shows "cancelling…"; agent aborts |
| Browser tab refresh | Relay replays last 256 events via `Last-Event-ID` | Chat panel reconstructs from replay; no agent action lost |
| OpenCode crashes | `OpencodeRuntime` restarts; relay reconnects upstream | "Reconnecting…" pill; resumes |
| FastAPI process restart | Buffer lost; session still on disk in OpenCode | Page reload fetches messages via `GET /session/<sid>/messages` for context |

**Non-goals for v1**:
- DB-persisted event log (defer to v2 if audit needs grow)
- Plan-only mode toggle (defer to v2 if scope grows)
- Dedicated Plan/Sources/Draft panels (defer to v2 polish)
- Multi-session per user (single session, single user — current dashboard constraint)
- Container-per-session sandboxing (defer)
- `idempotency_key` migration to `iw next-id` (separate small CR if/when it bites)

**Estimated build time**: 1–2 days for a focused agent. The longest part is template work (chat panel + approval modal + htmx wiring). Backend pieces are mechanical — each module is a small, single-responsibility wrapper.

---

## Recommendations

1. **Primary**: Build v1 against OpenCode using the outline in §10. The footprint is ~400 lines of Python, ~150 lines of templates, and a 6-line `opencode.json` permission block. No new DB tables, no new CLI flags, no policy code.

2. **Alternative**: Build v1 against Pi using the outline in §3. ~350 LOC Python + a ~40-line TypeScript extension + LF-only JSONL framing. Choose this only if (a) the user wants to test Pi's smaller-context-budget claim in practice, or (b) we anticipate post-v1 scope changes (multi-runtime extensions, custom UI dialogs, autocomplete) that Pi's richer extension API supports more cleanly. Otherwise it's the slightly-more-expensive option.

3. **Do explicitly**: write the design doc to reference R-00074 §1 and §10 as the authoritative v1 surface, and reference R-00073 §14 only as "patterns to grow into when scope expands." This avoids the over-engineering trap retroactively.

4. **Avoid**: building any of the R-00073 §14 components in v1 (policy table, plan-only mode, idempotency_key migration, event-log persistence, per-step DB checkpoints). Each is a real future enhancement; none earns its weight today.

5. **Avoid**: containerizing the OpenCode/Pi subprocess in v1. Repo-bounded `directory` + `external_directory: deny` (OpenCode) or the extension's tool-call filter (Pi) is the right depth for this user.

6. **Plan for**: a small follow-up CR for `iw next-id --idempotency-key <session_id>` independent of the dashboard work. This is a latent CLI issue, not a dashboard-driven concern. Filing it now means it lands before the dashboard does, but it's a separate scope.

---

## Limitations

- This research is a synthesis of R-00071, R-00072, R-00073 plus targeted Python-side fetches (httpx-sse, FastAPI SSE, Pi RPC Python example, our own `routers/sse.py` and `routers/code_qa.py`). It does not re-do the deep architecture surveys; their conclusions stand. If those conclusions are wrong, this re-framing inherits the error.
- The Python code sketches in §2 and §3 are **illustrative**, not production-ready: error handling, logging, structured config, type hints to the project's standard, and `mypy`-clean signatures all need to land in the actual implementation. No-one should copy-paste these blocks; they exist to set the order of magnitude.
- The 256-event ring buffer size is a guess that matches the existing dashboard's SSE polling cadence. If a single `/iw-research` run produces materially more than 256 events (long tool-call streams, lots of token deltas), the buffer should grow. Easy to tune once real usage exists.
- The `prctl(PR_SET_PDEATHSIG)` trick in `opencode_runtime.start()` is Linux-only. If the dashboard ever needs to run on macOS or WSL, we need a portable kill-on-parent-exit pattern (`atexit` + `os.killpg(...)`).
- We have not verified that OpenCode's `permission.asked` event payload includes enough context (the specific bash command, the working directory, a human-readable rationale) to render a useful modal. R-00071 §4 inferred this from the docs but didn't see the wire-level payload. A 30-minute spike — start `opencode serve` locally, set `bash: ask`, run a session, capture an event — would convert this from MEDIUM to HIGH confidence.
- The TypeScript extension sketch for Pi uses a regex-based command filter; a real implementation needs to handle edge cases (quoted args, shell pipelines, env-var indirection). OpenCode's `permission` block does this for us with documented glob semantics; replicating that in TypeScript is more work than the 40-line sketch suggests if we ever pick Pi for v1.
- The recommendation is for v1 *of this specific feature*. As scope grows (multi-user, multi-session, public exposure, untrusted prompts), the R-00073 §14 components return one by one. This doc deliberately doesn't try to time those additions — we'll know when we see the next scope change.

---

## Sources

| # | Source | Credibility | URL |
|---|--------|-------------|-----|
| 1 | R-00071 — OpenCode embedding research (HTTP+SSE surface, permission events) | HIGH | docs/research/R-00071-opencode-dashboard-embedding.md |
| 2 | R-00072 — Pi embedding research (RPC mode, extension UI, head-to-head) | HIGH | docs/research/R-00072-pi-dashboard-embedding.md |
| 3 | R-00073 — Coding-agent-in-web-UI patterns (the over-engineered §14 we're correcting) | HIGH | docs/research/R-00073-coding-agent-web-ui-patterns.md |
| 4 | OpenCode — Server docs (`opencode serve`, endpoints, auth) | HIGH | https://opencode.ai/docs/server/ |
| 5 | OpenCode — Config docs (`permission` block, glob patterns, providers) | HIGH | https://opencode.ai/docs/config/ |
| 6 | Pi — RPC mode (commands, events, LF-only framing, extension UI protocol) | HIGH | https://github.com/badlogic/pi-mono/blob/main/packages/coding-agent/docs/rpc.md |
| 7 | Pi — Extensions docs (tool_call hook, ctx.ui.confirm, plugin signature) | HIGH | https://pi.dev/docs/latest/extensions |
| 8 | httpx-sse — Python SSE client (`aconnect_sse`, `aiter_sse`, ServerSentEvent fields, Last-Event-ID) | HIGH | https://pypi.org/project/httpx-sse/ |
| 9 | FastAPI — SSE + StreamingResponse pattern documentation | HIGH | https://fastapi.tiangolo.com/tutorial/server-sent-events/ |
| 10 | IW AI Core — existing `dashboard/routers/sse.py` (canonical event-generator pattern in this project) | HIGH | dashboard/routers/sse.py |
| 11 | IW AI Core — existing `dashboard/routers/code_qa.py` (canonical streaming-with-worker-thread pattern) | HIGH | dashboard/routers/code_qa.py |
| 12 | IW AI Core — `dashboard/CLAUDE.md` (htmx + EventSource + Tailwind prebuilt patterns) | HIGH | dashboard/CLAUDE.md |
| 13 | Replit / SaaStr July 2025 incident (the R-00073 over-engineering trigger) | HIGH | https://www.theregister.com/2025/07/21/replit_saastr_vibe_coding_incident/ |
| 14 | Mario Zechner — Pi design philosophy (minimal context, no MCP) | HIGH | https://mariozechner.at/posts/2025-11-30-pi-coding-agent/ |

---

## Appendix: Research Log

**Date range**: 2026-05-14 to 2026-05-14
**Queries run**: 2 WebSearch, 3 WebFetch, 2 Read (our own codebase)
**Mode used**: tech
**Depth level**: standard

**Notes**
- The decisive insight from re-reading our own `dashboard/routers/sse.py` and `dashboard/routers/code_qa.py` is that we already have **two canonical SSE-streaming patterns** in production in this codebase. The new `research_chat` router can mirror them closely — minimal new convention to introduce.
- The biggest "I should have caught this in R-00073" is that **OpenCode's `permission` block in `opencode.json` is the entire safeguard layer we need**. Six lines of config replaces R-00073 §14's `POLICY` table + risk-classification code + `WAITING_FOR_CONFIRMATION` state. The user was right to push back.
- The Pi extension sketch is genuinely small (~40 lines), but the asymmetry vs OpenCode's config-only approach is what makes OpenCode the cleaner v1 pick. If Pi added a built-in permission system in a future release, the comparison would flip on this axis.
- The 1-day prototype build estimate in §10 assumes a focused agent + the existing dashboard SSE patterns to copy from. A first-time-on-this-codebase agent should budget 2 days.
