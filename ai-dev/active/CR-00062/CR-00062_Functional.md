# CR-00062 — Functional Design

<!--
Audience: humans (product owners, support, onboarding engineers).
Keep total body at most 500 words. Plain English. No file paths, class names, SQL, or code fences.
-->

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

This change adds one Alembic migration (data-only inserts into the runtime catalogue). No table or column DDL is changed.

## Why

The platform currently lets a project pick one of two agent runtimes — Claude Code or OpenCode — through a single per-project setting. The user installed a third runtime, Pi, locally and wants it as a peer option. Pi is a provider-neutral, MIT-licensed CLI that supports the same one-shot prompt-in, output-out shape the platform already uses, so adding it is wiring rather than redesign. The change is additive — no project is forced off its current runtime.

## What Changed (for the User)

- The runtime picker in the dashboard shows two extra options: "Pi + MiniMax 2.7" and "Pi + GPT-5.3 Codex". Both are non-default and enabled, so an operator can select them per work item or per step.
- An operator who sets a project's runtime to "pi" in the registry sees that project run with Pi for all step launches, fix cycles, automated merge resolutions, and AI documentation regeneration jobs.
- The platform now rejects typos in the runtime field. A project configured with a misspelled runtime value is skipped at startup with a warning, rather than silently defaulting to OpenCode.
- The sync-agents command reports a new "Pi agents" line in its output, alongside the existing Claude and OpenCode lines.

## How It Behaves

When a project is configured to use Pi, every place where the daemon needs to ask an agent to do something — running a workflow step inside a worktree, retrying after a code-review finding, regenerating a documentation page, or attempting an automated merge resolution — invokes the Pi CLI in print mode with the project's chosen model. The platform pipes the prompt in, captures the output, and routes it the same way it has always routed Claude Code or OpenCode output.

Pi reads agent definitions from a per-project Pi directory created by sync-agents, and reads skill definitions from the same shared skills directory the other runtimes already use. Existing skill files require no edits.

If an operator picks a Pi runtime for an in-flight item and the catalogue rows are later disabled, the in-flight item keeps its pinned runtime; new items fall back to the platform default.

## Out of Scope

- Switching any existing project to Pi. The wiring is added and proven by tests against a stub Pi binary; a follow-up picks a pilot project once Pi has run cleanly.
- Embedding Pi inside the dashboard chat experience. That was evaluated separately and rejected.
