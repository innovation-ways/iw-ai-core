# CR-00033 — Functional Design

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. This item adds no migrations and changes no existing migration.)

## Why

The IW AI Core dashboard is styled with Tailwind, primarily through a CDN. A
local Tailwind CLI also exists for compiling a static stylesheet, but inside
the agent worktrees that the daemon spins up, the CLI sometimes cannot run —
its dependencies are not always fully installed. A recent incident showed an
agent burning a fix-cycle to re-discover this and find the workaround. The
workaround is simple and already used by humans on the team, but it is not
written down anywhere a future agent or new operator would find it.

## What Changed (for the User)

For readers of the Tech Stack documentation, the section that describes how
the dashboard is styled now includes an explicit Tailwind CLI fallback
strategy. They will see:

- An honest description of when the local Tailwind CLI is reliable and when
  it is not, including the no-op build target.
- A clear rule for what to do instead: write plain CSS into the served
  stylesheet directly, since it ships as-is.
- A short note in the decisions log so the trade-off is visible alongside the
  original decision to use Tailwind via the CDN.

There is no behavioural change to the running dashboard, no UI change, and no
change to how styles are loaded at request time. Existing pages render
identically.

## How It Behaves

Day-to-day styling continues to work the way it does today: most pages reach
for Tailwind utility classes that come from the CDN, and the dashboard serves
its existing stylesheet without a build step. Nothing about that flow is
altered by this change.

The new behaviour is purely informational. When someone — an agent in a
fix-cycle, a new contributor, or an operator triaging a styling task — reads
the Tech Stack doc, they now see, in one place, the rule for adding new
styles inside an agent worktree. They learn that running the existing build
target does nothing today, that compiling Tailwind locally can fail because
of missing local dependencies, and that the supported answer is to write
plain CSS into the served stylesheet. The old prose that hinted local
compilation was a routine production path is corrected so the document does
not contradict the new subsection.

## Out of Scope

- Changing the build target itself, installing missing dependencies, or making
  the local Tailwind compiler reliable.
- Adding a Critical Rule about the fallback to the project-level agent guide.
  That is a separate decision, not included here.
