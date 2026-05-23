# CR-00079 — Functional Design

## ⛔ Docker is off-limits

Standard policy. This change touches only written guidance files — no Docker interaction.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This change leaves migrations unchanged — there is no schema change.

## Why

When a piece of development work is planned, it is broken into a sequence of steps that automated agents carry out one at a time. There has been no rule about how much a single step should contain, so a step sometimes bundles many unrelated pieces of work at once. A recent step did exactly that — it packed three test areas, a build-file change, and several documentation updates into one step. The agent ran out of working memory partway through and the step failed. This change adds a clear rule, at the point where work is planned, so steps are kept small and focused from the start.

## What Changed (for the User)

- Anyone planning a new feature, incident, or change request now has explicit guidance that each step should cover one cohesive piece of work, and that work spanning several unrelated areas should be split into several steps.
- A short checklist is provided to catch oversized steps while the plan is still being drafted — for example, flagging when documentation updates are riding along with code changes, or when a single step would need a long list of unrelated sub-tasks.
- Future work plans will tend to have more, smaller steps rather than a few large ones. This makes each step quicker, easier to review, and far less likely to exhaust an agent's working memory.

## How It Behaves

The guidance applies when a work plan is being created. The author checks each proposed step against the checklist: a step that touches one module or one closely-related group of files is fine; a step that mixes unrelated concerns is split before the plan is finalised. The guidance is advisory — it shapes how plans are written. It does not change how steps are executed once a plan exists, it does not change any work item that has already been planned, and it does not change the planning file format. The same rule is recorded as the single source of truth in the shared workflow guidance and is pointed to from the planning templates so it is visible wherever plans are drafted.

## Out of Scope

- Sending steps to a larger or different model — explicitly excluded.
- The runtime-side memory fixes (tracked as a separate incident).
- An automated tool that rejects oversized steps — this change delivers guidance only; mechanical enforcement may be considered later if guidance proves insufficient.
