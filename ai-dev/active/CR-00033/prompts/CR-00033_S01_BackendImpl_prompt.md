# CR-00033_S01_BackendImpl_prompt

**Work Item**: CR-00033 -- Document Tailwind CLI Fallback Strategy in Tech Stack Docs
**Step**: S01
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (see the 2026-04-22 incident in
docs/IW_AI_Core_DB_Setup.md).

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures.
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This step makes no migrations and changes no migration file. The standard
agent-context migration restrictions still apply: do not run
`alembic upgrade/downgrade/stamp` against the live orchestration DB.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00033 --json` (authoritative).
- `ai-dev/active/CR-00033/CR-00033_CR_Design.md` — Design document (read first).
- `ai-dev/active/CR-00033/CR-00033_Functional.md` — Human-facing summary.
- `docs/IW_AI_Core_Tech_Stack.md` — File you will edit.
- `Makefile` — Source of truth for the `css` target's no-op state (line ~8 declares it `.PHONY`-only).
- `dashboard/static/styles.css`, `dashboard/static/tailwind.src.css`, `dashboard/tailwind.config.js` — Read-only references for the prose you will write (file names must match what is in the repo).
- `ai-dev/active/I-00067/reports/I-00067_self_assess_report.md` — Source finding [3] for evidence citations.

## Output Files

- `ai-dev/active/CR-00033/reports/CR-00033_S01_BackendImpl_report.md` — Step report.
- `docs/IW_AI_Core_Tech_Stack.md` — Edited.

## Context

This CR is **documentation-only**. Your job is to extend §2.4 ("Dashboard") of
`docs/IW_AI_Core_Tech_Stack.md` with an explicit Tailwind CLI fallback strategy,
gently correct the existing prose that implies CLI compilation is reliable, and
add a row (or extend the existing row) in §10 Decisions Log. **Do not touch any
other file.**

Read `CLAUDE.md` first for general project conventions, then read the design doc
in full before editing.

## Requirements

### 1. Add a "Tailwind CLI fallback strategy" subsection under §2.4 Dashboard

Insert a new subsection **immediately after** the existing "Why not the current
custom CSS from InnoForge dashboard" paragraph and **before** the next sibling
section (§2.4 Compression, currently a duplicate-numbered "### 2.4. Compression").

Header text (exact): `### Tailwind CLI fallback strategy`

The subsection MUST contain, in this order, in plain prose (no fenced code
blocks for narrative content; one short fenced block for the rule example is
allowed):

1. Why a fallback is needed: agent worktrees may have an incomplete
   `node_modules` (e.g., the I-00067 fix-cycle hit
   `Cannot find module 'postcss-selector-parser'` when invoking the Tailwind
   CLI). Cite I-00067 by ID, not by file path.
2. The current state of `make css`: declared in `.PHONY` in the `Makefile`
   without a rule body, so `make css` exits with `Nothing to be done for 'css'`.
3. **The rule (must appear verbatim as the operative sentence):**
   *When new styling is required and the Tailwind CLI cannot run, append plain
   CSS rules directly to `dashboard/static/styles.css`.*
4. Why this is safe: `dashboard/static/styles.css` is the file the dashboard
   serves to clients as-is, so plain CSS rules take effect without any
   compilation step. The Tailwind utility classes already on the page continue
   to come from the CDN.
5. When NOT to use the fallback: when the Tailwind CLI is known-good in your
   environment AND `make css` actually produces output. (Today, neither is
   guaranteed in agent worktrees.)
6. A short forward-looking note: a separate change may give `make css` a real
   rule body or remove it from `.PHONY`; until then, this subsection is the
   authoritative guidance.

Total length budget for this subsection: ~150–250 words.

### 2. Update the "Why Tailwind CSS via CDN" paragraph

The current sentence (line ~95) is:

> *"For production-feel without npm, a standalone Tailwind CLI binary can
> generate a static CSS file."*

Rewrite this sentence so it stops implying that CLI compilation is a routine
production path. Acceptable replacement (you may rephrase as long as the
meaning matches):

> *"A standalone Tailwind CLI binary exists for compiling a static stylesheet,
> but it is not reliable inside agent worktrees today — see "Tailwind CLI
> fallback strategy" below."*

Do not delete the original sentence's neighbours. Do not rewrite paragraphs that
are not directly affected.

### 3. Update §10 Decisions Log

The existing row (currently around line 836) reads:

| D3 | CSS framework | Tailwind (CDN) | Custom CSS, Bootstrap | Clean utilities, no build step via CDN, consistent from day one. |

Either:

- (Preferred) Add a new row immediately below D3 referencing the fallback rule,
  e.g., a `D3a` row titled "Tailwind CLI fallback" with rationale "CLI
  unreliable in agent worktrees; append plain CSS to `styles.css`."
- OR extend the D3 "Notes" cell to add: *"When CLI is unavailable, append plain
  CSS to `dashboard/static/styles.css` (see §2.4)."*

Pick whichever fits the table format better. Do not break the table syntax.

### 4. No other edits

- Do NOT edit any file other than `docs/IW_AI_Core_Tech_Stack.md`.
- Do NOT modify the `Makefile`, `dashboard/static/styles.css`, or any code.
- Do NOT add new files.
- Preserve existing Markdown structure: heading levels, table widths, line wrapping
  conventions of the surrounding file (~120 chars).

### 5. Sanity-check the doc compiles

After your edit, eyeball the file for:

- No accidentally-broken tables (pipe alignment, column counts).
- No duplicated headings introduced (the file already has a known
  duplicate-numbered "### 2.4. Compression" — do NOT try to fix that here; it is
  out of scope).
- Internal links/anchors in the file (if any) still resolve.

## Project Conventions

Read `CLAUDE.md` for project conventions. For docs:

- Match the existing tone in `docs/IW_AI_Core_Tech_Stack.md` — concise, factual,
  decisions-with-rationale.
- Use sentence case for headings, not Title Case (matches existing style).
- Do not add emoji.
- Do not introduce new top-level (`##`) sections — stay within `### 2.4.x` and
  the existing §10 table.

## TDD Requirement

This is a documentation-only change. There is no testable runtime behavior.
TDD does not apply to this step. Skip the RED/GREEN/REFACTOR loop and explain
this in your report's `notes` field.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Even though no Python is touched, run these before reporting completion:

1. `make format-check` — must pass. Use the *check* variant (not `make format`), so a pre-existing formatting drift on `main` cannot silently rewrite a Python file inside this CR's diff and trip AC5 / the S02 scope check.
2. `make typecheck` — must report zero new errors.
3. `make lint` — must report zero new errors.

If any tool flags a file you did NOT touch as already-broken on `main`, note it
in `preflight` as a pre-existing issue and proceed.

## Test Verification

Run `make test-unit` to confirm no regressions. Markdown changes should not
affect any test, but run the suite anyway to confirm.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "CR-00033",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "docs/IW_AI_Core_Tech_Stack.md"
  ],
  "preflight": {
    "format": "ok|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": "Documentation-only change; TDD does not apply."
}
```
