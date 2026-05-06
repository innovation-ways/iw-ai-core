# I-00071 — Functional Design

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This work item adds no migrations.

## Why

When several work items are approved together in a batch, the platform tries to run them in parallel — but recently a perfectly safe combination of items was held back for over an hour, with the system repeatedly logging that they "overlapped" with another running item. They did not. The cross-batch safety check that decides whether two items touch the same area was being too strict for two reasons that combine to produce false alarms. The fix removes those false alarms so independent items can run in parallel as designed.

## What Changed (for the User)

- Items whose only relationship is "two test files happen to live under the same tests folder" are no longer held back from running in parallel.
- Items whose paths were written with markdown formatting in the design document are now stored cleanly, so the safety check can compare them correctly.
- The dashboard event stream stops showing recurring "held for scope" notices for items that should never have been held in the first place.
- Throughput on multi-item batches improves: items that were previously serialised by accident now launch in parallel as the batch was designed to do.

## How It Behaves

When the daemon evaluates whether to launch a pending item, it compares the item's declared file scope against any item already in flight in the same project. Two checks were producing false matches: the parser kept formatting characters from the design document inside each scope entry, and the test-file recogniser missed entries written with relative folder names. After the fix, the parser produces clean entries, and the recogniser correctly identifies test-only scopes regardless of how the path is written.

The user-visible effect is straightforward: when two items honestly share a code area, they still serialise (correct behaviour); when they only appear to share an area because of the two issues above, they now launch in parallel.

The fix is contained to a single check inside the orchestration daemon and the design-document parser. It does not change how items are designed, approved, or merged, and it does not alter the batch planner or any user-facing dashboard page.

## Out of Scope

- Backfilling existing rows already stored with formatting characters. Those items finish their current batch and the next time their successors are registered the parser handles them cleanly.
- Any change to the batch planner's design-time grouping logic.
