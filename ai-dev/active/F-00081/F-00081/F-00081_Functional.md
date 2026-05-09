# F-00081 — Functional Design

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This work adds one migration: a small lookup table, seed rows, and three optional foreign-key columns.

## Why

Every step the daemon launches today runs with the same default agent and model — OpenCode plus MiniMax. Operators cannot say "this item should run on Claude Code with Opus" or "this failing step should retry on a different agent". The user wants control over which agent and which model each item, and each individual step, runs on, while leaving the existing default in place for anyone who does not care to change it.

## What Changed (for the User)

- A new pair of dropdowns — **CLI** (OpenCode or Claude Code) and **Model** (MiniMax, Sonnet, Opus, …) — appears on every batch's items tab and on every item detail page.
- The combinations are curated and paired: the model dropdown only ever shows models the chosen CLI supports. New combinations are added centrally without code changes.
- The strip of coloured circles for step status becomes a compact bar of slim segments. The same green / blue / red / grey signals remain, but the row no longer eats horizontal space.
- On the batch items tab the override is set per item. A small dot next to the badge marks items whose individual steps carry their own different overrides.
- On the item detail page, every step row has its own dropdowns. They are editable while the step is pending, failed, or paused. Once the step starts, completes, is skipped or cancelled, they become read-only labels showing what actually ran.
- An "Apply to all remaining" shortcut sets the same override on every still-editable step under the item.
- Changes are recorded in the audit log as a single event per click, even when one click changes many steps.

## How It Behaves

- If you do nothing, the system behaves exactly as before. Steps inherit the project default — currently OpenCode plus MiniMax.
- An item-level override applies to every step under that item without its own override, next time those steps launch.
- A step-level override wins over the item-level override, which wins over the project default.
- A running step is never interrupted by a change. The new choice takes effect the next time the daemon picks up a step.
- Failed and paused steps are editable on purpose. If a step keeps failing on one agent you can switch it before the daemon retries.
- The catalogue is protected: the platform refuses to disable or delete the entry marked as the global default.
- Adding a new model or agent later is configuration, not code. Operators add a row and the dropdowns offer it next page load.

## Out of Scope

- A self-service admin screen for editing the catalogue from the browser. Catalogue edits go through migrations or direct SQL for now.
- Cost warnings or guardrails when picking the more expensive model. The user explicitly chose to trust whoever sets the override.
