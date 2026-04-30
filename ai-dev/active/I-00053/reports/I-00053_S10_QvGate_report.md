# I-00053 S10 QvGate Report

## Gate

| Field        | Value                     |
|--------------|---------------------------|
| Gate         | integration-tests         |
| Command      | `make allure-integration` |
| Exit code    | 0                         |
| Result       | PASS                      |
| Duration (s) | 351                       |

## Output (tail)

```
orch/rag/qa.py                              334    167    140     22    44%
orch/rag/symbol_gen.py                       72     56     22      0    17%
orch/skills/init_project.py                  83     10     14      4    81%
orch/skills/sync.py                          83     48     30      4    35%
orch/skills/sync_agents.py                   39     11      6      1    64%
orch/staleness/alembic_check.py              95     71     32      0    19%
orch/staleness/config.py                     85     21     32     10    65%
orch/staleness/detection.py                 192    164     64      0    11%
orch/staleness/git_lookup.py                 58     45     16      0    18%
orch/staleness/service.py                    94     63     24      0    26%
orch/test_runner.py                         360    318     70      2    10%
orch/utils/log_capture.py                    33     21      8      1    32%
-------------------------------------------------------------------------------------
TOTAL                                     17958   7070   4834    671    56%

19 files skipped due to complete coverage.
Coverage HTML written to dir tests/output/coverage/htmlcov
Coverage XML written to file tests/output/coverage/coverage.xml
Coverage JSON written to file tests/output/coverage/coverage.json
Required test coverage of 46.0% reached. Total coverage: 56.10%
========== 1155 passed, 18 skipped, 149 warnings in 351.16s (0:05:51) ==========
```

## Verdict

```
pass
```
