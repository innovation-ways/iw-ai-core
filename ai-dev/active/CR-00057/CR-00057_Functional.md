# CR-00057 — Functional Design

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

This change does not add or modify any database migration.

## Why

The AI Assistant chat panel shows nearly forty model options today, most of them duplicates of the same MiniMax variant tagged with different provider aliases. Operators have no way to say "for this installation, only offer these models" — the dropdown is whatever the underlying chat runtime happens to advertise. The team also wants Gemma 4 (26B) running on the in-house Ollama server to be a first-class choice, which today it is not.

## What Changed (for the User)

- The model dropdown now shows only the models explicitly approved for the project the operator is viewing.
- For the IW AI Core project, the dropdown shows exactly five entries — Claude Opus 4.7, Claude Sonnet 4.6, MiniMax 2.7, GPT-5.3 Codex, and Gemma 4 26B — with Claude Opus 4.7 selected by default.
- Operators can edit the list per project by changing a small block in the platform's project registry and asking the daemon to reload.
- Selecting any of those five and sending a prompt produces a real reply, including the new Gemma 4 26B option served from the in-house GPU host.
- On pages not scoped to a single project, the dropdown gracefully falls back to the unfiltered list.

## How It Behaves

When the chat panel opens, it reads the page address to determine which project the operator is viewing and asks the dashboard for that project's approved models. The dashboard returns the intersection of the approved list with whatever the chat runtime can actually reach. If an approved model is unreachable — for example, somebody forgot to set up the Ollama provider on a new machine — that entry is quietly omitted and a single warning is logged so operators can see the cause.

If a project has no approved list, the dropdown falls back to today's behaviour: every model the runtime advertises is shown. Existing installations keep working without any configuration change. A short log note makes the fallback visible.

Changing the approved list takes effect within roughly a minute: an operator updates the registry, signals the daemon to reload, and the next time the chat panel opens its dropdown the new list is in place. Sessions already running keep using the model they started with.

When a model labelled "Claude Opus 4.7" or "Claude Sonnet 4.6" is picked, the request is sent through the existing chat runtime using the Anthropic API key — not the standalone Claude Code subscription. The dropdown labels and the new documentation page call this out so the labelling is not misread.

## Out of Scope

- A native Claude Code runtime path for the chat panel. Deferred.
- A direct Ollama path that bypasses the existing chat runtime. Ollama enters via the existing runtime's provider configuration.
