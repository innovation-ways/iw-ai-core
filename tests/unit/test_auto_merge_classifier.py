"""Unit tests for orch.daemon.auto_merge — classify_conflicts().

Covers: all skip reasons, allowlist filtering, binary detection, hunk size,
too-many-files, determinism, and refuse-list precedence over allowlist.
"""

from __future__ import annotations

from pathlib import Path


def _make_config(
    allowlist: list[str] | None = None,
    refuselist: list[str] | None = None,
    max_hunk_lines: int = 80,
    max_files: int = 5,
    max_file_size: int = 256000,
):
    """Build a minimal AutoMergeConfig for tests."""
    from orch.daemon.auto_merge import AutoMergeConfig

    return AutoMergeConfig(
        phase=0,
        runtime_option_id=None,
        allowlist_patterns=tuple(allowlist or ["tests/**/*.py", "docs/**/*.md"]),
        refuselist_patterns=tuple(refuselist or ["orch/db/migrations/versions/*.py", ".env"]),
        max_conflict_hunk_lines=max_hunk_lines,
        max_conflicted_files_per_merge=max_files,
        max_file_size_bytes=max_file_size,
        max_event_metadata_bytes=262144,
        llm_call_timeout_seconds=120,
    )


def _write_conflict_file(path: Path, content: str | None = None) -> None:
    """Write a file with a minimal conflict marker if no content given."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content or "<<<<<<< HEAD\nA\n=======\nB\n>>>>>>> branch\n")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_all_files_allowlisted(tmp_path: Path) -> None:
    """3 conflict files in tests/ → eligible, no skip."""
    from orch.daemon.auto_merge import classify_conflicts

    files = []
    for i in range(3):
        f = tmp_path / "tests" / "unit" / f"test_mod_{i}.py"
        _write_conflict_file(f)
        files.append(f"tests/unit/test_mod_{i}.py")

    config = _make_config(allowlist=["tests/**/*.py"], refuselist=[])

    result = classify_conflicts(worktree_path=tmp_path, conflict_files=files, config=config)

    assert result.skipped_reason is None
    assert set(result.eligible_files) == set(files)
    assert len(result.refuse_files) == 0
    assert len(result.binary_files) == 0
    assert len(result.oversized_files) == 0
    assert len(result.oversized_hunks) == 0


def test_one_file_refuse_listed(tmp_path: Path) -> None:
    """1 file in orch/db/migrations/versions/ → skipped_reason='refuse_list'."""
    from orch.daemon.auto_merge import classify_conflicts

    migration_file = tmp_path / "orch" / "db" / "migrations" / "versions" / "d1e2f3gpt53c_test.py"
    _write_conflict_file(migration_file)

    config = _make_config(
        allowlist=["tests/**/*.py"],
        refuselist=["orch/db/migrations/versions/*.py"],
    )

    result = classify_conflicts(
        worktree_path=tmp_path,
        conflict_files=["orch/db/migrations/versions/d1e2f3gpt53c_test.py"],
        config=config,
    )

    assert result.skipped_reason == "refuse_list"
    assert "orch/db/migrations/versions/d1e2f3gpt53c_test.py" in result.refuse_files
    assert len(result.eligible_files) == 0


def test_mixed_refuse_and_allow(tmp_path: Path) -> None:
    """Mix of refuse-listed and allowlisted files → skipped_reason='refuse_list' (refuse wins)."""
    from orch.daemon.auto_merge import classify_conflicts

    test_file = tmp_path / "tests" / "test_something.py"
    _write_conflict_file(test_file)

    migration_file = tmp_path / "orch" / "db" / "migrations" / "versions" / "abc123_test.py"
    _write_conflict_file(migration_file)

    config = _make_config(
        allowlist=["tests/**/*.py"],
        refuselist=["orch/db/migrations/versions/*.py"],
    )

    result = classify_conflicts(
        worktree_path=tmp_path,
        conflict_files=[
            "tests/test_something.py",
            "orch/db/migrations/versions/abc123_test.py",
        ],
        config=config,
    )

    # Refuse-list wins regardless of allowlist match
    assert result.skipped_reason == "refuse_list"
    assert "orch/db/migrations/versions/abc123_test.py" in result.refuse_files
    assert len(result.eligible_files) == 0


def test_binary_file_detected_by_content(tmp_path: Path) -> None:
    """File with \\x00 in first 8KB → skipped_reason='binary'."""
    from orch.daemon.auto_merge import classify_conflicts

    # Create a file that matches the allowlist but contains binary content
    conflict_file = tmp_path / "tests" / "fixtures" / "image.bin"
    conflict_file.parent.mkdir(parents=True, exist_ok=True)
    conflict_file.write_bytes(b"\x00\x01\x02\x03 binary content")

    config = _make_config(
        allowlist=["tests/**/*"],
        refuselist=[],
    )

    result = classify_conflicts(
        worktree_path=tmp_path,
        conflict_files=["tests/fixtures/image.bin"],
        config=config,
    )

    assert result.skipped_reason == "binary"
    assert "tests/fixtures/image.bin" in result.binary_files
    assert len(result.eligible_files) == 0


def test_binary_file_detected_by_suffix(tmp_path: Path) -> None:
    """.png file → skipped_reason='binary' (suffix detection, not null-byte check)."""
    from orch.daemon.auto_merge import classify_conflicts

    # PNG file in tests/ — would otherwise be allowlisted by tests/**/*
    # but suffix wins
    png_file = tmp_path / "tests" / "foo.png"
    png_file.parent.mkdir(parents=True, exist_ok=True)
    # Write ASCII content (no null bytes) — suffix-only detection must fire
    png_file.write_bytes(b"not actually binary but has .png suffix")

    config = _make_config(
        allowlist=["tests/**/*"],
        refuselist=[],  # no refuselist — so only binary detection fires
    )

    result = classify_conflicts(
        worktree_path=tmp_path,
        conflict_files=["tests/foo.png"],
        config=config,
    )

    assert result.skipped_reason == "binary"
    assert "tests/foo.png" in result.binary_files


def test_oversized_file(tmp_path: Path) -> None:
    """File > max_file_size_bytes → skipped_reason='file_too_large'."""
    from orch.daemon.auto_merge import classify_conflicts

    conflict_file = tmp_path / "docs" / "huge.md"
    conflict_file.parent.mkdir(parents=True, exist_ok=True)
    # Write 1001 bytes (exceeds limit of 500)
    conflict_file.write_text("x" * 1001 + "\n<<<<<<< HEAD\nA\n=======\nB\n>>>>>>> branch\n")

    config = _make_config(
        allowlist=["docs/**/*.md"],
        refuselist=[],
        max_file_size=500,
    )

    result = classify_conflicts(
        worktree_path=tmp_path,
        conflict_files=["docs/huge.md"],
        config=config,
    )

    assert result.skipped_reason == "file_too_large"
    assert "docs/huge.md" in result.oversized_files
    assert len(result.eligible_files) == 0


def test_oversized_hunk(tmp_path: Path) -> None:
    """Conflict hunk > 80 lines → skipped_reason='hunk_too_large'."""
    from orch.daemon.auto_merge import classify_conflicts

    # Build a conflict block with >80 lines between markers
    lines = ["<<<<<<< HEAD\n"]
    lines += [f"line {i}\n" for i in range(50)]
    lines += ["=======\n"]
    lines += [f"other {i}\n" for i in range(50)]
    lines += [">>>>>>> branch\n"]

    conflict_file = tmp_path / "docs" / "big_conflict.md"
    conflict_file.parent.mkdir(parents=True, exist_ok=True)
    conflict_file.write_text("".join(lines))

    config = _make_config(
        allowlist=["docs/**/*.md"],
        refuselist=[],
        max_hunk_lines=80,
    )

    result = classify_conflicts(
        worktree_path=tmp_path,
        conflict_files=["docs/big_conflict.md"],
        config=config,
    )

    assert result.skipped_reason == "hunk_too_large"
    assert "docs/big_conflict.md" in result.oversized_hunks
    assert len(result.eligible_files) == 0


def test_too_many_files(tmp_path: Path) -> None:
    """More than max_conflicted_files_per_merge → skipped_reason='too_many_files'."""
    from orch.daemon.auto_merge import classify_conflicts

    # Create 6 files with small conflict hunks (limit is 5)
    conflict_files = []
    for i in range(6):
        f = tmp_path / "tests" / f"test_mod_{i}.py"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(f"<<<<<<< HEAD\nA{i}\n=======\nB{i}\n>>>>>>> branch\n")
        conflict_files.append(f"tests/test_mod_{i}.py")

    config = _make_config(
        allowlist=["tests/**/*.py"],
        refuselist=[],
        max_files=5,
    )

    result = classify_conflicts(
        worktree_path=tmp_path,
        conflict_files=conflict_files,
        config=config,
    )

    assert result.skipped_reason == "too_many_files"
    assert len(result.eligible_files) == 0


def test_non_allowlisted_file(tmp_path: Path) -> None:
    """dashboard/static/foo.js conflict → skipped_reason='not_allowlisted'."""
    from orch.daemon.auto_merge import classify_conflicts

    js_file = tmp_path / "dashboard" / "static" / "foo.js"
    _write_conflict_file(js_file)

    config = _make_config(
        allowlist=["tests/**/*.py", "docs/**/*.md"],
        refuselist=[],
    )

    result = classify_conflicts(
        worktree_path=tmp_path,
        conflict_files=["dashboard/static/foo.js"],
        config=config,
    )

    assert result.skipped_reason == "not_allowlisted"
    assert len(result.eligible_files) == 0


def test_decision_tree_determinism_invariant_6(tmp_path: Path) -> None:
    """Same inputs across 10 invocations produce identical ClassificationResult."""
    from orch.daemon.auto_merge import classify_conflicts

    for i in range(3):
        f = tmp_path / "tests" / "unit" / f"test_det_{i}.py"
        _write_conflict_file(f)

    files = [f"tests/unit/test_det_{i}.py" for i in range(3)]
    config = _make_config(allowlist=["tests/**/*.py"], refuselist=[])

    results = [
        classify_conflicts(worktree_path=tmp_path, conflict_files=files, config=config)
        for _ in range(10)
    ]

    first = results[0]
    for r in results[1:]:
        assert r.skipped_reason == first.skipped_reason
        assert r.eligible_files == first.eligible_files
        assert r.refuse_files == first.refuse_files
        assert r.binary_files == first.binary_files
        assert r.oversized_files == first.oversized_files
        assert r.oversized_hunks == first.oversized_hunks


def test_refuse_list_precedence(tmp_path: Path) -> None:
    """Binary file in tests/ (tests/foo.png) is classified as refuse via suffix, NOT eligible."""
    from orch.daemon.auto_merge import classify_conflicts

    # tests/foo.png is in the allowlist pattern tests/**/* but is also in the
    # refuselist pattern *.png — refuse-list must win.
    png_file = tmp_path / "tests" / "foo.png"
    png_file.parent.mkdir(parents=True, exist_ok=True)
    png_file.write_bytes(b"PNG data here")

    config = _make_config(
        allowlist=["tests/**/*"],
        refuselist=["*.png"],
    )

    result = classify_conflicts(
        worktree_path=tmp_path,
        conflict_files=["tests/foo.png"],
        config=config,
    )

    # Refuse-list check runs first — refuse_list wins, not binary
    assert result.skipped_reason == "refuse_list"
    assert "tests/foo.png" in result.refuse_files
    assert len(result.eligible_files) == 0


def test_refuse_list_takes_precedence(tmp_path: Path) -> None:
    """A file matching the refuse list causes skipped_reason='refuse_list'."""
    from orch.daemon.auto_merge import classify_conflicts

    conflict_file = tmp_path / "orch" / "db" / "migrations" / "versions" / "abc.py"
    conflict_file.parent.mkdir(parents=True, exist_ok=True)
    conflict_file.write_text("# migration\n<<<<<<< HEAD\nA\n=======\nB\n>>>>>>> branch\n")

    config = _make_config(
        allowlist=["tests/**/*.py"],
        refuselist=["orch/db/migrations/versions/*.py"],
    )

    result = classify_conflicts(
        worktree_path=tmp_path,
        conflict_files=["orch/db/migrations/versions/abc.py"],
        config=config,
    )

    assert result.skipped_reason == "refuse_list"
    assert "orch/db/migrations/versions/abc.py" in result.refuse_files


def test_allowlist_filters_non_matching_file(tmp_path: Path) -> None:
    """A file that is not in the allowlist causes skipped_reason='not_allowlisted'."""
    from orch.daemon.auto_merge import classify_conflicts

    conflict_file = tmp_path / "orch" / "daemon" / "some_module.py"
    conflict_file.parent.mkdir(parents=True, exist_ok=True)
    conflict_file.write_text("code\n<<<<<<< HEAD\nA\n=======\nB\n>>>>>>> branch\n")

    config = _make_config(
        allowlist=["tests/**/*.py", "docs/**/*.md"],
        refuselist=[],
    )

    result = classify_conflicts(
        worktree_path=tmp_path,
        conflict_files=["orch/daemon/some_module.py"],
        config=config,
    )

    assert result.skipped_reason == "not_allowlisted"


def test_binary_detection_causes_skip(tmp_path: Path) -> None:
    """A binary file (contains null bytes) causes skipped_reason='binary'."""
    from orch.daemon.auto_merge import classify_conflicts

    conflict_file = tmp_path / "tests" / "fixtures" / "image.bin"
    conflict_file.parent.mkdir(parents=True, exist_ok=True)
    conflict_file.write_bytes(b"\x00\x01\x02\x03 binary content")

    config = _make_config(
        allowlist=["tests/**/*"],
        refuselist=[],
    )

    result = classify_conflicts(
        worktree_path=tmp_path,
        conflict_files=["tests/fixtures/image.bin"],
        config=config,
    )

    assert result.skipped_reason == "binary"
    assert "tests/fixtures/image.bin" in result.binary_files


def test_hunk_size_limit_causes_skip(tmp_path: Path) -> None:
    """Conflict hunk larger than max_conflict_hunk_lines causes skipped_reason='hunk_too_large'."""
    from orch.daemon.auto_merge import classify_conflicts

    lines = ["<<<<<<< HEAD\n"]
    lines += [f"line {i}\n" for i in range(50)]
    lines += ["=======\n"]
    lines += [f"other {i}\n" for i in range(50)]
    lines += [">>>>>>> branch\n"]

    conflict_file = tmp_path / "docs" / "big_conflict.md"
    conflict_file.parent.mkdir(parents=True, exist_ok=True)
    conflict_file.write_text("".join(lines))

    config = _make_config(
        allowlist=["docs/**/*.md"],
        refuselist=[],
        max_hunk_lines=80,
    )

    result = classify_conflicts(
        worktree_path=tmp_path,
        conflict_files=["docs/big_conflict.md"],
        config=config,
    )

    assert result.skipped_reason == "hunk_too_large"
    assert "docs/big_conflict.md" in result.oversized_hunks


def test_too_many_files_causes_skip(tmp_path: Path) -> None:
    """More conflict files than max_conflicted_files_per_merge → skipped_reason='too_many_files'."""
    from orch.daemon.auto_merge import classify_conflicts

    conflict_files = []
    for i in range(6):
        f = tmp_path / "tests" / f"test_mod_{i}.py"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(f"<<<<<<< HEAD\nA{i}\n=======\nB{i}\n>>>>>>> branch\n")
        conflict_files.append(f"tests/test_mod_{i}.py")

    config = _make_config(
        allowlist=["tests/**/*.py"],
        refuselist=[],
        max_files=5,
    )

    result = classify_conflicts(
        worktree_path=tmp_path,
        conflict_files=conflict_files,
        config=config,
    )

    assert result.skipped_reason == "too_many_files"


def test_eligible_files_all_pass(tmp_path: Path) -> None:
    """Files that pass all checks are returned as eligible with skipped_reason=None."""
    from orch.daemon.auto_merge import classify_conflicts

    for i in range(2):
        f = tmp_path / "tests" / "unit" / f"test_something_{i}.py"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(f"<<<<<<< HEAD\nA{i}\n=======\nB{i}\n>>>>>>> branch\n")

    config = _make_config(
        allowlist=["tests/**/*.py"],
        refuselist=[],
        max_hunk_lines=80,
        max_files=5,
    )

    result = classify_conflicts(
        worktree_path=tmp_path,
        conflict_files=["tests/unit/test_something_0.py", "tests/unit/test_something_1.py"],
        config=config,
    )

    assert result.skipped_reason is None
    assert set(result.eligible_files) == {
        "tests/unit/test_something_0.py",
        "tests/unit/test_something_1.py",
    }
    assert len(result.refuse_files) == 0
    assert len(result.binary_files) == 0
    assert len(result.oversized_hunks) == 0


def test_file_too_large_causes_skip(tmp_path: Path) -> None:
    """A file larger than max_file_size_bytes causes skipped_reason='file_too_large'."""
    from orch.daemon.auto_merge import classify_conflicts

    conflict_file = tmp_path / "docs" / "huge.md"
    conflict_file.parent.mkdir(parents=True, exist_ok=True)
    conflict_file.write_text("x" * 1001 + "\n<<<<<<< HEAD\nA\n=======\nB\n>>>>>>> branch\n")

    config = _make_config(
        allowlist=["docs/**/*.md"],
        refuselist=[],
        max_file_size=500,
    )

    result = classify_conflicts(
        worktree_path=tmp_path,
        conflict_files=["docs/huge.md"],
        config=config,
    )

    assert result.skipped_reason == "file_too_large"
    assert "docs/huge.md" in result.oversized_files
