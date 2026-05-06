# CR-00031 — Functional Design

## Why

In a recent dashboard styling fix, the agent edited the Tailwind source file but the change never reached the served stylesheet. The build command meant to compile Tailwind sources is currently a no-op, so a later step had to discover, mid-fix-cycle, that the right move is to add plain CSS straight to the served stylesheet. We want the next agent to know this on the first try, not the third.

## What Changed (for the User)

For an operator or contributor reading the project's top-level conventions document, there is one new line in the Critical Rules list. It tells future AI agents what to do when the Tailwind build does nothing: skip the build and add ordinary CSS rules straight to the served stylesheet, with a pointer back to the incident that surfaced the issue.

There is no change to any running service, page, or workflow. No commands behave differently. No data moves.

## How It Behaves

When an AI agent picks up future work that involves adding or tweaking styles, it now starts from a documented expectation: if the build target reports it has nothing to do, the agent appends CSS to the served stylesheet directly and continues. This avoids a scenario observed previously where the agent silently produced a change that did not affect the rendered page, the next step's checks failed, and the fix cycle had to rediscover the workaround on its own.

The rule is a guideline for future work; existing pages and styles are unaffected. Anyone who chose to build Tailwind sources by hand can still do so once the underlying toolchain is fixed. This change does not lock anyone into the workaround long-term — it just makes the current reality visible so it does not silently waste cycles.

## Out of Scope

- Repairing the Tailwind toolchain itself (the empty build target, the missing dependencies inside isolated worktrees) is not part of this work. That belongs to a separate platform fix and is tracked alongside the same incident.
- No styling change to any page is included.
