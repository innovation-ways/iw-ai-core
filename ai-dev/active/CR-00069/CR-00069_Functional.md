# CR-00069 — Functional Design

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This change adds, modifies, and removes no migrations.

## Why

Clearing an AI Assistant chat currently pops up a confirmation dialog asking the
user to confirm before the chat is wiped. Because the Clear button is already
switched off whenever there is nothing to clear, and clearing a chat is a quick,
low-cost action, the extra dialog mostly just adds a second click. This change
removes that dialog so clearing is a single, immediate action.

## What Changed (for the User)

- Clicking "Clear" in the AI Assistant now clears the chat straight away.
- There is no longer a popup asking the user to confirm before clearing.
- After clearing, the user still sees a short "Chat cleared." note in the
  conversation, so it is always obvious that the action happened.
- The Clear button still appears switched off when there is no conversation to
  clear, so an empty chat cannot be cleared by accident.

## How It Behaves

When a user has an active chat with messages, the Clear button is available.
Clicking it immediately empties the conversation and shows a brief "Chat
cleared." note in its place. The button then switches off again because there is
nothing left to clear.

When a chat is empty — for example a brand-new tab — the Clear button stays
switched off and clicking the area does nothing, exactly as before. This means
the removal of the confirmation popup does not introduce a risk of clearing
something by mistake: the only time Clear can be pressed is when there is a real
conversation, and the action is quick and clearly acknowledged.

Everything else about clearing a chat is unchanged: the conversation history is
reset on the server, the live updates reconnect, and the user can immediately
start a fresh conversation in the same tab.

## Out of Scope

- This change only affects the Clear action in the AI Assistant; confirmation
  dialogs elsewhere in the application are not touched.
- It does not change what clearing does or how chat history is stored — only
  whether a confirmation popup appears first.
