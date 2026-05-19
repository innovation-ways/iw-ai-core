### Item Analysis: I-00095

Bottom line: tighten the S05/S09 functional contract around default-sort UI state and pagination URL preservation, because that mismatch caused the only substantive fix cycle in this incident.

Steps analyzed: 17   Steps with retries: 3 (S09, S10-S15 gate reruns, S16)   Total fix-cycles: 2 (S09, S16)   DB signal: yes

[1] Functional-spec drift on default sort indicator and pagination URL preservation
    Severity: HIGH   Class: design   Frequency: systemic
    Evidence:
      - ai-dev/logs/I-00095_S09_run1.log:551 - "I-00095_Functional.md says default load has no highlighted header, but implementation defaults to sort=created_at, dir=desc, and template marks timestamp as active with chevron."
      - ai-dev/logs/I-00095_S09_fix1.log:380 - "default (no sort in URL) now keeps the backend default ordering but shows no active sort indicator"
      - ai-dev/logs/I-00095_S09_fix1.log:391 - "Made Prev/Next preserve sort only when sort is explicitly in the URL."
    Recommendation: add an explicit invariant block in the functional/design template for "default ordering vs active sort indicator" and for "pagination must preserve sort only when query explicitly contains it".
    Target: ai-dev/templates/Issue_Functional_Template.md
    Pros: prevents review/fix thrash on subtle URL/UI contract semantics; improves reviewer-agent consistency.
    Cons: slightly longer functional docs and stricter wording requirements.
    If we don't: similar sortable-table incidents will keep failing late in final review due to interpretation drift rather than implementation bugs.
    Effort: S (~15-25 lines, 1 file)

Incident-specific signal check:
- Whitelist consistency across aggregator/route/template: stayed consistent; no drift found. Evidence: ai-dev/logs/I-00095_S03_run1.log:377 and ai-dev/logs/I-00095_S09_run3.log:516.
- Verdict NULLS LAST decision: no test pain observed; behavior remained stable. Evidence: ai-dev/logs/I-00095_S01_run1.log:1008.
- S05 pagination-URL preservation: did require a fix cycle and was corrected in S09 fix. Evidence: ai-dev/logs/I-00095_S09_fix1.log:391.
- S16 curl 400 verification vs 422 pitfall: curl verification succeeded with HTTP 400 (not 422). Evidence: ai-dev/logs/I-00095_S16_run3.log:509 and ai-dev/logs/I-00095_S16_run3.log:677.

Coverage notes: read all logs in full (all files under 1 MB); used targeted grep for whitelist/default-sort/pagination/400-vs-422 signals, then anchored findings with line-level evidence.
