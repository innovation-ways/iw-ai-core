# CR-00054 S11 QvGate Report

## Gate

| Field        | Value           |
|--------------|-----------------|
| Gate         | assertions      |
| Command      | `make test-assertions` |
| Exit code    | 0             |
| Result       | PASS         |
| Duration (s) | 1       |

## Output (tail)

```
uv run python scripts/check_test_assertions.py --baseline tests/assertion_free_baseline.txt tests/
No new assertion-scanner violations (441 files scanned).
```

## Verdict

```
pass
```
