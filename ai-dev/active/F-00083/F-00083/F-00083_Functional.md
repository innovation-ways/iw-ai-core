# F-00083 — Functional Design

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. This work adds no migrations — there are no new database tables.)

## Why

Today, asking the AI assistant for help with platform tasks — kicking off a research, debugging a failing item, walking through a feature — means leaving the dashboard for a terminal and driving a coding agent CLI by hand. That breaks the flow. This work brings the same assistant into the dashboard as a side panel that follows the user across every page, so the conversation lives where the work lives.

## What Changed (for the User)

- A collapsible chat panel sits on the left of every dashboard page. A keyboard shortcut opens and closes it; the open/closed state persists as the user moves around.
- Each browser tab gets its own conversation. Two tabs run two threads in parallel without mixing.
- The assistant lists every skill and slash command it knows — the same ones available from the terminal — and a slash-key autocomplete suggests them as the user types.
- A model picker chooses which model drives the conversation. A small indicator shows how much of the working memory is in use.
- When the assistant wants to do something with side effects — edit a file, run a shell command, write a record — a confirmation card appears. The user can allow, deny, or cancel mid-run.
- When viewing a specific item, batch, research, doc, or code module, a small "currently viewing" tag is added next to the input. The user can dismiss it before sending.
- The existing assistant in the Code view (which answers questions about code modules) keeps working exactly as before. The two are deliberately separate: the Code one is a question-and-answer surface for code understanding; the new one is the full tool-using assistant.

## How It Behaves

- Open the panel, type a prompt, send. The assistant streams its answer. Anything risky pops a confirmation card; the run pauses until the user clicks allow or deny.
- A new chat button starts a fresh conversation; a history dropdown jumps back into a previous one.
- If the network blips or the tab is refreshed mid-answer, the panel reconnects and the answer keeps streaming where it left off. Long pauses may lose the oldest events, but the conversation itself is preserved on disk and re-renders on reload.
- If the underlying service crashes, the panel reconnects automatically. If it can't recover, an "assistant unavailable" banner appears and the input is disabled until the platform recovers.
- From the Research view, a one-click button opens the panel with the right command pre-typed.

## Out of Scope

- A separate run-debugging skill for items in error. This panel is the surface for it; the skill itself ships separately.
- An alternative lightweight assistant runtime explored during planning. The architecture leaves room for it as a future option; only the primary runtime ships here.
- Persisting every chat event to the platform database. The assistant's own on-disk session storage is the record for now.
