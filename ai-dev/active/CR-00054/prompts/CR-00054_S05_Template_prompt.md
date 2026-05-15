# CR-00054_S05_Template_prompt

**Work Item**: CR-00054 -- Add OpenCode stub to worktree E2E stack
**Step**: S05
**Agent**: template-impl

---

## ⛔ Docker is off-limits

Standard policy. This step only edits markdown.

## ⛔ Migrations: agents generate, daemon applies

This step does NOT touch migrations.

## Input Files

- `docs/IW_AI_Core_Testing_Strategy.md` — to be appended
- `ai-dev/active/CR-00054/CR-00054_CR_Design.md` — design contract
- `scripts/e2e_opencode_stub.py` — written by S01 (read for accurate references)
- `Dockerfile.e2e` — modified by S02 (read for accurate references)
- `docker-compose.e2e.yml` — modified by S03 (read for accurate references)

## Output Files

- `docs/IW_AI_Core_Testing_Strategy.md` — updated
- `ai-dev/active/CR-00054/reports/CR-00054_S05_Template_report.md` — step report

## Context

You are implementing **S05** — adding a new "E2E OpenCode stub" subsection to `docs/IW_AI_Core_Testing_Strategy.md` documenting the stub, its scope, and how to extend it.

## Requirements

### 1. Find the right insertion point

Locate the existing "E2E stack" / "browser_verification" section in `docs/IW_AI_Core_Testing_Strategy.md` that describes the `e2e-ollama` stub pattern. The new subsection goes **after** that one.

If no E2E stack section exists yet, create a new top-level section titled `## E2E browser-verification stack` and place this subsection under it.

### 2. Content of the new subsection

```markdown
### E2E OpenCode stub (CR-00054)

The chat features in F-00083 introduced a managed `opencode serve` subprocess that the production daemon spawns on the dashboard host. The per-worktree e2e stack does **not** install the real `opencode` binary because it would balloon the image with ~100 MB and an LLM-provider config the stack does not own. Instead the e2e image ships a thin shim at `/usr/local/bin/opencode` that execs a Python stub server (`scripts/e2e_opencode_stub.py`) implementing opencode v1.15.0's HTTP+SSE wire protocol.

The pattern mirrors the existing `e2e-ollama` stub: a focused, deterministic in-process server that replaces a heavier runtime for browser_verification.

**Surface implemented**

| Path | Behaviour |
|------|-----------|
| `GET /global/health` | Unauthenticated 200 (used by OpencodeRuntime's startup poll) |
| `GET /config` | Returns one stub model (`stub/echo`) + default model + default agent |
| `POST /session` · `GET /session` · `GET /session/{sid}` · `GET /session/{sid}/messages` | Process-local session CRUD |
| `POST /session/{sid}/prompt_async` | Emits a deterministic event sequence on `/event` (message → message → permission.asked → pause → message/idle) |
| `POST /session/{sid}/abort` | Emits `session.idle` with `aborted: true` |
| `POST /session/{sid}/permissions/{rid}` | Forwards the allow/deny response and emits a follow-up event |
| `GET /event` | Long-lived SSE; ring buffer (`deque(maxlen=256)`) supports `Last-Event-ID` replay |

**Auth**: HTTP Basic with username `opencode` and the per-startup `OPENCODE_SERVER_PASSWORD` env var, matching the real runtime.

**Determinism**: The stub's event sequence is a fixture, not a behaviour spec. Tests that need a richer agent surface (real tool calls reading files, multi-turn planning, etc.) must either extend the stub OR run against a real local `opencode serve` outside the e2e stack.

**Extending the stub**

When a new chat-related qv-browser step needs richer events:
1. Add the new event shape to `scripts/e2e_opencode_stub.py`'s synthetic sequence.
2. Add a matching integration test in `tests/integration/test_e2e_opencode_stub.py`.
3. Update this section's "Surface implemented" table.
4. If the wire-protocol bumps (opencode v1.16+, etc.), update both the stub and the host `opencode` binary's pinned version in the developer-docs README.

**Why a stub, not the real binary**: same trade-offs as the `e2e-ollama` stub — image size, build time, no LLM-provider config in CI, deterministic outputs for assertions.
```

### 3. Add a one-line reference from the Architecture doc (optional)

If `docs/IW_AI_Core_Architecture.md` contains an end-to-end-flow section that mentions the chat panel, add a single sentence noting that the e2e stack uses a stub for OpenCode. Keep it short. If you don't find a natural insertion point, skip this — the testing-strategy doc is the canonical reference.

### 4. Section ordering / table-of-contents

If the testing-strategy doc maintains a TOC at the top, update it to include the new subsection.

## Project Conventions

Read `CLAUDE.md` and `doc-system/CLAUDE.md` (if present) for documentation tone. Match the existing testing-strategy doc's voice: terse, factual, example-driven.

## TDD Requirement

Documentation-only. Use `tdd_red_evidence: "n/a — template/markdown edits only, no production logic"`.

## Pre-flight Quality Gates

- `make format`: not applicable to markdown (record as `n/a`).
- `make typecheck`: not applicable.
- `make lint`: runs `scripts/check_templates.py` on Jinja2 templates only; markdown is not in scope. Record as `n/a` unless lint actually scans markdown.

## Test Verification

`tests_passed: true` with `test_summary: "n/a — doc-only change"`.

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "template-impl",
  "work_item": "CR-00054",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["docs/IW_AI_Core_Testing_Strategy.md"],
  "preflight": {
    "format": "n/a",
    "typecheck": "n/a",
    "lint": "n/a"
  },
  "tests_passed": true,
  "test_summary": "n/a — doc-only change",
  "tdd_red_evidence": "n/a — template/markdown edits only, no production logic",
  "blockers": [],
  "notes": ""
}
```
