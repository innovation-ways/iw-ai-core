# I-00086 — Functional Design

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This item leaves migrations unchanged.

## Why

On the item-detail page, users can pick which AI model an individual step uses, or apply one model to every remaining editable step in one go. After picking an option the database is in fact updated, but the page gives no sign of it: no message appears, and the read-only Model column next to the dropdown keeps showing the old value until the user reloads the page. Several users have repeatedly clicked the Apply button thinking it was broken. The goal is to make this control behave the way users already expect — give clear, immediate confirmation that the change took effect.

## What Changed (for the User)

- Picking a model in any per-step dropdown shows a short success message such as "Model updated" and updates the Model column in that row right away.
- Picking a model from the "Apply to remaining steps" selector and clicking Apply shows a success message such as "Model updated for 5 step(s)", where the count reflects the actual number of steps that were eligible to change.
- When Apply is clicked but no step is eligible (everything is already running, done, or merged), a softer informational message appears: "No editable steps to update". The screen no longer goes silent.
- The steps table refreshes in place — there is no full page reload, no scroll jump, and any expanded run-history sections stay where they were.

## How It Behaves

When the user changes the model on a single step, the row's CLI dropdown briefly disables to prevent double-clicks, the server stores the new choice, the steps table re-renders with the new model label visible, and a green confirmation message slides in from the corner of the screen for a few seconds.

When the user uses the bulk Apply control, the system looks at every step that is still editable, updates them all in one shot, and shows a single confirmation message with the count. Steps that are no longer editable — for example, those currently running or already finished — are left alone, and the count in the message reflects only what actually changed.

If something goes wrong — for example the user picks an option that no longer exists in the database, or the item they are looking at has been deleted — the page shows a red error message instead of a silent failure, and the steps table is left untouched.

## Out of Scope

- This incident does not change which models are offered in the dropdown; that list is managed elsewhere.
- This incident does not change what happens when a step actually runs with the chosen model — the orchestrator and daemon behaviour is unaffected.
