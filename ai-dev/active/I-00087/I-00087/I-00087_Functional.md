# I-00087 — Functional Design

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This work item leaves migrations unchanged.

## Why

After the previous chat-panel fixes shipped, manual testing surfaced that the AI Assistant still does not show the model's reply. Users see their own message, then a muted "Session idle." line, and nothing in between — even though the language model genuinely answered. This is a P1 usability bug that makes the assistant feel broken. The goal is to make the assistant actually look like it is talking back, and to keep the conversation visible across page refreshes.

## What Changed (for the User)

- Sending a prompt now shows the assistant's reply streaming in, word by word, in its own bubble below the user's message.
- When the assistant invokes a tool (read a file, run a command, etc.) a small system breadcrumb appears so the user can see what is happening.
- When the assistant needs to ask the user for permission, the existing approval modal again appears at the right moment (it had silently stopped working).
- Refreshing the page or returning later restores the full conversation — both the user's and the assistant's turns — instead of clearing the visible history.
- Errors from the model (provider auth, quota, abort) now render as an error message in the panel rather than being silently dropped.

## How It Behaves

- The panel keeps its existing session model: each browser tab owns one assistant session, identified by a session ID stored in browser session storage. Reusing that ID across reloads is how context is kept with the model.
- When the user sends a prompt, the panel asks the assistant to start a streaming reply. As tokens stream back, the panel updates the same reply bubble in place. When the assistant signals it is done, the bubble is marked final and the input is re-enabled.
- If the network blips, the panel reconnects and asks the assistant to resume from the last event it saw, so partially streamed replies are not duplicated.
- "New chat" clears the visible log, drops the cached session ID, and starts a fresh session on the next prompt.
- Switching to a past session from the history list loads that session's full conversation and connects its live stream.
- Tool breadcrumbs, permission modals, and error messages all render as soon as the corresponding event arrives.

## Out of Scope

- Richer tool-call rendering (inline inputs and outputs) — only a one-line breadcrumb is added.
- A separate "thinking" view for the assistant's reasoning steps.
- Adding a JavaScript unit-test framework — coverage relies on the existing pytest harness plus the end-to-end browser verification step.
