# F-00085 — Functional Design

## Why

The automated merge-conflict resolver shipped last week but runs invisibly. An operator cannot see whether it is enabled for a project, what model it uses, what conflicts it has handled, or whether its proposals were sensible — today the only path is to edit a config file, reload the daemon, and query the database by hand. To make the audit window sustainable, and to let operators opt projects in independently, we need both a visibility surface and a control surface on the dashboard.

## What Changed (for the User)

- A new **Auto-Merge** project page sits alongside Queue, History, and Batches.
- A small status chip appears in the header of every per-project page when the resolver is enabled, showing phase, model, attempts, and a health indicator. Clicking it jumps to the page.
- The page lists every interaction the resolver had with a merge conflict — files involved, proposal text, skipped reasons, failures.
- For each successful proposal the operator opens a side-by-side diff of proposal vs current main, then marks it correct, wrong, partial, or pending, with an optional note.
- Verdict counts roll up into 7-day and 30-day accuracy windows; token-cost rollups show spend at the chosen model.
- A refuse-list panel groups skipped conflicts by reason, confirming the safety net is firing where expected.
- A health indicator reflects a background probe the daemon runs every five minutes — a one-word OK round-trip — so a misconfiguration surfaces before the next real conflict.
- A **Settings** panel lets the operator enable or disable the resolver per project and pick its model. "Use global default" preserves today's behaviour.

## How It Behaves

Opening the page on a project with no events shows a friendly empty state. As real conflicts happen the activity log fills; clicking a row reveals the proposal and the operator records a verdict in one click. Rollups refresh on the next load.

The Settings panel is the operator's control. Phase off means the resolver does nothing — no attempts, no probes, chip gone. Phase dry-run evaluates conflicts and records what it would have proposed, without modifying any branch. The runtime picker lists every enabled model from the platform's catalog; the choice takes effect at the next merge and is audited in the activity log.

If the picked runtime is later disabled, the resolver falls back to the global default and the chip annotates the situation. Phases two and three are reserved for future work and cannot be selected here. The health probe runs in the background and never blocks a merge; if it stops succeeding the chip turns yellow, then red once the failure rate crosses the threshold, while the page keeps showing the most recent good state alongside the latest probe error.

## Out of Scope

- The resolver still does not apply any proposal automatically — that ships once the audit proves it is right often enough.
- Alerts that leave the dashboard (email, chat, webhooks) are not part of this feature.
- Verdict capture is operator-judged; no automated comparison between proposed and merged versions yet.
