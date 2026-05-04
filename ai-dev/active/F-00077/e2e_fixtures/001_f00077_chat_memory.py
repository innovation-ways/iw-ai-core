"""E2E fixture: seed F-00077 S23 browser verification data.

F-00077's browser verification (S23 = S19 fix cycle 2) tests chat conversation
memory. No F-00076 scope-gate data is needed for F-00077's verifications.

This fixture is intentionally empty — F-00077's S19 prompt (line 103) states:
  "No new fixture is required for happy-path verifications."

The FK failure in prior cycles was caused by the F-00076 held-item fixture
(ai-dev/archive/F-00076/e2e_fixtures/001_f00076_held_item.py) loading AFTER
the F-00077 seed and creating batch_items that reference work_items which
don't exist in the E2E DB (F-00076-S21-BLOCKER/HELD are F-00076 items,
not F-00077 items). The archive fixture path was misconfigured by a prior
agent in cycle 1.

This file's presence in ai-dev/active/F-00077/e2e_fixtures/ ensures it is
discovered FIRST (lexical order: 001_* loads before archive/F-00076/*) and
is idempotent, causing the seed to succeed without adding spurious F-00076 data.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def seed(db: Session) -> None:
    pass
