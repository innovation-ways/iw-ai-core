"""Spec-conformance test — bidirectional drift check between the iw CLI and its spec.

The ``iw`` CLI is the agent-to-DB bridge; its command set is documented in the
**§4 "Command Summary"** section of ``docs/IW_AI_Core_CLI_Spec.md`` as a fenced
ASCII tree. This module parses that tree, introspects the *actual* Click command
tree from :mod:`orch.cli.main`, and asserts:

1. Every command documented in §4 exists in the CLI.
2. Every command registered in the CLI is documented in §4.
3. Every documented command has at least one contract test under
   ``tests/integration/cli/`` **or** is listed in :data:`KNOWN_UNTESTED_COMMANDS`.

Two module-level allowlists keep the gate a *ratchet* — it fires only on NEW
problems, never on pre-existing drift / coverage gaps:

* :data:`KNOWN_SPEC_DRIFT` absorbs pre-existing existence drift (assertions 1
  and 2). CR-00073 brought §4 fully in sync with the live CLI, so it is empty.
* :data:`KNOWN_UNTESTED_COMMANDS` absorbs the pre-existing coverage gap
  (assertion 3). It is pre-seeded with every command that does not yet have a
  dedicated ``*_contract.py`` test — i.e. everything except the 6 priority
  commands CR-00073 covers first.

Both functions that produce the inputs — :func:`parse_spec_commands` and
:func:`collect_cli_commands` — are module-level so a reviewer (or a RED
demonstration) can ``monkeypatch`` them to prove the assertions can fail.

This module touches no database; it parses files and introspects Click objects.
"""

from __future__ import annotations

import re
from pathlib import Path

import click

from orch.cli.main import cli

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

# This file: tests/integration/test_cli_spec_conformance.py → repo root is parents[2].
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SPEC_PATH = _REPO_ROOT / "docs" / "IW_AI_Core_CLI_Spec.md"
_CONTRACT_TEST_DIR = _REPO_ROOT / "tests" / "integration" / "cli"

# The 5 distinct leaf commands that CR-00073 ships dedicated *_contract.py
# coverage for (the "evidence-ingestion hooks" priority group exercises
# approve + step-done, already in this set — so it is 5 commands, not 6).
PRIORITY_COMMANDS: frozenset[str] = frozenset(
    {"step-done", "register", "doc-update", "approve", "next-id"}
)


# ---------------------------------------------------------------------------
# Allowlists — module-level constants, auditable by code review
# ---------------------------------------------------------------------------

# Existence drift the conformance check tolerates. Keyed by command name; each
# entry carries a "reason" (filed Incident ID or one-line rationale) and a
# "direction" — "spec_only" (documented but absent from the CLI) or "cli_only"
# (registered in the CLI but undocumented). CR-00073 fixed §4 of the spec doc
# directly rather than allowlisting, so this is empty: any drift now fails.
KNOWN_SPEC_DRIFT: dict[str, dict[str, str]] = {}

# Commands that do not yet have a dedicated contract test. Keyed by command
# name; each entry carries a one-line "reason". Pre-seeded with every command
# outside the 6 priority commands (see PRIORITY_COMMANDS) — this is expected to
# be the large majority and is correct: CR-00073 covers priority commands
# first (see the design's "Out of Scope"). Assertion 3 fails only when a NEWLY
# added command ships with neither a contract test nor an entry here.
_DEFERRED = "non-priority — contract coverage deferred, TESTS_ENHANCEMENT 3.3 follow-up"
KNOWN_UNTESTED_COMMANDS: dict[str, dict[str, str]] = {
    "current-project": {"reason": _DEFERRED},
    "approve-merge": {"reason": _DEFERRED},
    "unapprove": {"reason": _DEFERRED},
    "item-cancel": {"reason": _DEFERRED},
    "item-status": {"reason": _DEFERRED},
    "item-report": {"reason": _DEFERRED},
    "archive": {"reason": _DEFERRED},
    "step-start": {"reason": _DEFERRED},
    "step-fail": {"reason": _DEFERRED},
    "step-restart": {"reason": _DEFERRED},
    "step-restart-from": {"reason": _DEFERRED},
    "step-skip": {"reason": _DEFERRED},
    "step-kill": {"reason": _DEFERRED},
    "batch-create": {"reason": _DEFERRED},
    "batch-approve": {"reason": _DEFERRED},
    "batch-status": {"reason": _DEFERRED},
    "batch-pause": {"reason": _DEFERRED},
    "batch-resume": {"reason": _DEFERRED},
    "batch-cancel": {"reason": _DEFERRED},
    "doc-job-start": {"reason": _DEFERRED},
    "doc-job-done": {"reason": _DEFERRED},
    "doc-job-status": {"reason": _DEFERRED},
    "docs-export": {"reason": _DEFERRED},
    "regression-classify": {"reason": _DEFERRED},
    "search": {"reason": _DEFERRED},
    "worktree-status": {"reason": _DEFERRED},
    "sync-skills": {"reason": _DEFERRED},
    "sync-agents": {"reason": _DEFERRED},
    "sync-templates": {"reason": _DEFERRED},
    "init-project": {"reason": _DEFERRED},
    "db-identity": {"reason": _DEFERRED},
    "db-identity show": {"reason": _DEFERRED},
    "db-identity check": {"reason": _DEFERRED},
    "migration-lock": {"reason": _DEFERRED},
    "migration-lock acquire": {"reason": _DEFERRED},
    "migration-lock release": {"reason": _DEFERRED},
    "migration-lock status": {"reason": _DEFERRED},
    "migrations": {"reason": _DEFERRED},
    "migrations list-pending": {"reason": _DEFERRED},
    "migrations dry-run": {"reason": _DEFERRED},
    "migrations apply": {"reason": _DEFERRED},
    "merge-queue": {"reason": _DEFERRED},
    "merge-queue status": {"reason": _DEFERRED},
    "merge-queue unfreeze": {"reason": _DEFERRED},
    "merge-queue retry-merge": {"reason": _DEFERRED},
    "oss": {"reason": _DEFERRED},
    "oss enable": {"reason": _DEFERRED},
    "oss disable": {"reason": _DEFERRED},
    "oss scan": {"reason": _DEFERRED},
    "oss status": {"reason": _DEFERRED},
    "oss install": {"reason": _DEFERRED},
    "oss fix": {"reason": _DEFERRED},
    "daemon": {"reason": _DEFERRED},
    "daemon start": {"reason": _DEFERRED},
    "daemon stop": {"reason": _DEFERRED},
    "daemon status": {"reason": _DEFERRED},
    "projects": {"reason": _DEFERRED},
    "projects list": {"reason": _DEFERRED},
}


# ---------------------------------------------------------------------------
# Spec parsing — §4 "Command Summary" fenced ASCII tree
# ---------------------------------------------------------------------------

# A tree row: optional indent units, then a branch connector, then the name.
# Each indent unit is 4 columns ("│   " or "    "). The connector itself is
# "├── " or "└── ". depth 1 == top-level command under the `iw` root.
_BRANCH_RE = re.compile(r"(├──|└──)")


def _extract_section4_block(spec_text: str) -> str:
    """Return the fenced code block under the §4 "Command Summary" heading.

    Raises ValueError if §4 or its fenced block cannot be located — a missing
    section is itself a spec defect this test must surface, not swallow.
    """
    heading = re.search(r"^##\s+4\.\s+Command Summary\s*$", spec_text, re.MULTILINE)
    if heading is None:
        raise ValueError("§4 'Command Summary' heading not found in CLI spec")
    after = spec_text[heading.end() :]
    fence = re.search(r"```[^\n]*\n(.*?)\n```", after, re.DOTALL)
    if fence is None:
        raise ValueError("§4 'Command Summary' fenced code block not found in CLI spec")
    return fence.group(1)


def parse_spec_commands(spec_text: str | None = None) -> set[str]:
    """Parse the §4 ASCII command tree into a set of full command paths.

    Sub-commands are returned space-joined with their group: a ``status``
    nested under ``daemon`` is returned as ``"daemon status"``. The ``iw``
    root and pure description text are ignored. Robust to the box-drawing
    branch characters and to commands with or without a trailing description.

    When *spec_text* is None the live ``docs/IW_AI_Core_CLI_Spec.md`` is read.
    """
    if spec_text is None:
        spec_text = _SPEC_PATH.read_text(encoding="utf-8")

    block = _extract_section4_block(spec_text)

    commands: set[str] = set()
    parent_at_depth: dict[int, str] = {}
    for line in block.splitlines():
        match = _BRANCH_RE.search(line)
        if match is None:
            continue  # the `iw` root line, blank lines, stray `│` columns
        depth = match.start() // 4 + 1
        rest = line[match.end() :].strip()
        if not rest:
            continue
        name = rest.split()[0]
        full = name if depth == 1 else f"{parent_at_depth[depth - 1]} {name}"
        parent_at_depth[depth] = full
        # A deeper node can never inherit a stale sibling at a greater depth.
        for stale in [d for d in parent_at_depth if d > depth]:
            del parent_at_depth[stale]
        commands.add(full)
    return commands


# ---------------------------------------------------------------------------
# CLI introspection — the actual Click command tree
# ---------------------------------------------------------------------------


def collect_cli_commands(group: click.Group | None = None, prefix: str = "") -> set[str]:
    """Walk the Click command tree, returning every command's full path.

    Sub-commands of a :class:`click.Group` are space-joined with the group
    name (matching :func:`parse_spec_commands`). The group node itself is
    included — a group is a registered command too.
    """
    if group is None:
        group = cli
    found: set[str] = set()
    for name, command in group.commands.items():
        full = f"{prefix}{name}"
        found.add(full)
        if isinstance(command, click.Group):
            found |= collect_cli_commands(command, prefix=f"{full} ")
    return found


# ---------------------------------------------------------------------------
# Contract-test coverage detection
# ---------------------------------------------------------------------------


def commands_with_contract_tests() -> set[str]:
    """Return the set of commands that have at least one contract test.

    Scans every ``test_*_contract.py`` file under ``tests/integration/cli/``.
    A command is considered tested when each segment of its full path appears
    as a quoted CLI token (``"step-done"``, ``'acquire'``, …) in the same
    file — the form a command takes when passed to ``CliRunner.invoke`` or a
    subprocess ``argv``. The quote anchors prevent ``approve`` from matching
    inside ``approve-merge``.
    """
    contract_files = sorted(_CONTRACT_TEST_DIR.glob("test_*_contract.py"))
    file_texts = {p: p.read_text(encoding="utf-8") for p in contract_files}

    def _token_re(token: str) -> re.Pattern[str]:
        return re.compile(r"""["']""" + re.escape(token) + r"""["']""")

    tested: set[str] = set()
    all_cmds = collect_cli_commands() | parse_spec_commands()
    for cmd in all_cmds:
        segments = cmd.split(" ")
        seg_res = [_token_re(seg) for seg in segments]
        for text in file_texts.values():
            if all(rgx.search(text) for rgx in seg_res):
                tested.add(cmd)
                break
    return tested


# ---------------------------------------------------------------------------
# Assertion 1 — every documented command exists in the CLI
# ---------------------------------------------------------------------------


def test_every_spec_command_exists_in_cli() -> None:
    """§4 must not document a command the CLI does not register."""
    spec_commands = parse_spec_commands()
    cli_commands = collect_cli_commands()

    spec_only = spec_commands - cli_commands
    unexpected = {
        cmd
        for cmd in spec_only
        if not (cmd in KNOWN_SPEC_DRIFT and KNOWN_SPEC_DRIFT[cmd].get("direction") == "spec_only")
    }
    assert unexpected == set(), (
        "docs/IW_AI_Core_CLI_Spec.md §4 documents commands the CLI does not "
        f"register (fix §4 or add a KNOWN_SPEC_DRIFT entry): {sorted(unexpected)}"
    )


# ---------------------------------------------------------------------------
# Assertion 2 — every CLI command is documented in §4
# ---------------------------------------------------------------------------


def test_every_cli_command_documented_in_spec() -> None:
    """The CLI must not register a command undocumented in §4."""
    spec_commands = parse_spec_commands()
    cli_commands = collect_cli_commands()

    cli_only = cli_commands - spec_commands
    unexpected = {
        cmd
        for cmd in cli_only
        if not (cmd in KNOWN_SPEC_DRIFT and KNOWN_SPEC_DRIFT[cmd].get("direction") == "cli_only")
    }
    assert unexpected == set(), (
        "The iw CLI registers commands undocumented in docs/IW_AI_Core_CLI_Spec.md "
        f"§4 (fix §4 or add a KNOWN_SPEC_DRIFT entry): {sorted(unexpected)}"
    )


# ---------------------------------------------------------------------------
# Assertion 3 — every documented command has a contract test (or is allowlisted)
# ---------------------------------------------------------------------------


def test_every_spec_command_has_contract_test_or_allowlisted() -> None:
    """Each §4 command needs a contract test OR a KNOWN_UNTESTED_COMMANDS entry."""
    spec_commands = parse_spec_commands()
    tested = commands_with_contract_tests()

    uncovered = {
        cmd for cmd in spec_commands if cmd not in tested and cmd not in KNOWN_UNTESTED_COMMANDS
    }
    assert uncovered == set(), (
        "Spec commands with neither a contract test under tests/integration/cli/ "
        f"nor a KNOWN_UNTESTED_COMMANDS entry: {sorted(uncovered)}"
    )


# ---------------------------------------------------------------------------
# Self-checks — guard the conformance machinery itself
# ---------------------------------------------------------------------------


def test_spec_parser_extracts_a_realistic_command_set() -> None:
    """The §4 parser must yield a non-trivial tree including nested sub-commands."""
    spec_commands = parse_spec_commands()
    # §4 documents dozens of commands across several groups — a parser that
    # silently returns a near-empty set (bad regex, wrong section) is a bug.
    assert len(spec_commands) >= 30, f"§4 parser yielded too few commands: {spec_commands}"
    # Nested sub-commands must be space-joined with their group.
    assert "migration-lock acquire" in spec_commands
    assert "daemon start" in spec_commands
    assert "projects list" in spec_commands
    # Top-level commands appear bare.
    assert "next-id" in spec_commands
    # The `iw` root is not itself a command.
    assert "iw" not in spec_commands


def test_cli_introspection_includes_groups_and_subcommands() -> None:
    """The Click walk must descend into groups and join sub-command paths."""
    cli_commands = collect_cli_commands()
    assert len(cli_commands) >= 30, f"CLI introspection yielded too few: {cli_commands}"
    # Group node itself plus a nested sub-command.
    assert "migration-lock" in cli_commands
    assert "migration-lock acquire" in cli_commands
    # All 5 priority commands are real, registered, top-level commands.
    assert cli_commands >= PRIORITY_COMMANDS


def test_priority_commands_are_detected_as_contract_tested() -> None:
    """The contract-test scanner must recognise the 6 priority commands as covered.

    This guards the detection in :func:`commands_with_contract_tests` — if it
    silently stopped finding the priority commands, assertion 3 would pass
    vacuously for them.
    """
    tested = commands_with_contract_tests()
    missing = PRIORITY_COMMANDS - tested
    assert missing == set(), f"priority commands not detected as contract-tested: {sorted(missing)}"


def test_allowlists_are_internally_consistent() -> None:
    """The allowlists must be well-formed and must not shadow priority coverage."""
    # KNOWN_SPEC_DRIFT entries each carry a reason and a valid direction.
    for cmd, entry in KNOWN_SPEC_DRIFT.items():
        assert entry.get("reason"), f"KNOWN_SPEC_DRIFT[{cmd!r}] missing 'reason'"
        assert entry.get("direction") in {"spec_only", "cli_only"}, (
            f"KNOWN_SPEC_DRIFT[{cmd!r}] has invalid 'direction': {entry.get('direction')!r}"
        )
    # KNOWN_UNTESTED_COMMANDS entries each carry a reason.
    for cmd, entry in KNOWN_UNTESTED_COMMANDS.items():
        assert entry.get("reason"), f"KNOWN_UNTESTED_COMMANDS[{cmd!r}] missing 'reason'"
    # A priority command must never be parked in KNOWN_UNTESTED_COMMANDS — that
    # would hide a real regression if its contract test were deleted.
    shadowed = PRIORITY_COMMANDS & set(KNOWN_UNTESTED_COMMANDS)
    assert shadowed == set(), (
        f"priority commands must not be in KNOWN_UNTESTED_COMMANDS: {sorted(shadowed)}"
    )
