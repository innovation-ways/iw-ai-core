# I-00112 — Functional Design

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt. This work does not touch docker.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This work adds one new migration that appends nullable columns to the keep-alive run history table; existing rows are unaffected.

## Why

The Keep-Alive Scheduler's only job is to keep a model's 5-hour usage window warm by sending a tiny message on a schedule. On 2026-05-25, the operator noticed the dashboard's Recent Executions table claimed every overnight fire was a success, yet the claude.ai usage page showed no messages and the 5-hour window was never anchored. The scheduler was treating "the command exited cleanly" as success without checking whether a message was actually sent — so a silent no-op looked identical to a real fire. This work makes those silent no-ops visible and prevents them from being labelled successful.

## What Changed (for the User)

- The Recent Executions table on the Keep-Alive Scheduler page now has two extra columns: Elapsed (how long the fire took) and Output (the first part of what the model replied). Rows captured before this fix show "—" in those columns.
- A fire that "looked clean" but did not actually reach Anthropic — for example, the command exited quickly with no reply — is now labelled "Failed" instead of "Success". The operator no longer has to cross-check claude.ai/usage to confirm a fire really anchored the window.
- Each row now carries enough information to audit a suspicious fire in seconds, without leaving the page.

## How It Behaves

When a scheduled slot fires, the scheduler now records four extra facts: the command's exit code, how long it took, what the model wrote back, and any error text. A fire is only labelled "Success" when all three hold: the command exited cleanly, the model actually wrote something back, and the round-trip took at least half a second. Anything else — an instant exit, an empty reply, a non-zero exit code — is labelled "Failed" with the captured detail stored alongside, so the operator can see *why* it was rejected. The single retry the scheduler already does on a failed first attempt is unchanged; the second attempt is judged against the same three-part contract.

The Recent Executions table reflects this immediately: Success rows show a non-empty Elapsed and a snippet of the model's reply; Failed rows show the captured stderr or rejection reason in the existing error column. Historical rows from before this change show "—" in the new columns because their detail was never captured — they are not retroactively re-classified.

## Out of Scope

- This work does not change which model the scheduler fires against, the slot schedule, or the retry policy — only how a fire is judged successful and how much detail is recorded about each fire.
- This work does not back-fill the new columns for rows that already exist; those rows keep their original status and display "—" in the new columns.
