# F-00064 S06 — Code Review: Tests (S05)

## Summary

Reviewed unit test implementation from S05 (tests-impl). Tests are well-structured, correctly mocked, and all pass.

## Files Reviewed

- `tests/unit/rag/test_diagram_render.py` — 14 tests (pre-existing + S05 additions)
- `tests/unit/rag/test_mapgen_mermaid.py` — 3 tests (new, S05)

## Checklist Verification

### Coverage ✅
- All 8 render tests present: binary missing, timeout, nonzero exit, unexpected exception (mermaid); binary missing, timeout, nonzero exit (d2); unknown type dispatcher; check_diagram_tools (both absent, mermaid available, d2 available, both available)
- All 3 `_build_mermaid` ELK injection tests present: ELK injected when omitted, ELK not duplicated, fallback DSL when no fenced block

### Test Quality ✅
- No test connects to live DB (port 5433) or live Ollama — `conftest.py` arms the live-DB guard with env hijack to port 1
- All subprocess calls monkeypatched via `unittest.mock.patch` — no real subprocess execution
- Each test has a single, clear assertion focus
- Invariant verified: `render_mermaid` and `render_d2` never raise (confirmed by `assert result is None` across all error-path tests)

### Correctness ✅
- `test_returns_none_when_binary_missing` correctly mocks both `shutil.which` returning `None` AND `Path` returning a mock path where `.exists()` returns `False`
- Timeout test correctly simulates `subprocess.TimeoutExpired`
- ELK deduplication test uses `result.count("layout: elk") == 1` to verify exactly one occurrence

## Quality Gates

| Gate | Result |
|------|--------|
| `make lint` | ✅ All checks passed |
| `make test-unit` (F-00064 tests) | ✅ 17 passed, 0 failed |

## Findings

- `test_mapgen_mermaid.py` uses `@pytest.fixture` with a `mock_config` fixture scoped per-class; this is appropriate since each test constructs a fresh `MapGenerator`.
- The `_build_mermaid` method is `@staticmethod` but internally constructs an `Ollama` instance — patching `orch.rag.mapgen.Ollama` at the class level is the correct approach.
- The fallback DSL test correctly uses `"graph TD" in result` rather than `result.startswith()` because ELK frontmatter is prepended before the fallback DSL.

## Conclusion

**Approved**: Yes. Tests are correct, complete, and follow project conventions.

