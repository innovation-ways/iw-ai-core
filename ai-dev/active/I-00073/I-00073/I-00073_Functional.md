# I-00073 — Functional Design

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This item adds no migration — the whole point is to make the platform tolerate the natural gap between an in-flight feature's schema changes and the moment the orchestration database actually receives them.

## Why

When a new feature adds columns to one of the platform's own bookkeeping tables, the agent doing the work cannot tell the platform it finished. The agent runs to completion, all quality gates pass, but the call that records "done" crashes against the live database because that database has not yet received the new columns the agent just declared. The system then assumes the agent died, restarts the same step, hits the same wall, and eventually stalls. A real recent feature hit exactly this trap and required an operator to manually unblock it. The goal is to remove that trap so future schema-evolving work flows through the pipeline without operator intervention.

## What Changed (for the User)

- Agents reporting completion of a step never again crash with a "missing column" error caused by their own in-flight schema work.
- Workflows that add columns to platform bookkeeping tables advance through the pipeline by themselves; no operator step required.
- Operators no longer have to apply migrations out of band to rescue a stuck workflow.
- The dashboard no longer shows the misleading "Process exited without reporting completion" status when the only thing that actually went wrong was a transient schema drift.

## How It Behaves

When an agent finishes its work and tells the platform "this step is done", the platform records the completion using only the small, pinned set of fields it has always cared about. Any extra fields the in-flight feature added to the same table are simply ignored on this read path. Reporting succeeds, the step advances, and the workflow proceeds to the next agent. The behaviour is identical for "this step failed", "restart this step", "skip this step", "kill this step", and "show me the status of this item". The pinned-set rule applies only to the agent-facing commands; everywhere else, including the daemon's own bookkeeping, behaviour is unchanged.

The first sign that a future regression has slipped in will be the regression test, which simulates the exact drift scenario and runs on every build.

## Out of Scope

- Changing how migrations are applied or who applies them — the constraint that agents write migrations and the daemon applies them at merge time stays exactly as it is.
- Changing daemon-side queries — the daemon already runs from a tree where database and code are in sync, so there is no drift to defend against.
