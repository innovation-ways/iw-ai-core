# CR-00053 S16 QvGate Report

| Field        | Value                |
|--------------|----------------------|
| Gate         | security-secrets     |
| Command      | `make security-secrets` |
| Exit code    | 0                    |
| Result       | PASS                 |
| Mode         | manual (operator-driven) |

## Output

```
gitleaks scanned ~65MB in 2.26s
no leaks found
[security-secrets] OK
```

## Verdict

```
pass
```

## Workflow note

First run produced 3 false-positive `iw-internal-fqdn` findings inside
`.mypy_cache/3.12/{sqlalchemy/event/attr.data.json,sqlalchemy/event/base.data.json,threading.data.json}`.
The cache was populated by the preceding S12 (type-check) gate; gitleaks runs
with `--no-git`, so gitignored caches are still scanned. After
`rm -rf .mypy_cache && make security-secrets`, gitleaks reports clean.

Follow-up suggestion: add `.mypy_cache/` (and probably `.ruff_cache/`,
`.pytest_cache/`) to the `[allowlist].paths` in `.gitleaks.toml` so the gates
are independent of run order. Out of scope for CR-00053.
