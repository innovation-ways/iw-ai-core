"""Unit tests for ``orch.chat.pi.pi_jsonl_reader`` (F-00087).

Invariants tested:
    #1  No Python built-in line iterator in pi_jsonl_reader.py (grep test).
    #2  Unicode separators inside JSON strings do not split records.

Additional cases:
    - Partial record on stream close (remaining buffer flushed).
    - CRLF line endings stripped to LF-only semantics.
    - Multiple records in a single read chunk.
"""

from __future__ import annotations

import asyncio
import inspect
from pathlib import Path

import pytest

from orch.chat.pi.pi_jsonl_reader import aiter_jsonl_lines

# ---------------------------------------------------------------------------
# Helper: build a fake asyncio.StreamReader from bytes
# ---------------------------------------------------------------------------


def _make_stream(data: bytes) -> asyncio.StreamReader:
    """Return a StreamReader pre-loaded with ``data``."""
    reader = asyncio.StreamReader()
    reader.feed_data(data)
    reader.feed_eof()
    return reader


async def _collect(stream: asyncio.StreamReader) -> list[bytes]:
    """Collect all JSONL records from the stream."""
    result: list[bytes] = []
    async for line in aiter_jsonl_lines(stream):
        result.append(line)
    return result


# ---------------------------------------------------------------------------
# Invariant #2 — Unicode separators do not split records
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unicode_separators_in_json_string_do_not_split() -> None:
    """Feeding a JSONL stream with U+2028 / U+2029 inside string values must
    yield exactly one record per LF byte — not split mid-JSON.

    The regression case from R-00072 §2: Python's ``readline`` / ``for line``
    will split on these characters; our LF-only byte reader must not.
    """
    import json

    # Real Unicode bytes — NOT escape sequences.  U+2028 = LS, U+2029 = PS.
    line_sep = " "  # LINE SEPARATOR
    para_sep = " "  # PARAGRAPH SEPARATOR
    # ``json.dumps`` defaults to ensure_ascii=True which escapes U+2028 /
    # U+2029 to ASCII \u2028 / \u2029 BEFORE encoding to bytes — a
    # readline-based reader would pass that input identically.  Pass
    # ensure_ascii=False (and self-verify the raw 3-byte UTF-8 sequences are
    # present in the stream) so the regression case is actually exercised.
    record1 = json.dumps(
        {"text": f"line1{line_sep}line2{para_sep}end"}, ensure_ascii=False
    ).encode()
    record2 = json.dumps({"x": 1}, ensure_ascii=False).encode()

    # Self-verify the test actually exercises the U+2028 / U+2029 regression:
    # the raw UTF-8 byte sequences must be present in the encoded record.
    assert b"\xe2\x80\xa8" in record1, "test bug: U+2028 not encoded as raw bytes"
    assert b"\xe2\x80\xa9" in record1, "test bug: U+2029 not encoded as raw bytes"

    data = record1 + b"\n" + record2 + b"\n"

    stream = _make_stream(data)
    records = await _collect(stream)

    assert len(records) == 2, f"Expected 2 records, got {len(records)}: {records!r}"

    # Both records must parse cleanly
    obj1 = json.loads(records[0])
    obj2 = json.loads(records[1])
    assert line_sep in obj1["text"]
    assert para_sep in obj1["text"]
    assert obj2["x"] == 1


# ---------------------------------------------------------------------------
# Invariant #1 — No built-in line iterator in the module source
# ---------------------------------------------------------------------------


def test_no_builtin_line_iterators_present() -> None:
    """The pi_jsonl_reader module must NOT use readline / 'for line in' / iter(…readline…).

    Uses AST to inspect actual code nodes (not docstrings/comments) so
    that documentation mentioning the forbidden names is allowed.
    """
    import ast

    from orch.chat.pi import pi_jsonl_reader as mod

    src_path = Path(inspect.getfile(mod))
    source = src_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    violations: list[str] = []
    for node in ast.walk(tree):
        # Attribute calls like stream.readline()
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "readline":
                violations.append(
                    f"line {node.lineno}: forbidden .readline() call — "
                    "must use LF-only byte-level scanning"
                )
            # A readline sentinel passed to the iter builtin is forbidden too.
            if isinstance(func, ast.Name) and func.id == "iter" and node.args:
                first_arg = node.args[0]
                if isinstance(first_arg, ast.Attribute) and first_arg.attr == "readline":
                    violations.append(f"line {node.lineno}: forbidden iter(x.readline, ...)")
        # Text-layer stream iteration (a for-loop over the stream variable)
        # calls __iter__ on an io.IOBase — also forbidden.
        if (
            isinstance(node, ast.For)
            and isinstance(node.iter, ast.Name)
            and node.iter.id == "stream"
        ):
            violations.append(
                f"line {node.lineno}: forbidden 'for ... in stream' — "
                "must use LF-only byte-level scanning"
            )

    assert not violations, (
        "pi_jsonl_reader.py must not use Python built-in line iteration:\n  "
        + "\n  ".join(violations)
    )


# ---------------------------------------------------------------------------
# Partial record on stream close
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_partial_record_flushed_on_stream_close() -> None:
    """If the stream closes with a partial (no trailing \\n) record, it is still yielded."""
    import json

    data = b'{"partial":true}'  # no trailing newline
    stream = _make_stream(data)
    records = await _collect(stream)

    assert len(records) == 1
    assert json.loads(records[0]) == {"partial": True}


# ---------------------------------------------------------------------------
# CRLF stripping
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_crlf_line_endings_stripped() -> None:
    """Trailing \\r before \\n must be stripped; the record bytes should contain no \\r."""
    import json

    record = json.dumps({"crlf": True}).encode()
    data = record + b"\r\n"
    stream = _make_stream(data)
    records = await _collect(stream)

    assert len(records) == 1
    assert b"\r" not in records[0]
    assert json.loads(records[0]) == {"crlf": True}


# ---------------------------------------------------------------------------
# Multiple records in one chunk
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_multiple_records_in_single_chunk() -> None:
    """Three back-to-back JSONL records are all yielded."""
    import json

    recs = [{"i": i} for i in range(3)]
    data = b"".join(json.dumps(r).encode() + b"\n" for r in recs)
    stream = _make_stream(data)
    records = await _collect(stream)

    assert len(records) == 3
    for i, raw in enumerate(records):
        assert json.loads(raw) == {"i": i}


# ---------------------------------------------------------------------------
# Empty lines are skipped
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_lines_skipped() -> None:
    """Pure empty lines (bare \\n) must NOT be yielded as records."""
    import json

    data = b'{"a":1}\n\n{"b":2}\n'
    stream = _make_stream(data)
    records = await _collect(stream)

    assert len(records) == 2
    assert json.loads(records[0]) == {"a": 1}
    assert json.loads(records[1]) == {"b": 2}


# ---------------------------------------------------------------------------
# Empty stream — yields nothing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_stream_yields_nothing() -> None:
    """An empty byte stream must yield zero records."""
    stream = _make_stream(b"")
    records = await _collect(stream)
    assert records == [], f"expected no records from empty stream, got {records!r}"


# ---------------------------------------------------------------------------
# Partial record buffered across reads
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_partial_record_buffered_across_reads() -> None:
    """A record split across two feed_data calls must be yielded as one record."""
    import json

    reader = asyncio.StreamReader()
    # Feed partial JSON first …
    reader.feed_data(b'{"a":1')
    # … then complete it and follow with a full second record.
    reader.feed_data(b'}\n{"b":2}\n')
    reader.feed_eof()

    records = await _collect(reader)

    assert len(records) == 2, f"expected 2 records, got {len(records)}: {records!r}"
    assert json.loads(records[0]) == {"a": 1}
    assert json.loads(records[1]) == {"b": 2}


# ---------------------------------------------------------------------------
# Trailing partial at EOF
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_trailing_partial_at_eof() -> None:
    """A partial record with no trailing LF at EOF is yielded as a final record.

    Contract: the implementation flushes the remaining buffer on stream close,
    yielding the partial bytes as the last record.  The test documents and pins
    this behaviour — callers (like the RPC pump) must handle the case where
    the subprocess dies mid-record.
    """
    import json

    # One complete record followed by a partial with no trailing newline.
    data = b'{"first":1}\n{"second_partial":2'
    stream = _make_stream(data)
    records = await _collect(stream)

    # Implementation yields the trailing partial as the last record.
    assert len(records) == 2, (
        f"expected 2 records (one complete + one trailing partial), got {len(records)}: {records!r}"
    )
    assert json.loads(records[0]) == {"first": 1}
    # The trailing partial is yielded verbatim (the JSON is incomplete by
    # design — the contract is "flush remaining buffer at EOF", not "validate
    # JSON").  Callers (PiRpcClient) handle JSONDecodeError gracefully.
    assert records[1] == b'{"second_partial":2'
