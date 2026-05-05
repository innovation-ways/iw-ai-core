# CR-00035 — Functional Design

## ⛔ Docker is off-limits

Standard policy.

## ⛔ Migrations: agents generate, daemon applies

Adds one nullable column on the doc-generation jobs table. Daemon applies on merge.

## Why

Documentation regeneration jobs have never actually produced a document. Every job ever launched died silently and was flipped to failed by a fifteen-minute wall-clock timeout. Operators who open the job page see only failed-timeout with no indication of what the agent tried to do, why nothing happened, or whether the process is even still alive. This change makes a running job visible while it runs, gives operators a structured post-mortem when it ends, and fixes the underlying dispatch bug so jobs actually do work.

## What Changed (for the User)

- The doc-generation job page shows a live-streaming log card while a job is running. New output appears within a couple of seconds of the agent producing it.
- When a job ends — whether it succeeded or failed — the page shows an Execution Report card summarising what happened: how long it took, which skill ran, which sub-commands the agent invoked, whether any document content was actually produced, and a one-line diagnosis when something is obviously off.
- Operators can download the full raw log of any past job from the same page.
- A job whose agent process has died is now flagged as failed within about a minute instead of staying running for a quarter of an hour.
- Doc-generation jobs actually run the doc-generation skill now. Before this change, every job was misrouted to the wrong workflow and the agent gave up before doing any real work.

## How It Behaves

When a job is queued, the page shows queued. As soon as the daemon picks it up and launches the agent, the page flips to running and the live log starts streaming. The operator watches the agent in near real time.

If the agent finishes cleanly, it closes the job itself. The live stream stops, the status badge flips to completed, and the Execution Report card appears with a summary plus a download link for the full log.

If the agent crashes or exits without closing the job, the next polling cycle notices the process is gone and marks the job failed with a clear reason. The Execution Report tells the operator what the agent managed to do before exiting and offers a heuristic diagnosis where possible — for example, flagging cases where the agent ran but never produced any document content.

If the agent simply hangs, the existing fifteen-minute guard still ends the job and the report records that as a timeout outcome.

The raw-log download is available whenever the underlying log file still exists.

## Out of Scope

- Redesigning how documents are generated, what doc types exist, or how editorial guidelines work.
- Backfilling reports for historical failed jobs already in the database — they keep their existing record without the new card.
