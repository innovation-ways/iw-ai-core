# F-00086_S03_Backend_prompt

**Work Item**: F-00086 -- Multi-tab AI Assistant on OpenCode
**Step**: S03
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss.

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Do not run `alembic upgrade/downgrade/stamp` against the live DB. S01 already wrote the migration; you only consume its schema via the testcontainer fixtures in your unit tests (no direct alembic calls from your step).

## Input Files

- **Runtime step state** — `uv run iw item-status F-00086 --json`.
- `ai-dev/active/F-00086/F-00086_Feature_Design.md` — design document
- `ai-dev/active/F-00086/reports/F-00086_S01_Database_report.md` — S01 report (ChatTab ORM shape)
- Existing chat plumbing (you will move these, do NOT modify their behaviour):
  - `orch/chat/__init__.py`
  - `orch/chat/opencode_runtime.py`
  - `orch/chat/opencode_client.py`
  - `orch/chat/relay_manager.py`
  - `orch/chat/filters.py`

## Output Files

- `orch/chat/runtime_base.py` — new `ChatRuntime` ABC
- `orch/chat/opencode/__init__.py` — new subpackage
- `orch/chat/opencode/runtime.py` — moved from `orch/chat/opencode_runtime.py`
- `orch/chat/opencode/client.py` — moved from `orch/chat/opencode_client.py`
- `orch/chat/opencode/relay_manager.py` — moved from `orch/chat/relay_manager.py` + rekeyed by `tab_id`
- `orch/chat/opencode/filters.py` — moved from `orch/chat/filters.py`
- `orch/chat/tab_service.py` — new tab CRUD + soft-cap + soft-delete + reopen + bootstrap
- `orch/chat/migration_helpers.py` — new `bootstrap_default_tab(project_id)`
- `orch/chat/__init__.py` — updated re-exports
- `ai-dev/active/F-00086/reports/F-00086_S03_Backend_report.md` — Step report

## Context

You are implementing the **runtime-agnostic backend layer** for the multi-tab AI Assistant. Three things happen in this step:

1. **Define the `ChatRuntime` ABC** so the existing OpenCode plumbing can implement it and the future Pi plumbing (F-B) can implement it without re-touching tab_service or RelayManager.
2. **Move the existing OpenCode plumbing into an `orch/chat/opencode/` subpackage** as a MECHANICAL rename — no behaviour change. Verify by running `tests/dashboard/test_chat_*.py` after the move and ensuring no regression.
3. **Add the tab_service + migration_helpers modules** that wrap the new `chat_tabs` table with CRUD, soft-cap, soft-delete/reopen, and bootstrap-default semantics.

Read the design document's §Scope and §Invariants in full before writing code. The Invariants section is your acceptance contract.

## Requirements

### 1. Define the `ChatRuntime` ABC (`orch/chat/runtime_base.py`)

Abstract base class. Use `abc.ABC` + `@abstractmethod`. Every method is `async`. The signatures below are mandatory; the OpenCode runtime (after the move) MUST conform.

```python
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

class ChatRuntime(ABC):
    @abstractmethod
    async def health(self) -> bool: ...

    @abstractmethod
    async def create_session(
        self, *, model: str | None = None, agent: str | None = None, directory: str | None = None
    ) -> str: ...

    @abstractmethod
    async def get_session(self, session_id: str) -> dict[str, Any]: ...

    @abstractmethod
    async def list_sessions(self) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def get_messages(self, session_id: str) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def prompt(
        self, session_id: str, text: str, *, model: str | None = None, system: str | None = None
    ) -> None: ...

    @abstractmethod
    async def abort(self, session_id: str) -> None: ...

    @abstractmethod
    async def reply_permission(
        self, session_id: str, request_id: str, response: str, *, remember: bool = False
    ) -> None: ...

    @abstractmethod
    async def set_model(self, session_id: str, model: str) -> None: ...

    @abstractmethod
    async def close_session(self, session_id: str) -> None: ...

    @abstractmethod
    async def subscribe(
        self, session_id: str, *, last_event_id: str | None = None
    ) -> AsyncIterator[dict[str, Any]]: ...

    @abstractmethod
    async def get_config(self) -> dict[str, Any]: ...

    @abstractmethod
    async def get_providers(self) -> dict[str, Any]: ...
```

If a method is genuinely absent from today's OpenCode client (e.g., `set_model` may not exist as a public method), add it to the client during this step as a thin wrapper that posts to the OpenCode HTTP surface — match the existing client style.

### 2. Move the OpenCode plumbing into `orch/chat/opencode/`

Use `git mv` (do NOT copy + delete — preserve git history):

```bash
git mv orch/chat/opencode_runtime.py orch/chat/opencode/runtime.py
git mv orch/chat/opencode_client.py orch/chat/opencode/client.py
git mv orch/chat/relay_manager.py orch/chat/opencode/relay_manager.py
git mv orch/chat/filters.py orch/chat/opencode/filters.py
```

Create `orch/chat/opencode/__init__.py` re-exporting the canonical names:

```python
from orch.chat.opencode.client import OpencodeClient
from orch.chat.opencode.relay_manager import RelayManager
from orch.chat.opencode.runtime import OpencodeRuntime
```

Update `orch/chat/__init__.py` to re-export the same names from the new location so importers anywhere outside this package keep working. Then **grep the entire repo** for the old import paths (`from orch.chat.opencode_runtime`, `from orch.chat.opencode_client`, `from orch.chat.relay_manager`, `from orch.chat.filters`) and update every match to the new paths.

**Behaviour MUST NOT change in this move.** After the move, run `uv run pytest tests/dashboard/test_chat_router.py tests/dashboard/test_chat_endpoint_session_lifecycle.py -v` and confirm every test still passes. (Tests will be migrated to the tab-scoped API in S08 — at S03's end they still exercise the legacy `/api/chat/sessions/*` paths, which is fine because S06 hasn't run yet.)

### 3. Make `OpencodeRuntime` extend `ChatRuntime`

Add `class OpencodeRuntime(ChatRuntime):` (was a plain class). Verify every abstract method has a matching implementation. If `set_model` or `close_session` don't exist, add them now (thin pass-throughs to the OpenCode HTTP surface or no-ops with clear docstrings explaining why).

### 4. Rekey `RelayManager` by `tab_id`

Today the relay is keyed by `opencode_session_id`. Change the public surface:

- `get_or_create_relay(tab_id: str) -> Relay`
- Each `Relay` instance is bound to one `(tab_id, opencode_session_id)` pair. The `tab_id → opencode_session_id` lookup happens inside `RelayManager.get_or_create_relay()` via a service-layer helper (`tab_service.get_tab(tab_id).opencode_session_id`).
- **Every event yielded by `Relay.subscribe()` MUST have a top-level `"tab_id"` field** (invariant #2). Stamp it at emit time inside the relay's event normalizer.
- Ring buffer semantics, `Last-Event-ID` replay, keep-alive comments — all unchanged.

### 5. New `orch/chat/tab_service.py`

Module-level functions (NOT a class) operating on a SQLAlchemy `Session` parameter:

```python
def create_tab(db: Session, *, project_id: str, runtime: str = "opencode",
               model: str, title: str = "New chat", agent: str | None = None,
               opencode_session_id: str | None = None) -> tuple[ChatTab, bool]:
    """Returns (tab, soft_cap_exceeded)."""

def list_tabs(db: Session, *, project_id: str, include_closed: bool = False) -> list[ChatTab]:
    """Active tabs ordered by last_active_at DESC; include_closed=True appends closed."""

def get_tab(db: Session, tab_id: str) -> ChatTab | None: ...

def update_tab(db: Session, tab_id: str, *, title: str | None = None,
               model: str | None = None) -> ChatTab:
    """No-op if both args are None; otherwise bumps updated_at."""

def close_tab(db: Session, tab_id: str) -> ChatTab:
    """Idempotent soft-delete. If already closed, returns unchanged."""

def reopen_tab(db: Session, tab_id: str) -> ChatTab:
    """Idempotent: if already active, returns unchanged. Clears closed_at."""

def recent_closed_tabs(db: Session, *, project_id: str, limit: int = 10) -> list[ChatTab]:
    """Closed tabs ordered by closed_at DESC."""

def touch_last_active(db: Session, tab_id: str) -> None:
    """Called by RelayManager and prompt endpoints to bump last_active_at."""
```

**Allowlists** (enforced here, not in the DB):
- `runtime` must be in `{"opencode"}` — raise `ValueError("runtime '<x>' not in allowlist {'opencode'}")`. The set is a module-level constant `ALLOWED_RUNTIMES = frozenset({"opencode"})` so F-B can extend it with one line.
- `status` is set internally — never accept it as a parameter.

**Soft cap** (invariant #4): count `active` tabs for `project_id` BEFORE insert. After insert, if `count + 1 > 10`, set `soft_cap_exceeded = True` in the return. The tab is always created; the flag is advisory.

**Empty-body PATCH** (invariant #8): if both `title` and `model` are None, return the tab unchanged WITHOUT modifying `updated_at`.

### 6. New `orch/chat/migration_helpers.py`

Single function:

```python
def bootstrap_default_tab(db: Session, *, project_id: str,
                          runtime: ChatRuntime, project_repo_root: str | None) -> ChatTab | None:
    """If NO chat_tabs row exists for project_id (active OR closed), attempt to seed one
    from a prior runtime session.

    Returns the seeded tab, or None if no seeding occurred.

    Idempotent and intent-preserving: re-running is a no-op once ANY row exists for the
    project. The gate is "zero rows", NOT "zero active rows" — once a user has had any
    tab in the project (even one they later closed), bootstrap MUST NOT resurrect an
    arbitrary prior OpenCode session, because that would override the user's
    intentional close-all action.

    Concurrency-safe via the `uq_chat_tabs_default_per_project` partial unique index
    (`UNIQUE (project_id) WHERE title='Default' AND status='active'`) — on IntegrityError,
    swallow and re-fetch the existing default tab.
    """
```

Implementation outline:

1. Query: `SELECT COUNT(*) FROM chat_tabs WHERE project_id = :pid` (counts BOTH `active` and `closed`). If count > 0, return `None` immediately — no bootstrap.
2. Call `runtime.list_sessions()`; filter by `cwd == project_repo_root` (exact equality when supplied; if `project_repo_root is None`, do NOT filter).
3. Pick the most recent matching session (sort by `created_at` or whatever field the OpenCode session dict exposes).
4. If no matching session, return `None`.
5. Otherwise, `INSERT` a new `ChatTab` with `title="Default"`, `runtime="opencode"`, `model=<cached default_model>`, `opencode_session_id=<picked>` inside a `try/except IntegrityError` that re-fetches the colliding default tab on collision (the partial unique index protects against concurrent first-load races).

### 7. Update `orch/chat/__init__.py`

Re-export:
- `ChatRuntime` (from `runtime_base`)
- `OpencodeRuntime`, `OpencodeClient`, `RelayManager` (from `opencode` subpackage)
- The `tab_service` module (as a namespace import: `from orch.chat import tab_service`)
- `bootstrap_default_tab` (from `migration_helpers`)

### 8. TDD: write at least the targeted failing tests for tab_service BEFORE the implementation

Place in `tests/unit/chat/test_tab_service.py`:

- `test_create_tab_persists_row_with_defaults`
- `test_create_tab_rejects_unknown_runtime`
- `test_create_tab_returns_soft_cap_flag_when_count_exceeds_ten`
- `test_close_tab_is_idempotent`
- `test_reopen_tab_restores_active_status`
- `test_empty_patch_does_not_bump_updated_at`
- `test_bootstrap_creates_default_tab_when_empty_and_session_exists`
- `test_bootstrap_is_idempotent_under_concurrent_calls`

Use the existing testcontainer fixture from `tests/integration/conftest.py` (move it or import it appropriately — review `tests/CLAUDE.md` for the FTS DDL hook requirement after `Base.metadata.create_all()`).

**Capture the RED run output** for `test_create_tab_returns_soft_cap_flag_when_count_exceeds_ten` — that's your primary TDD red evidence for the report.

## Project Conventions

Read `CLAUDE.md`, `orch/CLAUDE.md`, and `tests/CLAUDE.md`. Critical conventions:
- SQLAlchemy 2.0 `Mapped[...]` style.
- `DaemonEvent.event_metadata` precedent — avoid `metadata` as a column name (we don't use it here, but watch the pattern).
- Testcontainer URL: replace `postgresql+psycopg2://` with `postgresql+psycopg://`.
- Apply `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after `Base.metadata.create_all()` in test fixtures (see `tests/CLAUDE.md`).

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck` — must report zero errors involving the files you touched
3. `make lint`
4. `uv run pytest tests/unit/chat/test_tab_service.py -v` — your new tests must pass green
5. `uv run pytest tests/dashboard/test_chat_router.py tests/dashboard/test_chat_endpoint_session_lifecycle.py -v` — confirm no regression after the package move

Do NOT run the full unit or integration suite — that's S14 / S15's job.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "backend-impl",
  "work_item": "F-00086",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/chat/runtime_base.py",
    "orch/chat/__init__.py",
    "orch/chat/opencode/__init__.py",
    "orch/chat/opencode/runtime.py",
    "orch/chat/opencode/client.py",
    "orch/chat/opencode/relay_manager.py",
    "orch/chat/opencode/filters.py",
    "orch/chat/tab_service.py",
    "orch/chat/migration_helpers.py",
    "tests/unit/chat/test_tab_service.py"
  ],
  "preflight": {
    "format": "ok|fixed",
    "typecheck": "ok",
    "lint": "ok"
  },
  "tests_passed": true,
  "test_summary": "tests/unit/chat/test_tab_service.py: 8 passed",
  "tdd_red_evidence": "tests/unit/chat/test_tab_service.py::test_create_tab_returns_soft_cap_flag_when_count_exceeds_ten — AssertionError or ImportError (capture exact line from RED run)",
  "blockers": [],
  "notes": ""
}
```
