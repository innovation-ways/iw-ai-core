# CR-00063 — Functional Design

<!--
Audience: humans (product owners, support, onboarding engineers).
DO NOT include file paths, class names, SQL, code fences, or implementation
steps. If you need to capture those, they belong in the technical design doc.
Keep the total body at most 500 words (the review skill blocks >500).
-->

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

This item leaves migrations unchanged — it is a frontend-only fix with no database changes.

## Why

When a user closes their browser and reopens the AI Assistant, the chat panel appears empty even though the conversation history is intact in the background. The agent can still answer questions correctly (proving the history is there), but past messages are invisible. This creates a confusing experience — users cannot see what they previously discussed and may not trust that their context was preserved.

## What Changed (for the User)

- Reopening the browser (or refreshing the page) now shows the full conversation history in the chat panel, including user messages, assistant responses, and tool activity.
- If the chat history cannot be loaded (for example, because the AI runtime is temporarily starting up), a clear error message is shown in the panel instead of a silent empty state.
- When multiple chat tabs exist, the panel now reopens on the most recently used tab rather than defaulting to the first tab in the list.

## How It Behaves

On page or browser reload, the chat panel performs the following steps:

1. Fetches the list of chat tabs from the server.
2. Selects the tab that was most recently active (based on the last-used timestamp stored on the server, so it works even when browser session data is cleared).
3. Loads the full message history for that tab from the AI runtime session.
4. Renders all message types in order: user messages, assistant responses, and any tool-related activity (such as web searches or code lookups performed during the conversation).
5. If the history cannot be retrieved, an error banner appears in the chat panel so the user knows something went wrong — the panel no longer silently shows nothing.

After this fix, the behavior on browser restart matches what a user would expect: their prior conversation is visible and they can continue where they left off.

## Out of Scope

- This fix does not change how messages are stored or persisted — history lives in the AI runtime session as before.
- Clearing conversation history is a separate feature (CR-00064).
