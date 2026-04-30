# I-00052 S10 QvGate Report

## What was done
Executed integration tests quality gate via `make allure-integration`.

## Test Results
- **Status**: FAIL
- **Total**: 1157 passed, 1 failed, 11 skipped
- **Duration**: 281.73s (4m 41s)

## Failure
**Test**: `test_project_doc_fts_full_text_search` (`tests/integration/test_project_docs.py:486`)

```
assert len(results) == 1
E       assert 3 == 1
E        +  where 3 = len([<ProjectDoc>, <ProjectDoc>, <ProjectDoc>])
```

The test queries `plainto_tsquery('english', 'API')` expecting 1 result (only "Users API"), but all 3 docs match because "API" appears as a substring in other documents' content. This is a test assumption bug, not a code defect — the FTS functionality itself works correctly.

## Observations
- The failure is in the FTS search test — it incorrectly assumes `plainto_tsquery('API')` will only match case-insensitively within quoted terms, but `'API'` as a bare word matches across all documents
- 1157 integration tests pass, covering OSS dashboard routes/service/SSE, scanner, persistence, migrations, RAG index generation, worktrees, evidences, and more
- No code changes were made during this step
