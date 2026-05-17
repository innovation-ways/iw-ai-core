# CR-00057_S05_Template_prompt

**Work Item**: CR-00057 — AI Assistant chat model allowlist (per-project, with Ollama provider)
**Step**: S05
**Agent**: template-impl

---

## ⛔ Docker is off-limits

Standard policy. This step does not touch containers.

## ⛔ Migrations: agents generate, daemon applies

This step does not touch migrations.

## Input Files

- `ai-dev/active/CR-00057/CR-00057_CR_Design.md` — design (read AC1 and AC5)
- `projects.toml` — registry file you are seeding
- `CLAUDE.md` — Quick Navigation table you are appending to
- `docs/IW_AI_Core_Tech_Stack.md` — existing tech-stack doc for cross-reference
- Opencode docs — verify the **current** `ollama` provider config shape via context7 (`mcp__context7__resolve-library-id` then `mcp__context7__query-docs`) for opencode 1.14.x or whatever the project's lockfile pins. Do NOT guess the JSON shape from memory.

## Output Files

- `ai-dev/active/CR-00057/reports/CR-00057_S05_Template_report.md`
- Modified: `projects.toml`
- Modified: `CLAUDE.md` (one row in the Quick Navigation table)
- New: `docs/IW_AI_Core_AI_Assistant_Models.md`

## Context

You are doing three things:

1. Seed the `[projects.iw-ai-core.ai_assistant]` block in `projects.toml` so the new behavior actually fires once the daemon reloads.
2. Document the chat allowlist mechanism + the opencode `ollama` provider configuration in a new doc page so operators can replicate it on a fresh machine.
3. Add a Quick Navigation row in CLAUDE.md so the new doc is discoverable.

## Requirements

### 1. Seed `projects.toml`

Append (or insert in the natural location for the `iw-ai-core` block):

```toml
[projects.iw-ai-core.ai_assistant]
models = [
  "anthropic/claude-opus-4-7",
  "anthropic/claude-sonnet-4-6",
  "minimax/MiniMax-M2.7",
  "openai/gpt-5.3-codex",
  "ollama/gemma4:26b",
]
default_model = "anthropic/claude-opus-4-7"
```

Do **not** modify any other project's block. Other projects (innoforge, cv, Podforger) will continue to use the fail-open path until their owners add their own blocks.

### 2. New doc page: `docs/IW_AI_Core_AI_Assistant_Models.md`

Structure (mirror the tone and table style of `docs/IW_AI_Core_DB_Setup.md`):

- **What this page covers** — one-paragraph framing.
- **The allowlist contract** — describe the `[projects.X.ai_assistant]` shape (`models`, `default_model`), validation rules (`provider/model` regex), and fail-open semantics.
- **How the dashboard uses it** — one-line: dashboard intersects the allowlist with opencode's `/config/providers` per request, project-keyed 30 s cache.
- **Configuring opencode providers** — concrete steps for `anthropic`, `openai`, `minimax`, and `ollama`. For the ollama section: paste the exact JSON shape you verified via context7 (`provider`/`baseURL`/`models` fields, whatever opencode 1.14.x expects). Show two examples: a localhost Ollama (for laptops) and the IW AI Core production wiring against `http://iw-dev-01:11434`.
- **Label honesty** — explicit paragraph: `anthropic/*` rows in the allowlist route through opencode's Anthropic provider key, **not** the standalone `claude-code` CLI subscription. Operators should not interpret "Claude Opus 4.7" in the dropdown as "Claude Code".
- **Operational notes** — refreshing after edits (SIGHUP + 30 s cache); how to remove a model; how to debug "model not in dropdown" (check the WARNING log line; verify opencode's `opencode models` lists it).
- **Out of scope** — same three bullets as the design doc.

Do not embed implementation file paths inline beyond what's necessary for the operator (e.g. `~/.config/opencode/opencode.json` and `projects.toml` are fine; deep links into `dashboard/routers/chat.py` are not — they belong in the design doc).

### 3. CLAUDE.md Quick Navigation row

In `CLAUDE.md` under the "Quick Navigation" table, add a row:

```markdown
| AI Assistant model allowlist | `projects.toml` `[projects.X.ai_assistant]` · `docs/IW_AI_Core_AI_Assistant_Models.md` |
```

Place it in a logical spot (next to other dashboard/chat rows if any; otherwise near the configuration row). Do not reflow the rest of the table.

### 4. Opencode provider config (DO NOT TOUCH host config files)

You must **not** edit any file under `~/.config/opencode/`, `~/.local/share/opencode/`, or any other host-level user config. Those are operator-owned. Your job is only to **document** the configuration in the new doc page so an operator can apply it manually. The CR's acceptance is per-machine — the doc page is the lever.

### 5. Lint and template-check

```bash
make lint     # runs ruff + node --check + scripts/check_templates.py
```

Markdown files are not template-checked, but a malformed table row in CLAUDE.md can still be a review failure — eyeball your edit.

## Project Conventions

- Markdown style follows existing `docs/IW_AI_Core_*.md` files (H1 + H2 sections, tables for structured data, fenced code blocks for shell/JSON).
- Use absolute paths (e.g. `~/.config/opencode/opencode.json`) when referring to user-level config files.
- No marketing language. Plain operator-facing documentation.

## TDD Requirement

Use `"n/a — template/markdown edits and projects.toml seed; no production code path added"` for `tdd_red_evidence`.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

`make format` (no-op for markdown); `make typecheck` (no-op); `make lint` (must pass — template-check runs Jinja2 only, but CLAUDE.md row malformed-pipe could trip a reviewer).

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "template-impl",
  "work_item": "CR-00057",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["projects.toml", "docs/IW_AI_Core_AI_Assistant_Models.md", "CLAUDE.md"],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "n/a — docs + config seed",
  "tdd_red_evidence": "n/a — template/markdown edits and projects.toml seed; no production code path added",
  "blockers": [],
  "notes": "Record the exact opencode provider JSON shape you verified via context7 so the design-review can spot version drift."
}
```
