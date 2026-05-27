### Item Analysis: I-00115

Bottom line: eliminate the recurring `make test-unit` `ModuleNotFoundError: anthropic` gate break by making that dependency reliably available (or test-import-guarded) in the standard project test environment.

Steps analyzed: 14   Steps with retries: 2   Total fix-cycles: 5   DB signal: yes

[1] Repeated S05 gate failure on missing `anthropic` dependency
    Severity: HIGH   Class: environment   Frequency: systemic
    Evidence:
      - ai-dev/logs/I-00115_S05_run1.log:9 — "make test-unit ❌ (**ModuleNotFoundError: anthropic** in unit test collection)"
      - ai-dev/logs/I-00115_S05_run3.log:8 — "make test-unit ❌ (`ModuleNotFoundError: No module named 'anthropic'` during collection)"
      - ai-dev/logs/I-00115_S05_run5.log:13 — "`make test-unit` ❌ failed (`ModuleNotFoundError: No module named 'anthropic'`)"
    Recommendation: Ensure the test environment always provides `anthropic` (or guard that test module import so unrelated items are not blocked by optional-provider availability).
    Target: pyproject.toml
    Pros: Prevents repeated false-negative final-review failures and fix-cycle churn on unrelated items.
    Cons: Adds/locks one dependency (or requires small test harness adjustment).
    If we don't: Final review can keep failing for unrelated scope changes, causing avoidable retries and queue delay.
    Effort: S   (~1 file)
