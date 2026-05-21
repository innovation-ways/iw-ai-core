# CR-00068 — Functional Design

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This change adds, modifies, and removes no migrations.

## Why

The AI Assistant panel currently offers two separate ways to change the model
for a chat: a model bar sitting above the conversation, and a model picker
inside the settings panel. Having the same control in two places adds clutter
above the conversation and makes the panel busier than it needs to be. This
change removes the redundant model bar and keeps a single, clear place to change
the model.

## What Changed (for the User)

- The model bar that used to appear just above the conversation in the AI
  Assistant is gone.
- Changing the model for a chat is now done in one place: the settings panel,
  opened from the menu button near the message box.
- Each chat tab still shows a small badge with its model name, so users can
  still see at a glance which model a tab is using.
- The conversation area is slightly taller and less cluttered, since the bar no
  longer takes up space at the top.

## How It Behaves

When a user opens the AI Assistant and selects a chat tab, the conversation is
shown without a model bar above it. To see or change the model for the current
chat, the user opens the settings panel from the menu button beside the message
box; the settings panel lists the model alongside the chat title and runtime,
and changing it there updates the chat as before.

The small model badge on each tab in the tab strip is unchanged — it continues
to label every tab with its model, which is enough for users to tell tabs apart
at a glance without a separate bar.

Switching between tabs, opening and closing the settings panel, and collapsing
or expanding the whole AI Assistant all behave exactly as before, just without
the extra bar.

## Out of Scope

- This change does not alter how models are chosen, validated, or applied — only
  where the control to change them lives.
- The small per-tab model badge in the tab strip is intentionally kept and is
  not affected.
