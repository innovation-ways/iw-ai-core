# CR-00067 — Functional Design

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This change adds, modifies, and removes no migrations.

## Why

When chatting with the AI Assistant, users have no way to tell how much of the
conversation's context window has been consumed. As a long conversation grows,
the model silently begins to lose track of earlier messages, which feels like
unexplained misbehaviour. This change gives users a clear signal so they can
decide when to clear the chat or start a fresh tab before quality degrades.

## What Changed (for the User)

- A small percentage value now appears in the AI Assistant's message box footer,
  just to the left of the "Clear" button.
- The number shows how much of the chat's context window is currently in use,
  for example "42%".
- The value changes colour as usage rises: a calm neutral tone under 70%, an
  amber tone from 70% up to 90%, and a red tone at 90% or above.
- The percentage appears straight away when a chat tab is opened or switched to,
  and updates live while the AI is generating a reply.
- When there is no active chat, or no usage figure is available yet, the
  percentage is simply not shown — no placeholder, no zero.

## How It Behaves

When a user opens the AI Assistant and selects a chat tab, the system works out
that tab's current context usage and shows it as a percentage next to the Clear
button. The figure is based on the real size of the conversation so far and the
context limit of the model in use.

The colour acts as an at-a-glance health signal. Most of the time the value sits
in the neutral range. As the conversation approaches the context limit, the
value turns amber to invite the user to wrap up or clear the chat. If it reaches
the red range, the user knows the model is very close to its limit and earlier
messages may already be getting dropped.

While the AI is generating a reply, the figure refreshes on its own so it stays
current as the conversation grows. Once the reply is finished the value holds
steady — which is correct, because the context does not change while the chat is
idle. Switching to a different tab updates the percentage to reflect that tab.

If a tab has no usage data yet — for instance, a brand-new empty chat, or a chat
on a runtime that does not report usage — the percentage is hidden rather than
showing a misleading zero.

## Out of Scope

- This change does not add any warning popups, automatic clearing, or hard
  limits — it is a passive indicator only.
- It does not change how the AI Assistant stores conversations or how the
  underlying model behaves; it only measures and displays usage.
