# I-00076 — Functional Design

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt. This work does not touch any docker container, volume, or network state.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This work leaves migrations unchanged — no new revision is generated.

## Why

The dashboard lets an operator pick which AI tool and model a work-item step should run on — a small dropdown next to each step that is waiting or has failed. F-00081 added it. In practice the dropdown does not work: choosing an option and then restarting the step launches it on the project's default tool anyway. An operator who deliberately picked "Claude Code + Opus" for a stubborn step kept seeing it run on the default, with no error and no hint that the choice was ignored. This work makes the dropdown actually take effect.

## What Changed (for the User)

- Choosing a tool/model for a waiting or failed step in the item overview now sticks. The next time that step runs — whether the operator restarts it or the orchestrator picks it up — it uses the chosen tool and model.
- The choice is recorded once (previously the dropdown fired its save twice in quick succession, and both saves were empty), so the activity log shows a single, correct "runtime override changed" entry naming the option that was picked.
- Picking the "inherit" entry still does what it always did: it removes any override on that step so it falls back to the item-level or project default.
- Nothing else on the page changes — the step pipeline strip, the restart/skip buttons, and the "apply to remaining steps" control behave exactly as before.

## How It Behaves

When the operator opens the dropdown on a waiting or failed step and selects an option, the dashboard immediately saves that selection against the step and briefly locks the dropdown while the save is in flight, then unlocks it. From that point on, any launch of that step uses the selected tool and model. If the operator instead selects "inherit", the override is cleared and the step goes back to using whatever the item or project specifies. If the dashboard cannot reach the server, the dropdown reverts to its previous state and the operator can retry. The behaviour of steps that are already running, completed, or skipped is unchanged — those rows show the tool/model as read-only, as before.

## Out of Scope

- The dropdown still pre-selects the option that the *last run* of a failed step actually used, rather than the literal "inherit" entry. That is mildly confusing but harmless — making a fresh choice still saves correctly — and is left for a possible future change.
- A couple of unrelated cosmetic tweaks to the same dropdown that were in progress separately (a slightly wider control, showing the full option name instead of just the tool name) are not part of this work.
