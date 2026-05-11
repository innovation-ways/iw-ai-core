# I-00081 — Functional Design

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.) This work touches no Docker state.

## ⛔ Migrations: agents generate, daemon applies

This work adds no migrations and changes no database schema.

## Why

A user reported that the project Code page was showing "Syntax error in text — mermaid version 11.14.0" instead of the architecture diagram, reproduced live on the dashboard. The cause is that the architecture-diagram document can be stored in two different shapes — a plain diagram definition (produced by the code-understanding indexer) or a full mini-document containing several diagrams plus explanatory text (produced by the documentation generator) — and the Code page only knew how to display the first shape. When it received the second shape it handed the whole document, headings and all, to the diagram renderer, which failed. The goal is to make the Code page display either shape correctly.

## What Changed (for the User)

- The "Architecture Diagram" panel on a project's Code page now renders the diagrams correctly even when the architecture-diagram document was produced by the documentation generator (the multi-diagram, with-explanations form). The earlier "Syntax error in text" box and the wall of red error text are gone.
- When the document contains several diagrams, all of them now appear in the panel, each with its short "Why this diagram?" note, instead of nothing.
- Projects whose architecture-diagram document is the simpler single-diagram form continue to display exactly as before — one diagram, with its purpose line above it.

## How It Behaves

When the Code page opens the architecture-diagram document, it first looks at what kind of content it holds. If the content is a full mini-document (it contains fenced diagram blocks), the page renders that document the same way the rest of the architecture write-up is rendered: the heading is dropped (the panel already has its own title), each diagram block is turned into a live diagram, and the explanatory notes appear between them. If the content is just a bare diagram definition, the page keeps doing what it did before — show that one diagram with its purpose line. In both cases the diagrams are drawn in the browser and follow the current light/dark theme. Layout hints inside generated diagrams that the browser-side renderer doesn't support are removed before drawing so they can't break rendering. The same handling applies whether the panel is loaded as part of the full Code page or refreshed on its own.

## Out of Scope

- The Docs page rendering of diagram documents (tracked separately).
- Changing how either the code-understanding indexer or the documentation generator produces the architecture-diagram document — this work only changes how the Code page reads what is already stored.
