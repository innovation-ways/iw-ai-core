# CR-00070 — Functional Design

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt. This change uses no Docker.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This change leaves database migrations unchanged — no schema change.

## Why

When an operator looks at a work item's steps, each step shows a picker for which agent and model will run it. By default every step is set to "Inherit", which hides the real choice — the operator cannot tell whether the step will run on, say, Pi with MiniMax 2.7 or something else. The only time the actual agent and model become visible is after the step has already run. This change was requested so the effective agent and model are clear before execution, removing a routine source of confusion and accidental wrong-model runs.

## What Changed (for the User)

- The runtime picker on each step no longer shows the bare word "Inherit". It now shows the actual agent and model that will run, followed by the word "(inherited)" — for example "Pi + MiniMax 2.7 (inherited)".
- The "Apply to remaining steps" picker at the bottom of the steps table gets the same treatment: its default entry shows the real agent and model with the "(inherited)" tag.
- The "(inherited)" tag makes it easy to tell at a glance whether a step is simply following the default, or has been deliberately pinned to a specific agent and model.
- Nothing about choosing or clearing a runtime changes — only the wording the operator sees.

## How It Behaves

The picker works out the effective agent and model the same way the system does when it actually launches a step. If the whole work item has been set to a particular agent and model, every step that has not been individually changed shows that item-level choice, tagged "(inherited)". If the item has no such setting, the picker shows the project's configured default, tagged "(inherited)".

Selecting the "(inherited)" entry still means "no explicit choice for this step" — it simply lets the step follow the default, exactly as before. Picking a specific agent and model from the list still pins that step. The "Apply to remaining steps" control behaves the same as today; only its label is clearer.

If the platform has no runtime options configured at all — an unusual setup state — the steps table still loads normally and the picker falls back to a neutral "inherit" label rather than showing an error.

The relabelled picker appears consistently wherever the steps table is shown: on the full item page, on the overview tab, and immediately after an operator changes a step's runtime.

## Out of Scope

- The agent and model values themselves, and the rules for how they are resolved, are unchanged — this change only makes the already-resolved value visible.
- No change to how steps are executed, retried, or merged.
