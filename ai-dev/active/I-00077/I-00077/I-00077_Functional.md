# I-00077 — Functional Design

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This work adds no migrations.

## Why

A user asked the platform to regenerate a documentation diagram. The job failed almost immediately, but the Docs page gave no sign of it — the user only found out by chance on the background-jobs view. Two things were wrong: the document type involved had no editorial style guide attached, and the generation agent treated that absence as a reason to give up rather than fall back to the platform's built-in baseline guidance; and even once the job had failed, the Docs page never told anyone. This work makes generation resilient to a missing per-type guide and makes failures impossible to miss.

## What Changed (for the User)

- Regenerating a document that has no per-type editorial guide no longer fails for that reason — the generator uses the platform's global baseline editorial guidance instead, the same way it always could for other document types.
- When a documentation generation job fails, the Docs catalogue page now shows it: the failed item stays visible in the page's activity strip for a few minutes with the error message and a button to dismiss it, and a notification appears with the failure reason. You no longer have to open the background-jobs view to learn that a regeneration failed.
- The single-document page already showed a failure banner; the catalogue (all-documents) page now behaves consistently.

## How It Behaves

When a generation job is created, the platform attaches whatever editorial guidance applies — a guide specific to that one document if one exists, otherwise a guide for that document's type, otherwise the global baseline guide. Previously the chain stopped one step short and attached nothing when a type-specific guide was missing; now it continues to the baseline. The generation agent is also told plainly that an empty editorial context is normal and that it should proceed using its own built-in guidelines, only abandoning a job if it genuinely cannot read the job's details.

On the Docs catalogue page, the activity strip at the top now lists both jobs that are still running and jobs that finished in failure within roughly the last ten minutes. A failed entry is styled to stand out, names the error, and offers a dismiss control. A failure notification is also raised on that page. Successful jobs continue to behave as before — they disappear from the strip when done and the affected document refreshes.

## Out of Scope

- No change to how generation jobs are scheduled, retried, or how long they may run.
- No new editorial guides are authored; only the fallback order changes. (Separately, the wording change to the generation skill will be copied into the other repositories that carry the same skill — that is an operational follow-up, not part of this change.)
