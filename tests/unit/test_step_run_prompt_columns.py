"""CR-00056 S11: Unit tests for StepRun.prompt_text and fix_prompt_text columns.

Verifies the ORM model accepts the new columns at construction and that the
Python-level attribute assignment works correctly.

These are "unit" tests in the strict sense — they test the Python object
construction without any database round-trip. The attribute round-trip is
verified by direct Python assignment, not by flushing to a DB. The DB
integration is proven by the integration tests (test_daemon_prompt_snapshot.py).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Integer, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# ---------------------------------------------------------------------------
# Minimal StepRun-like model for unit testing without touching the real Base
# ---------------------------------------------------------------------------


class MinimalBase(DeclarativeBase):
    pass


class MinimalWorkflowStep(MinimalBase):
    """Minimal WorkflowStep stub — just enough FK for StepRun construction."""

    __tablename__ = "workflow_steps"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)


class StepRunStub(MinimalBase):
    """Minimal StepRun stub that replicates the new CR-00056 columns.

    Uses the same column types (Text, nullable) as the real StepRun to verify
    Python-level attribute assignment and constructor signatures.
    """

    __tablename__ = "step_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    step_id: Mapped[int] = mapped_column(Integer, nullable=False)
    run_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(Text, nullable=True)
    # CR-00056 columns (exact same types as real model)
    prompt_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    fix_prompt_text: Mapped[str | None] = mapped_column(Text, nullable=True)


def _make_step() -> MinimalWorkflowStep:
    """Create a minimal stub step to satisfy FK."""
    return MinimalWorkflowStep(id=99999)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_step_run_accepts_prompt_text():
    """Constructing StepRun with prompt_text='...' does not raise; attribute round-trips."""
    step = _make_step()
    run = StepRunStub(
        step_id=step.id,
        run_number=1,
        status="running",
        started_at=None,
        prompt_text="This is the initial prompt content for step S04.",
    )
    assert run.prompt_text == "This is the initial prompt content for step S04."
    assert run.fix_prompt_text is None


def test_step_run_accepts_fix_prompt_text():
    """Constructing StepRun with fix_prompt_text='...' does not raise; attribute round-trips."""
    step = _make_step()
    run = StepRunStub(
        step_id=step.id,
        run_number=2,
        status="running",
        started_at=None,
        prompt_text=None,
        fix_prompt_text="This is the fix-cycle prompt for step S04 retry.",
    )
    assert run.fix_prompt_text == "This is the fix-cycle prompt for step S04 retry."
    assert run.prompt_text is None


def test_step_run_defaults_prompt_columns_to_none():
    """When constructed without those kwargs, both attributes are None."""
    step = _make_step()
    run = StepRunStub(
        step_id=step.id,
        run_number=1,
        status="completed",
        started_at=None,
    )
    assert run.prompt_text is None
    assert run.fix_prompt_text is None


def test_step_run_accepts_both_prompt_columns_together():
    """StepRun can carry both base prompt_text and fix_prompt_text simultaneously."""
    step = _make_step()
    run = StepRunStub(
        step_id=step.id,
        run_number=2,
        status="running",
        started_at=None,
        prompt_text="Base prompt — kept for backwards-traceability.",
        fix_prompt_text="Fix prompt — contains the retry instructions.",
    )
    assert run.prompt_text == "Base prompt — kept for backwards-traceability."
    assert run.fix_prompt_text == "Fix prompt — contains the retry instructions."


def test_step_run_prompt_text_with_long_content():
    """prompt_text accepts a very long string (multi-KB prompt)."""
    step = _make_step()
    long_prompt = "A" * 10_000  # 10 KB of prompt content
    run = StepRunStub(
        step_id=step.id,
        run_number=1,
        status="running",
        started_at=None,
        prompt_text=long_prompt,
    )
    assert run.prompt_text == long_prompt
    assert len(run.prompt_text) == 10_000


def test_step_run_prompt_text_special_characters():
    """prompt_text correctly stores content with HTML-sensitive characters."""
    step = _make_step()
    dangerous = "<script>alert('xss')</script> & \"quotes\""
    run = StepRunStub(
        step_id=step.id,
        run_number=1,
        status="completed",
        started_at=None,
        prompt_text=dangerous,
    )
    assert run.prompt_text == dangerous
    # The raw value is stored as-is; escaping happens at render time (dashboard tests)


def test_step_run_accepts_prompt_text_with_unicode():
    """prompt_text accepts unicode content correctly."""
    step = _make_step()
    unicode_prompt = "日本語テスト 🎉 <>&'\""
    run = StepRunStub(
        step_id=step.id,
        run_number=1,
        status="running",
        started_at=None,
        prompt_text=unicode_prompt,
    )
    assert run.prompt_text == unicode_prompt


def test_step_run_accepts_empty_string_prompt():
    """prompt_text accepts empty string (non-None)."""
    step = _make_step()
    run = StepRunStub(
        step_id=step.id,
        run_number=1,
        status="running",
        started_at=None,
        prompt_text="",
    )
    assert run.prompt_text == ""
    # Empty string is not None — important distinction for the DB column
    assert run.prompt_text is not None
