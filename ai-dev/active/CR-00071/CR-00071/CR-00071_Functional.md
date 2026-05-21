# CR-00071 — Functional Design

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This change adds, modifies, and removes no migrations.

## Why

The AI Assistant recently gained a small context-usage percentage next to the
Clear button, so users can tell how full a conversation's context window is
getting. That indicator was built for one chat engine only. Shortly afterwards
the AI Assistant switched to a different engine as its default, and that engine
was never wired up — so the percentage now never appears for new chats. This
change extends the indicator to the new default engine so the figure is visible
again for everyday use.

## What Changed (for the User)

- The context-usage percentage now appears for chats running on the AI
  Assistant's current default engine, not just the older one.
- The percentage shows in the same place as before — just to the left of the
  Clear button — and behaves identically: a neutral tone under 70%, an amber
  tone from 70% up to 90%, and a red tone at 90% or above.
- It appears as soon as a chat tab is opened or switched to, and refreshes on
  its own while the assistant is generating a reply.
- Nothing changes for chats on the older engine — they keep showing the
  percentage exactly as before.

## How It Behaves

When a user opens the AI Assistant and selects a chat tab, the system works out
how much of that conversation's context window is in use and shows it as a
percentage. This now happens regardless of which engine the chat is running on.

The figure is based on the real size of the conversation so far and the context
limit of the model in use. The colour acts as an at-a-glance health signal: most
of the time the value sits in the neutral range, turns amber as the conversation
approaches the limit, and turns red when the model is very close to its limit
and earlier messages may already be getting dropped.

If a chat has no usage data yet — for instance a brand-new empty chat, or a chat
whose model has no known context limit — the percentage is simply hidden, just
as it is today. There is no misleading zero and no placeholder. In other words,
the worst case after this change is exactly the same as the current behaviour:
the percentage is either shown correctly or not shown at all.

## Out of Scope

- This change does not add warning popups, automatic clearing, or hard limits —
  the percentage remains a passive indicator only.
- It does not change how conversations are stored or how any model behaves; it
  only measures and displays usage.
