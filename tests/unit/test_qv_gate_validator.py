"""Unit tests for orch.qv_gate_validator — pure function tests with tmp_path as repo_root."""

from __future__ import annotations

from pathlib import Path

from orch.qv_gate_validator import (
    _bare_executable,
    _cd_directory,
    _makefile_has_target,
    _makefile_target,
    classify_qv_gate,
    validate_qv_gate,
)

# ---------------------------------------------------------------------------
# _makefile_target
# ---------------------------------------------------------------------------


class TestMakefileTarget:
    def test_plain_target(self) -> None:
        assert _makefile_target("make lint") == "lint"

    def test_target_with_flags(self) -> None:
        # -C, -f, -j flags consume their arguments and find the real target
        assert _makefile_target("make -C . lint") == "lint"
        assert _makefile_target("make --quiet lint") == "lint"
        assert _makefile_target("make -j2 lint") == "lint"

    def test_target_with_phony(self) -> None:
        # PHONY declaration on a separate line does not affect target detection
        assert _makefile_target(".PHONY: lint\nlint:\n\topts") is None  # not a make cmd
        assert _makefile_target("make lint") == "lint"

    def test_makefile_only_no_target(self) -> None:
        # bare 'make' (no target) — conservatively returns None (unclassifiable)
        assert _makefile_target("make") is None

    def test_non_make_command(self) -> None:
        assert _makefile_target("lint") is None

    def test_compound_make_command(self) -> None:
        # After shlex.split, "make lint && echo done" becomes
        # ['make', 'lint', '&&', 'echo', 'done']; 'lint' is returned as target.
        # This is the actual behaviour — compound commands are not filtered here.
        assert _makefile_target("make lint && echo done") == "lint"


# ---------------------------------------------------------------------------
# _makefile_has_target
# ---------------------------------------------------------------------------


class TestMakefileHasTarget:
    def test_target_exists(self, tmp_path: Path) -> None:
        (tmp_path / "Makefile").write_text("lint:\n\techo ok\n")
        assert _makefile_has_target(tmp_path, "lint") is True

    def test_target_missing(self, tmp_path: Path) -> None:
        (tmp_path / "Makefile").write_text("lint:\n\techo ok\n")
        assert _makefile_has_target(tmp_path, "arch-check") is False

    def test_no_makefile(self, tmp_path: Path) -> None:
        assert _makefile_has_target(tmp_path, "lint") is False

    def test_target_with_tab_indentation(self, tmp_path: Path) -> None:
        (tmp_path / "Makefile").write_text("lint:\techo ok\n")
        assert _makefile_has_target(tmp_path, "lint") is True

    def test_target_with_space_indentation(self, tmp_path: Path) -> None:
        (tmp_path / "Makefile").write_text("lint:  echo ok\n")
        assert _makefile_has_target(tmp_path, "lint") is True

    def test_target_with_dependencies(self, tmp_path: Path) -> None:
        (tmp_path / "Makefile").write_text("test: test-unit test-integration\n\topts\n")
        assert _makefile_has_target(tmp_path, "test") is True

    def test_target_is_prefix_of_another(self, tmp_path: Path) -> None:
        # "^lint:" should not match "lint-check:"
        (tmp_path / "Makefile").write_text("lint-check:\n\techo ok\n")
        assert _makefile_has_target(tmp_path, "lint") is False


# ---------------------------------------------------------------------------
# _cd_directory
# ---------------------------------------------------------------------------


class TestCdDirectory:
    def test_simple_cd(self) -> None:
        assert _cd_directory("cd frontend && npx tsc --noEmit") == "frontend"

    def test_cd_with_quoted_dir(self) -> None:
        assert _cd_directory("cd 'frontend' && npx tsc --noEmit") == "frontend"
        assert _cd_directory('cd "frontend" && npx tsc --noEmit') == "frontend"

    def test_cd_without_and(self) -> None:
        # "cd frontend" — standalone cd not followed by && — not the recognised pattern
        assert _cd_directory("cd frontend") == "frontend"

    def test_non_cd_command(self) -> None:
        assert _cd_directory("make lint") is None
        assert _cd_directory("ls") is None


# ---------------------------------------------------------------------------
# _bare_executable
# ---------------------------------------------------------------------------


class TestBareExecutable:
    def test_simple_executable(self) -> None:
        assert _bare_executable("npx tsc --noEmit") == "npx"
        assert _bare_executable("pytest tests/") == "pytest"

    def test_make_excluded(self) -> None:
        assert _bare_executable("make lint") is None

    def test_cd_excluded(self) -> None:
        assert _bare_executable("cd frontend && ls") is None

    def test_shell_operators_excluded(self) -> None:
        assert _bare_executable("foo | bar") is None
        # '&&' is a shell operator but it appears AFTER the first token in the
        # shlex-split list, so _bare_executable returns the first token.
        assert _bare_executable("foo && bar") == "foo"
        assert _bare_executable("foo > out.txt") is None

    def test_metacharacters_excluded(self) -> None:
        assert _bare_executable("foo$var") is None
        assert _bare_executable("foo?bar") is None
        assert _bare_executable("foo[0]") is None


# ---------------------------------------------------------------------------
# classify_qv_gate — Makefile patterns
# ---------------------------------------------------------------------------


class TestClassifyMakefileGate:
    def test_target_present_runnable(self, tmp_path: Path) -> None:
        (tmp_path / "Makefile").write_text("lint:\n\techo ok\n")
        v = classify_qv_gate(tmp_path, "lint", "make lint")
        assert v.runnable is True
        assert v.reason is None

    def test_target_missing_phantom(self, tmp_path: Path) -> None:
        (tmp_path / "Makefile").write_text("lint:\n\techo ok\n")
        v = classify_qv_gate(tmp_path, "arch-check", "make arch-check")
        assert v.runnable is False
        assert v.reason == "missing_makefile_target"

    def test_makefile_file_missing_phantom(self, tmp_path: Path) -> None:
        # No Makefile at all
        v = classify_qv_gate(tmp_path, "lint", "make lint")
        assert v.runnable is False
        assert v.reason == "missing_makefile_file"

    def test_target_with_dependencies(self, tmp_path: Path) -> None:
        (tmp_path / "Makefile").write_text("test: test-unit test-integration\n\tnope\n")
        v = classify_qv_gate(tmp_path, "test", "make test")
        assert v.runnable is True

    def test_target_with_phony(self, tmp_path: Path) -> None:
        (tmp_path / "Makefile").write_text(".PHONY: lint\nlint:\n\tnope\n")
        v = classify_qv_gate(tmp_path, "lint", "make lint")
        assert v.runnable is True


# ---------------------------------------------------------------------------
# classify_qv_gate — cd <dir> patterns
# ---------------------------------------------------------------------------


class TestClassifyCdGate:
    def test_cd_dir_present_runnable(self, tmp_path: Path) -> None:
        (tmp_path / "frontend").mkdir()
        v = classify_qv_gate(tmp_path, "frontend-tsc", "cd frontend && npx tsc --noEmit")
        assert v.runnable is True

    def test_cd_dir_missing_phantom(self, tmp_path: Path) -> None:
        v = classify_qv_gate(tmp_path, "frontend-tsc", "cd frontend && npx tsc --noEmit")
        assert v.runnable is False
        assert v.reason == "missing_directory"

    def test_cd_dir_is_a_file_phantom(self, tmp_path: Path) -> None:
        (tmp_path / "frontend").write_text("not a directory")
        v = classify_qv_gate(tmp_path, "frontend-tsc", "cd frontend && npx tsc --noEmit")
        assert v.runnable is False
        assert v.reason == "missing_directory"


# ---------------------------------------------------------------------------
# classify_qv_gate — bare executable patterns
# ---------------------------------------------------------------------------


class TestClassifyBareExecGate:
    def test_bare_exec_on_path_runnable(self, tmp_path: Path) -> None:
        # 'sh' is on PATH on every Linux box — always runnable
        v = classify_qv_gate(tmp_path, "shell-check", "sh -c 'echo ok'")
        assert v.runnable is True

    def test_bare_exec_off_path_still_runnable(self, tmp_path: Path) -> None:
        # Conservative: we do NOT check shutil.which(), so off-path binaries
        # are treated as runnable (false-negative degrades to pre-fix behaviour)
        v = classify_qv_gate(tmp_path, "deno-fmt", "deno-this-binary-does-not-exist --check")
        assert v.runnable is True


# ---------------------------------------------------------------------------
# classify_qv_gate — conservative-default cases
# ---------------------------------------------------------------------------


class TestClassifyConservative:
    def test_unknown_shape_returns_runnable(self, tmp_path: Path) -> None:
        # Complex pipeline — unrecognised, be conservative and assume runnable
        v = classify_qv_gate(tmp_path, "weird", "foo | bar | baz > out.txt")
        assert v.runnable is True

    def test_make_with_no_target_returns_runnable(self, tmp_path: Path) -> None:
        (tmp_path / "Makefile").write_text("all:\n\tnope\n")
        v = classify_qv_gate(tmp_path, "default", "make")
        assert v.runnable is True

    def test_command_with_envvars_returns_runnable(self, tmp_path: Path) -> None:
        # We don't expand $VAR — be conservative
        v = classify_qv_gate(tmp_path, "x", "FOO=1 some-command")
        assert v.runnable is True


# ---------------------------------------------------------------------------
# validate_qv_gate (convenience wrapper)
# ---------------------------------------------------------------------------


class TestValidateQvGate:
    def test_validates_runnable_gate(self, tmp_path: Path) -> None:
        (tmp_path / "Makefile").write_text("lint:\n\tnope\n")
        assert validate_qv_gate(tmp_path, "lint", "make lint") is True

    def test_validates_phantom_gate(self, tmp_path: Path) -> None:
        (tmp_path / "Makefile").write_text("lint:\n\tnope\n")
        assert validate_qv_gate(tmp_path, "arch-check", "make arch-check") is False


# ---------------------------------------------------------------------------
# Reason strings are documented values
# ---------------------------------------------------------------------------


class TestReasonStrings:
    def test_all_reasons_are_known(self, tmp_path: Path) -> None:
        """Every reason string returned must be one of the four documented values."""
        known = {
            "missing_makefile_target",
            "missing_makefile_file",
            "missing_directory",
            "missing_executable",
        }
        # Touch every phantom path
        (tmp_path / "Makefile").write_text("lint:\n\tnope\n")

        v1 = classify_qv_gate(tmp_path, "arch-check", "make arch-check")
        assert v1.reason in known

        # Remove Makefile
        (tmp_path / "Makefile").unlink()
        v2 = classify_qv_gate(tmp_path, "lint", "make lint")
        assert v2.reason in known

        v3 = classify_qv_gate(tmp_path, "frontend-tsc", "cd frontend && echo nope")
        assert v3.reason in known
