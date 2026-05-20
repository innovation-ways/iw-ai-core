"""LF-only byte-level JSONL reader for Pi RPC protocol (F-00087).

WHY THIS MODULE EXISTS
----------------------
Python's built-in line iteration helpers — ``io.IOBase.readline``,
``for line in stream``, ``iter(stream.readline, b"")`` — all split on
Unicode line-separator characters that may appear inside JSON strings:

    U+2028 LINE SEPARATOR      (UTF-8: 0xE2 0x80 0xA8)
    U+2029 PARAGRAPH SEPARATOR (UTF-8: 0xE2 0x80 0xA9)
    U+0085 NEL                 (UTF-8: 0xC2 0x85)

Pi tool output *will* contain such characters in practice (terminal
colour sequences, file contents, etc.).  Any of those bytes inside a
JSON string would cause the built-in helpers to split mid-record,
silently corrupting the protocol.

This module maintains a ``bytearray`` accumulation buffer, reads raw
bytes via ``await stream.read()``, and scans only for ``0x0A`` (LF) as
the record delimiter.  No Python text-layer abstraction touches the
bytes.

References: R-00072 §2, F-00087 §Invariants #1 + #2.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

_CHUNK_SIZE = 8192


async def aiter_jsonl_lines(
    stream: asyncio.StreamReader,
) -> AsyncIterator[bytes]:
    """Yield one complete JSONL record per iteration.

    Splits ONLY on ``b'\\n'`` (0x0A). Strips trailing ``b'\\r'`` if
    present (CRLF line endings). Buffers partial records across read
    calls. Yields each record as raw bytes (caller ``json.loads()``s).

    NEVER uses ``readline()``, ``for line in stream``, or any Python
    helper that splits on Unicode separators inside strings.

    On ``IncompleteReadError`` / stream EOF, yields any remaining
    non-empty buffer as a final record.
    """
    buf = bytearray()
    while True:
        try:
            chunk = await stream.read(_CHUNK_SIZE)
        except asyncio.IncompleteReadError as exc:
            # Drain whatever partial payload the exception carries.
            chunk = exc.partial
        if not chunk:
            # EOF — yield any remaining buffered data as final record.
            if buf:
                yield bytes(buf)
            return

        buf.extend(chunk)

        # Scan the buffer for LF bytes and emit complete records.
        while True:
            lf_pos = buf.find(0x0A)
            if lf_pos == -1:
                break
            record = bytes(buf[:lf_pos])
            # Remove the emitted bytes + the LF delimiter.
            del buf[: lf_pos + 1]
            # Strip trailing CR (CRLF support).
            if record.endswith(b"\r"):
                record = record[:-1]
            # Skip empty records (bare newlines).
            if record:
                yield record
