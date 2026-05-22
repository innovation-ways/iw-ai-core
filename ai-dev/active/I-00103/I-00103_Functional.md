# I-00103 — Functional Design

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This item adds no migration.

## Why

When the auto-merge resolver attempts to resolve a merge conflict and the underlying language model call fails, the failure is recorded in the events table for operator review. Until now the recorded event only listed which files errored, not why. To find out whether a failure was a timeout, a process-level error, or something else, the operator had to open a server log file and search by timestamp — a ten-minute log-spelunking exercise that should be a one-second glance at the events dashboard. This work closes that gap.

## What Changed (for the User)

- When an auto-merge call fails, the event detail in the dashboard now shows the exact reason for each failed file — for example, "LLM call timed out after 600 s" — in a dedicated section above the raw metadata block.
- The new section is clearly labelled, lists one row per file that errored, and shows the runtime that produced the failure (so the operator can tell at a glance which model misbehaved).
- Events that were recorded before this change continue to render exactly as before; the new section is hidden when no per-file reason is available, so historical rows are not visually disturbed.

## How It Behaves

When the resolver runs and any of its per-file model calls returns an error (timeout, non-zero exit, or an unexpected exception), the resolver now stores the human-readable reason alongside the file path on the resulting event. Error strings are kept short — capped at five hundred characters — so a chatty error message cannot make a single event row excessively large.

When an operator opens the event in the dashboard:

- If the new per-file reason data is present, the modal shows a labelled "Per-file errors" section. Each row contains the file the model was asked to resolve, the literal reason returned by the model runtime, and the runtime label (so it is obvious which model produced which failure).
- If the failure was actually an abstention rather than an error — i.e. the model deliberately refused to guess — the per-file reason section stays empty and the existing "abstained_files" indicator carries the information, exactly as before.
- If the event is older than this change and has no per-file reason data attached, the section is hidden entirely; the rest of the event detail looks identical to before. The dashboard never renders an empty placeholder.

## Out of Scope

- Historical events recorded before this change are not retroactively updated; their reasons remain only in the server log file. Going forward, every new failed event carries the reason directly.
- This change does not alter what counts as a failure, when the resolver retries, or any merge-queue behaviour. It is purely about surfacing existing information that was previously hidden.
