# I-00116 — Functional Design

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt. This work does not touch docker.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This work leaves migrations unchanged.

## Why

On 2026-05-27 the operator noticed a work item that had been "executing" for ~2.5 hours without progress. The orchestrator daemon was repeatedly re-launching the same review steps because the reviewer agents were finishing their work, writing the verdict report file, and then exiting without notifying the daemon — so the daemon thought they had crashed and started a fix loop that had nothing to fix. The same loop was free to chew through dozens of expensive agent runs because no overall cap stopped it, and one of the fix agents actually deleted the reproduction tests that had been written earlier. This work makes the orchestrator artifact-aware so it stops manufacturing crashes that never happened, and adds a safety net so any future loop bug self-terminates instead of running for hours.

## What Changed (for the User)

- When a code review finishes and the reviewer writes its verdict file but forgets to tell the orchestrator, the orchestrator now reads the verdict file from disk and treats the review as complete — instead of marking the review as crashed and triggering a fix cycle that has nothing to fix.
- If the same review steps for a single work item keep being re-launched many times (default: more than fifteen), the orchestrator marks the work item as failed with a clear note in the activity log and stops launching new agents. The operator sees the loop end in minutes instead of hours and can decide whether to retry or cancel.
- The review prompt has been clarified so reviewers only look at the files their own step is responsible for, instead of every uncommitted change in the working copy. This stops the "first pass says pass, second pass says fail" flip-flop that triggered the loop in the first place.

## How It Behaves

When a code review finishes, the reviewer is expected to mark the step done with a small command call. If that call is forgotten, the orchestrator now checks whether the reviewer's verdict report file exists on disk and was written after the review started. If yes, the orchestrator parses the verdict (pass or fail with a list of findings) and moves the workflow forward exactly as if the command had been called. If no report exists, the orchestrator behaves the same as before and marks the review as crashed so the operator can investigate.

Separately, the orchestrator now counts how many times any single work item has had its review steps re-launched. If the count crosses the safety threshold, the orchestrator stops launching more agents for that item and records why it stopped. The threshold defaults to fifteen relaunches and can be tuned via configuration.

For the third change, the review prompt explicitly tells the reviewer which files belong to the step under review, so the reviewer no longer reads changes that another step produced and mistakenly attributes them to the wrong step.

## Out of Scope

- This work does not change anything about how reviewers reach their verdict; the contract for what a "pass" or "fail" means is unchanged.
- This work does not retroactively recover any work items that already failed due to the loop pattern; only items that hit the pattern after this fix ships benefit from the new behaviour.
