# CR-00064 — Functional Design

<!--
Audience: humans (product owners, support, onboarding engineers).
DO NOT include file paths, class names, SQL, code fences, or implementation
steps. If you need to capture those, they belong in the technical design doc.
Keep the total body at most 500 words (the review skill blocks >500).
-->

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

This item leaves migrations unchanged — it is a frontend and API change with no database schema changes.

## Why

The AI Assistant chat panel has no way to reset a conversation. Once a user has had a lengthy exchange on one topic, the LLM carries that entire context forward into new questions — even after a browser reload. Users who want a genuinely fresh start (different topic, removal of sensitive prior context, or simply a cleaner slate) must create a new chat tab manually, which leaves the old history visible in the tab list. A dedicated Clear button gives users a one-click way to wipe the current conversation and start over without disrupting their tab organisation.

## What Changed (for the User)

- A new "Clear" button appears in the chat input area, next to the Abort button.
- The button is greyed out when the conversation is empty and becomes active as soon as any messages are present.
- Clicking Clear shows a short confirmation: "Clear chat history? This cannot be undone."
- After confirming, the entire conversation disappears from the chat window and the AI's memory of the session is reset. A brief "Chat cleared" notice confirms the action.
- The chat tab keeps its name and position — only the messages and context are gone.
- Cancelling the confirmation leaves everything exactly as it was.

## How It Behaves

When the user clicks Clear on a tab with history, a browser confirmation appears. If they cancel, nothing happens. If they confirm, the system performs a full reset in one step: the backend creates a brand-new AI session linked to the same tab, the chat window is cleared, and stream tracking is reset so the next assistant response starts fresh. A short "Chat cleared" notice confirms success. The Clear button immediately goes back to its disabled state, reflecting the now-empty conversation.

If the clear operation fails (for example, if the AI runtime is temporarily unavailable), an error message appears in the chat panel and the existing history is preserved — no partial state.

The feature works identically regardless of whether the tab is using the standard OpenCode runtime or the Pi runtime.

## Out of Scope

- Clearing does not delete the tab or move it to the history list — the tab stays in place with the same name.
- There is no "undo" for a clear operation. Prior messages are not archived or recoverable after confirming.
