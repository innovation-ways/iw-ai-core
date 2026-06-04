# IW AI Core — Daemon Design

**Project**: IW AI Core (Innovation Ways AI Orchestration Platform)
**Author**: Sergio G. + Claude
**Date**: 2026-04-07
**Version**: 1.0.0
**Status**: Draft

---

## 1. Overview

The daemon is the heart of IW AI Core — a single Python process that orchestrates all AI agent execution across all registered projects. It runs as a simple polling loop: read DB state, make decisions, take actions, sleep, repeat.

**Design philosophy:**
- **Simple polling, not event-driven.** A 60-second poll cycle is sufficient. The system is not latency-sensitive — a 60-second delay before picking up new work is perfectly acceptable.
- **DB is the only state.** The daemon holds no critical state in memory. If it crashes and restarts, it picks up exactly where it left off by reading the DB.
- **Deterministic bash for risky operations.** Worktree creation, dependency installation, and merges are bash scripts. The daemon calls them but doesn't implement them.
- **One daemon, all projects.** A single process iterates all projects. No per-project daemon processes.

---

## 2. Process Lifecycle

### 2.1. Startup

```
iw daemon start
  |
  v
1. Check PID file — if another daemon is running, exit with error
2. Write PID file
3. Load .env configuration
4. Connect to PostgreSQL (fail fast if unreachable)
5. Load projects.toml — discover all registered projects
6. For each enabled project:
   a. Read .iw-orch.json from project repo
   b. Validate repo path exists
   c. Register/update project in DB
   d. Instantiate BatchManager for the project
7. Run startup health check:
   a. Detect orphaned worktrees (worktrees on disk with no matching DB state)
   b. Detect zombie step_runs (status='running' but PID dead)
   c. Log findings, emit daemon_events
8. Emit 'daemon_started' event
9. Enter main loop
```

### 2.2. Graceful Shutdown (SIGTERM / SIGINT)

```
Signal received (SIGTERM or SIGINT)
  |
  v
1. Set self._running = False (main loop exits on next iteration)
2. Wait for current poll cycle to complete (max 30 seconds)
3. For each running step_run:
   a. Do NOT kill the agent process — let it finish its current work
   b. Mark step_run as 'interrupted' in error_message (daemon will resume on restart)
4. Emit 'daemon_stopped' event
5. Remove PID file
6. Exit 0
```

**Key**: Graceful shutdown does NOT kill running agents. They continue in their worktrees. When the daemon restarts, it detects them as running (PID alive) and resumes monitoring. If the PID has died in the meantime, the daemon marks the step as failed.

### 2.3. Crash Recovery (Unclean Restart)

```
iw daemon start (after crash)
  |
  v
1. Stale PID file exists — check if PID is alive
   a. PID alive → another daemon is running, exit with error
   b. PID dead → stale file from crash, remove it and continue
2. Normal startup (steps 2-8 from section 2.1)
3. Startup health check is critical here:
   a. step_runs with status='running': check each PID
      - PID alive → daemon resumes monitoring (nothing to do)
      - PID dead → mark as failed, error_message="Daemon crashed, process died"
   b. batch_items with status='executing': check linked step_runs
      - If all steps completed → advance to merge queue
      - If current step failed → leave for user to restart
   c. batch_items with status='setting_up': check if worktree exists
      - Worktree exists → retry agent launch
      - Worktree missing → reset to pending (will be set up again)
4. Emit 'daemon_started' event with metadata: {recovery: true, orphans_found: N}
```

**The daemon never loses track of work.** Every running process is recorded in the DB with its PID, command, and worktree. On restart, the daemon reconciles DB state with reality (PIDs, worktrees).

---

## 3. Main Loop

```python
class Daemon:
    """The IW AI Core orchestration daemon."""

    def __init__(self, config: DaemonConfig):
        self.config = config
        self._running = True
        self.db = create_session_factory(config.db_url)
        self.projects: dict[str, ProjectConfig] = {}
        self.managers: dict[str, BatchManager] = {}
        self.quota_monitor = QuotaMonitor(config)
        self.git_monitors: dict[str, GitStatusCache] = {}
        self._poll_count = 0
        self._last_poll_at: datetime | None = None

    def run(self):
        """Main entry point. Runs until SIGTERM/SIGINT."""
        self._setup_signal_handlers()
        self._startup()

        while self._running:
            try:
                self._poll_cycle()
            except Exception:
                logger.exception("Unhandled error in poll cycle — continuing")
                # Never crash the daemon on a single poll failure.
                # Log it, emit an event, and try again next cycle.
                self._emit_event("poll_error", message=traceback.format_exc())

            self._sleep(self.config.poll_interval)

        self._shutdown()

    def _poll_cycle(self):
        """One complete iteration of the daemon's work."""
        self._poll_count += 1
        self._last_poll_at = datetime.utcnow()

        # Phase 1: Reload project config if needed
        self._reload_projects_if_stale()

        # Phase 2: Per-project processing
        for project_id, config in self.projects.items():
            if not config.enabled:
                continue

            manager = self.managers[project_id]

            # 2a. Monitor running steps (health, timeout, stall, zombie)
            manager.monitor_running_steps()

            # 2b. Process approved batches (launch new items)
            manager.process_batches()

            # 2c. Process merge queue (sequential merges)
            manager.process_merge_queue()

            # 2d. Check auto-publish for completed batches
            manager.check_auto_publish()

            # 2e. Update git status cache
            self.git_monitors[project_id].refresh_if_stale()

        # Phase 3: Cross-project services
        self.quota_monitor.poll_if_due()
```

### 3.1. Poll Cycle Phases

Each poll cycle runs through these phases in order:

| Phase | What It Does | Frequency |
|-------|-------------|-----------|
| **1. Config reload** | Re-read `projects.toml` if modified (mtime check) | Every cycle |
| **2a. Monitor steps** | Check PID health, timeouts, stalls for all running steps | Every cycle |
| **2b. Process batches** | Launch new items from approved/executing batches | Every cycle |
| **2c. Merge queue** | Squash-merge completed items to main (one at a time per project) | Every cycle |
| **2d. Auto-publish** | Push to origin for completed batches with `auto_publish=true` | Every cycle |
| **2e. Git status** | Run git commands to cache branch state, worktree count | Every 30s (stale check) |
| **3. Quota monitor** | Poll LLM provider APIs for usage data | Every 5 min (stale check) |

### 3.2. Error Handling in the Main Loop

The main loop **never crashes**. Individual poll cycles can fail — the daemon logs the error, emits a `poll_error` event, and continues to the next cycle.

```python
while self._running:
    try:
        self._poll_cycle()
    except Exception:
        logger.exception("Unhandled error in poll cycle — continuing")
        self._emit_event("poll_error", message=traceback.format_exc())
    self._sleep(self.config.poll_interval)
```

**Per-project isolation**: If processing InnoForge throws an exception, the daemon still processes Project B and Project C in the same cycle.

```python
for project_id, config in self.projects.items():
    try:
        manager.monitor_running_steps()
        manager.process_batches()
        manager.process_merge_queue()
    except Exception:
        logger.exception("Error processing project %s — skipping", project_id)
        self._emit_event("project_error", project_id=project_id, message=traceback.format_exc())
        continue  # Don't let one project block others
```

---

## 4. BatchManager — Per-Project Processing

Each project gets its own `BatchManager` instance. This is where all per-project logic lives.

### 4.1. Step Monitoring

The most critical function — runs every poll cycle for every project.

```python
class BatchManager:
    """Manages batch execution for a single project."""

    def monitor_running_steps(self):
        """Check health of all running step_runs for this project."""
        running = self.db.query(StepRun).join(WorkflowStep).join(WorkItem).filter(
            WorkItem.project_id == self.project_id,
            StepRun.status == 'running'
        ).all()

        for run in running:
            self._check_step_health(run)

    def _check_step_health(self, run: StepRun):
        """Check a single running step for timeout, stall, or crash."""
        now = datetime.utcnow()
        alive = self._is_pid_alive(run.pid)
        run.pid_alive = alive

        if alive:
            run.last_heartbeat = now

            # Check timeout
            elapsed = (now - run.started_at).total_seconds()
            if elapsed > run.timeout_secs:
                self._kill_step(run, reason=f"Timeout after {elapsed:.0f}s (limit: {run.timeout_secs}s)")
                run.status = 'timeout'
                run.completed_at = now
                run.duration_secs = elapsed
                self._update_parent_step(run, 'failed')
                self._emit('step_timeout', run)

            # Check stall
            elif self._is_stalled(run, now):
                run.status = 'stalled'
                run.error_message = f"No progress for {self.config.stall_threshold}s"
                self._emit('step_stalled', run)

        else:
            # PID is dead — did the agent report completion via iw CLI?
            if run.status == 'running':
                # No — it crashed without reporting
                run.status = 'failed'
                run.completed_at = now
                run.duration_secs = (now - run.started_at).total_seconds()
                run.error_message = "Process exited without reporting completion (PID dead)"
                self._update_parent_step(run, 'failed')
                self._emit('step_crashed', run)

        self.db.commit()

    def _is_pid_alive(self, pid: int | None) -> bool:
        """Check if a process is alive via kill -0."""
        if pid is None:
            return False
        try:
            os.kill(pid, 0)
            return True
        except (ProcessLookupError, PermissionError):
            return False

    def _is_stalled(self, run: StepRun, now: datetime) -> bool:
        """Detect stall: PID alive but no heartbeat update for too long."""
        if run.last_heartbeat is None:
            return False
        stall_age = (now - run.last_heartbeat).total_seconds()
        return stall_age > self.config.stall_threshold

    def _kill_step(self, run: StepRun, reason: str):
        """Send SIGTERM to a running step."""
        if run.pid and self._is_pid_alive(run.pid):
            try:
                os.kill(run.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass  # Already dead between check and kill — fine
        run.error_message = reason

    def _update_parent_step(self, run: StepRun, new_status: str):
        """Update the workflow_step status when a run finishes."""
        step = self.db.get(WorkflowStep, run.step_id)
        step.status = new_status
        if new_status in ('completed', 'failed'):
            step.completed_at = datetime.utcnow()
```

### 4.2. Batch Processing

Launches new work items from approved/executing batches.

```python
def process_batches(self):
    """Find approved batches and launch items."""
    batches = self.db.query(Batch).filter(
        Batch.project_id == self.project_id,
        Batch.status.in_(['approved', 'executing'])
    ).all()

    for batch in batches:
        if batch.status == 'approved':
            batch.status = 'executing'
            self._emit('batch_executing', batch)

        self._process_batch(batch)

def _process_batch(self, batch: Batch):
    """Launch items for a batch, respecting parallelism and execution groups."""
    items = self.db.query(BatchItem).filter(
        BatchItem.project_id == self.project_id,
        BatchItem.batch_id == batch.id
    ).order_by(BatchItem.execution_group, BatchItem.id).all()

    # Count currently executing items
    executing_count = sum(1 for i in items if i.status in ('setting_up', 'executing'))

    # Find the current execution group
    current_group = self._current_execution_group(items)
    if current_group is None:
        # All items processed — check if batch is done
        self._check_batch_completion(batch, items)
        return

    # Launch pending items in the current group (up to max_parallel)
    for item in items:
        if item.execution_group != current_group:
            continue
        if item.status != 'pending':
            continue
        if executing_count >= batch.max_parallel:
            break  # Parallelism limit reached

        self._launch_item(batch, item)
        executing_count += 1

def _current_execution_group(self, items: list[BatchItem]) -> int | None:
    """Determine which execution group should be processing.

    Returns the lowest group number that has pending or executing items.
    Returns None if all items are in terminal state (merged, failed, skipped).
    """
    for item in items:
        if item.status in ('pending', 'setting_up', 'executing', 'completed'):
            return item.execution_group
    return None
```

### 4.3. Item Launch

The sequence for launching a single work item:

```python
def _launch_item(self, batch: Batch, batch_item: BatchItem):
    """Launch a work item: create worktree, then start first step."""
    item_id = batch_item.work_item_id

    # Phase 1: Worktree setup (deterministic bash)
    batch_item.status = 'setting_up'
    self.db.commit()
    self._emit('item_setup_started', item_id)

    try:
        worktree_info = self._setup_worktree(item_id)
    except WorktreeSetupError as e:
        batch_item.status = 'failed'
        batch_item.notes = f"Worktree setup failed: {e}"
        self.db.commit()
        self._emit('item_failed', item_id, message=str(e))
        return

    batch_item.status = 'executing'
    batch_item.worktree_info = worktree_info
    batch_item.started_at = datetime.utcnow()
    self.db.commit()
    self._emit('item_setup_completed', item_id)

    # Phase 2: Launch first pending step
    self._launch_next_step(item_id, worktree_info)

def _setup_worktree(self, item_id: str) -> dict:
    """Call the bash worktree setup script. Returns worktree metadata."""
    result = subprocess.run(
        ['bash', str(self.config.executor_dir / 'worktree_setup.sh'),
         item_id, self.project_config.repo_root],
        capture_output=True, text=True, timeout=300
    )
    if result.returncode != 0:
        raise WorktreeSetupError(result.stderr)

    worktree_path = self.project_config.repo_root / '.worktrees' / item_id
    return {
        'path': str(worktree_path),
        'branch': f'agent/{item_id}',
        'created_at': datetime.utcnow().isoformat()
    }
```

### 4.4. Worktree Container Lifecycle (F-00062)

After `worktree_setup.sh` succeeds, the daemon checks whether the project has an `ai-dev/iw-config/` directory. If so, it brings up a per-worktree Docker Compose stack (`orch/daemon/worktree_compose.py`):

```python
def _launch_item(self, batch: Batch, batch_item: BatchItem):
    batch_item.status = 'setting_up'
    self.db.commit()

    try:
        worktree_info = self._setup_worktree(item_id)
    except WorktreeSetupError as e:
        batch_item.status = 'failed'
        batch_item.notes = f"Worktree setup failed: {e}"
        self.db.commit()
        return

    batch_item.status = 'executing'
    batch_item.started_at = datetime.utcnow()
    self.db.commit()

    # Per-worktree compose stack (project-opted-in via ai-dev/iw-config/)
    if self.project_config.has_iw_config:
        up_result = self.worktree_compose.up(batch_item, worktree_info)
        if not up_result.success:
            batch_item.status = 'setup_failed'
            batch_item.notes = f"Compose setup failed: {up_result.error}"
            self.worktree_compose.down(batch_item.id)
            self.db.commit()
            return

    # Launch first pending step
    self._launch_next_step(item_id, worktree_info)
```

**`worktree_compose.up()`** renders the Jinja2 template from `ai-dev/iw-config/worktree-compose.template.yml`, discovers published ports (`worktree_db_port`, `worktree_app_port`), saves `worktree_compose_path`, and runs the optional `worktree-seed.sh`.

**Phase failure** → `setup_failed` status; `worktree_compose.down()` fires immediately; no step launch.

**Teardown** (`worktree_compose.down()`) fires on terminal status transitions (`merged`, `failed`, `skipped`, `killed`, `setup_failed`) via `_complete_item()` and `_on_step_failed()`.

Container naming: `iwcore-<batch_item_id>`. Persisted: `BatchItem.worktree_db_port`, `worktree_app_port`, `worktree_compose_path`.

#### Container Reaper

`orch/daemon/worktree_reaper.py` runs on daemon startup and every poll cycle:

- **Active**: container has matching non-terminal `BatchItem`
- **Stale**: container has matching terminal `BatchItem` (cleanable)
- **Orphan**: no matching `BatchItem` at all (leaked)

Operator force-teardown: dashboard Worktrees page → trash icon.

#### Daemon-Restart Re-attach

On restart (`orch/daemon/main.py:_reattach_worktrees()`), the daemon queries non-terminal `BatchItem` rows with `worktree_compose_path` set:

```python
for batch_item in non_terminal_items:
    if compose_is_running(worktree_compose_path):
        log("Re-attached to running stack for %s", batch_item.id)
    elif compose_file_exists(worktree_compose_path):
        # Host restarted; stack vanished — re-run up()
        up_result = worktree_compose.up(batch_item, worktree_info)
    else:
        # Both gone — operator must investigate
```

No double `up()` for already-running stacks.

#### Full contract

See [`docs/IW_AI_Core_Worktree_Isolation.md`](docs/IW_AI_Core_Worktree_Isolation.md) for the complete reference.

### 4.5. Step Launch

```python
def _launch_next_step(self, item_id: str, worktree_info: dict):
    """Find and launch the next pending step for a work item."""
    step = self.db.query(WorkflowStep).filter(
        WorkflowStep.project_id == self.project_id,
        WorkflowStep.work_item_id == item_id,
        WorkflowStep.status == 'pending'
    ).order_by(WorkflowStep.step_number).first()

    if step is None:
        # All steps done — item is completed
        self._complete_item(item_id)
        return

    self._launch_step(step, worktree_info)

def _launch_step(self, step: WorkflowStep, worktree_info: dict):
    """Launch a single step: start process, record everything in DB."""
    worktree_path = worktree_info['path']
    cli_tool = self.project_config.cli_tool

    # Build the exact command
    if cli_tool == 'opencode':
        command = f"opencode run '/execute {step.work_item_id} {step.step_id}'"
    else:
        command = f"claude -p '/execute {step.work_item_id} {step.step_id}'"

    # Determine dynamic timeout
    timeout = self._get_timeout(step.step_type)

    # Create log file
    log_dir = Path(worktree_path) / 'ai-dev' / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f'{step.work_item_id}_{step.step_id}_run{self._next_run_number(step)}.log'

    # Launch the process
    with open(log_file, 'w') as log_fh:
        proc = subprocess.Popen(
            command, shell=True, cwd=worktree_path,
            stdout=log_fh, stderr=subprocess.STDOUT,
            start_new_session=True  # Detach from daemon's process group
        )

    # Record everything in DB
    run = StepRun(
        step_id=step.id,
        run_number=self._next_run_number(step),
        status='running',
        pid=proc.pid,
        pid_alive=True,
        command=command,
        worktree_path=worktree_path,
        cli_tool=cli_tool,
        log_file=str(log_file),
        started_at=datetime.utcnow(),
        last_heartbeat=datetime.utcnow(),
        timeout_secs=timeout,
    )
    self.db.add(run)

    step.status = 'in_progress'
    step.started_at = datetime.utcnow()
    self.db.commit()

    self._emit('step_launched', step.work_item_id,
               metadata={'step_id': step.step_id, 'pid': proc.pid, 'timeout': timeout})
```

**`start_new_session=True`**: This is critical. It detaches the agent process from the daemon's process group. If the daemon is killed with SIGTERM, the signal is NOT propagated to agent processes. They continue running independently.

### 4.6. Step Completion Handling

When the daemon detects a step has completed (via `iw step-done` updating the DB), it needs to decide what happens next:

```python
def _on_step_completed(self, step: WorkflowStep, item_id: str, worktree_info: dict):
    """Handle a step that just completed. Decide next action."""

    # Is there a next step?
    next_step = self.db.query(WorkflowStep).filter(
        WorkflowStep.project_id == self.project_id,
        WorkflowStep.work_item_id == item_id,
        WorkflowStep.step_number > step.step_number,
        WorkflowStep.status == 'pending'
    ).order_by(WorkflowStep.step_number).first()

    if next_step:
        self._launch_step(next_step, worktree_info)
    else:
        # All steps done
        self._complete_item(item_id)

def _complete_item(self, item_id: str):
    """Mark a work item as completed and add to merge queue."""
    item = self.db.query(WorkItem).filter(
        WorkItem.project_id == self.project_id,
        WorkItem.id == item_id
    ).one()
    item.status = 'completed'
    item.completed_at = datetime.utcnow()
    self.db.commit()
    self._emit('item_completed', item_id)
    # Merge queue will pick it up on the next cycle
```

### 4.7. Merge Queue

Merges completed items to main, one at a time per project.

```python
def process_merge_queue(self):
    """Merge completed batch items to main, sequentially."""
    # Find items ready to merge (completed, not yet merged)
    ready = self.db.query(BatchItem).filter(
        BatchItem.project_id == self.project_id,
        BatchItem.status == 'completed'
    ).order_by(BatchItem.started_at).all()

    if not ready:
        return

    # Check if a merge is already in progress
    merging = self.db.query(BatchItem).filter(
        BatchItem.project_id == self.project_id,
        BatchItem.status == 'merging'
    ).first()

    if merging:
        return  # Wait for current merge to finish

    # Merge the oldest completed item
    item = ready[0]
    self._merge_item(item)

### 4.7.2. Auto-merge Gate (CR-00036)

When `batch.auto_merge` is `false`, `BatchManager` parks successful items in `awaiting_merge_approval` instead of `completed`. The merge queue continues to pick only `completed` items, so parked items remain invisible to it until an operator releases them via `POST /actions/item/{id}/approve-merge` (dashboard) or `iw item approve-merge` (CLI). The next daemon poll cycle then picks the item up via the existing merge queue path.

**Stall-checker exemption**: `awaiting_merge_approval` is a *waiting-on-human* state — the stall monitor (driven by `IW_CORE_STALL_THRESHOLD`) MUST NOT auto-fail items in this state. Operators may legitimately leave items parked for days; the dashboard surfaces the wait via the existing `BatchItem.updated_at` timestamp.

def _merge_item(self, batch_item: BatchItem):
    """Squash-merge a completed item's worktree branch to main."""
    item_id = batch_item.work_item_id
    worktree_path = batch_item.worktree_info.get('path')

    if not worktree_path:
        batch_item.status = 'failed'
        batch_item.notes = "No worktree path — cannot merge"
        self.db.commit()
        return

    batch_item.status = 'merging'
    self.db.commit()
    self._emit('merge_started', item_id)

    try:
        result = subprocess.run(
            ['bash', str(self.config.executor_dir / 'worktree_commit.sh'),
             item_id, self.project_config.repo_root],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0:
            raise MergeError(result.stderr)

        batch_item.status = 'merged'
        batch_item.merged_at = datetime.utcnow()
        batch_item.merge_info = {'stdout': result.stdout[:1000]}
        self.db.commit()
        self._emit('item_merged', item_id)

        # Cleanup worktree
        self._cleanup_worktree(item_id, worktree_path)

    except (MergeError, subprocess.TimeoutExpired) as e:
        batch_item.status = 'failed'
        batch_item.notes = f"Merge failed: {e}"
        self.db.commit()
        self._emit('merge_conflict', item_id, message=str(e))

### 4.7.1. Migration Pipeline (CR-00021)

The merge queue runs a 4-step migration pipeline for each completed batch item, from newest to oldest: **Phase 0 (rebase)** → **Phase 1 (dry-run)** → **squash-merge** → **Phase 2 (apply)**. Phase 3 (rollback) fires only on Phase 2 failure. The pipeline is serialised per project — only one batch item is in the pipeline at a time.

#### Phase 0: Pre-merge rebase (CR-00021)

**Problem**: Parallel batches generate migrations off the same `down_revision`. When Batch A merges first and main advances, Batch B's migration points to a stale base. Git rebase alone does not rewrite string content inside migration files, so Batch B arrives at the merge queue with a stale `down_revision`, creating a second Alembic head. `MultipleHeadsError` fires at Phase 1 (or Phase 2), requiring manual `alembic merge`.

**Solution** (`orch/daemon/migration_rebase.py`): Before Phase 1, fetch main, rebase the batch's branch, identify the batch's own migration files via `git diff merge-base..HEAD`, rewrite any stale `down_revision` strings to point at main's current head, and commit the edit.

**Order of operations**:
- `git fetch origin main` — update origin/main ref
- `git rebase main` in the worktree — abort on conflict, return `migration_rebase_failed`
- `git diff $(git merge-base HEAD main)..HEAD --name-only --diff-filter=A -- orch/db/migrations/versions/` — identify batch's own files
- Parse each file's `revision` and `down_revision`; determine chain root via tempfile tempdir trick
- Rewrite stale `down_revision` (regex replace, preserve whitespace); commit if changes were made
- Write `PendingMigrationLog(phase='rebase', old_revision=...)` for each rewrite
- Return `RebaseResult(success, rebased, rewrites, ...)`

**Failure semantics**:
- Rebase conflict → `batch_item.status = migration_rebase_failed`, queue NOT frozen
- Rebased dry-run fails → `batch_item.status = migration_invalid` (Phase 1 failure), queue NOT frozen
- Phase 2 apply fails → rollback fires; only Phase 3 rollback failure freezes the queue (unchanged)

**Reference**: `RebaseResult` dataclass at `orch/daemon/migration_rebase.py:74`.

```
┌──────────────────────────────────────────────────────────────┐
│                   Migration Pipeline Flow                     │
│                                                               │
│  ┌─────────┐    ┌────────────┐    ┌────────────┐    ┌─────┐ │
│  │ Phase 0 │───▶│  Phase 1   │───▶│  Squash    │───▶│Phase│ │
│  │ Rebase  │    │  Dry-run   │    │  Merge     │    │  2  │ │
│  │(CR-00021)   │(worktree)  │    │            │    │Apply│ │
│  └─────────┘    └────────────┘    └────────────┘    └─────┘ │
│      │                │                               │     │
│      ▼                ▼                               ▼     │
│  on conflict:     on failure:                     on fail:  │
│  migration_       migration_                      rollback  │
│  rebase_failed    invalid                          (Phase3)│
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

#### Phase 1: Pre-merge dry-run

Phase 1 runs **after Phase 0** and uses the **worktree's migrations directory** (not the daemon's main-repo migrations directory). This exercises the full post-squash-merge chain — including the batch's own migration files with their rewritten `down_revision` — before any content touches main.

The dry-run spins a short-lived PostgreSQL testcontainer, applies all pending revisions via `alembic upgrade head`, runs integration checks, then tears down. On failure the batch item is marked `migration_invalid` and main is untouched.

See `orch/daemon/migration_pipeline.py` (Phase 1 entry: `run_pre_merge_dry_run`).

#### Phase 2: Post-merge apply

After squash-merge, Phase 2 applies migrations to the live DB. If the chain now has multiple heads (should not happen after Phase 0 + Phase 1), `MultipleHeadsError` fires and Phase 3 rollback is triggered. See `orch/daemon/migration_pipeline.py` (`run_post_merge_apply`).

#### Phase 3: Rollback

If Phase 2 fails, Phase 3 attempts one `alembic downgrade -1`. If rollback itself fails, the queue is frozen and an operator alert is emitted. See `orch/daemon/migration_pipeline.py` (`run_rollback`).

#### Migration Pipeline Failure Matrix

| Failure point | `batch_item.status` | Queue frozen? | Recovery |
|---|---|---|---|
| Compose stack `up()` failure | `setup_failed` | **No** | User can re-trigger; compose `down()` called |
| Phase 0 rebase conflict | `migration_rebase_failed` | **No** | Next poll cycle picks up next batch |
| Phase 0 rewrite failure | `migration_rebase_failed` | **No** | Next poll cycle picks up next batch |
| Phase 1 dry-run failure | `migration_invalid` | **No** | User can re-trigger after fixing |
| Phase 2 apply failure | `migration_rolled_back` | **No** | Rollback fires; user can investigate |
| Phase 3 rollback failure | `failed` | **Yes** | Operator intervention required |

**Recovery-testing cross-link (F-00089):** deterministic fault-injection coverage for these daemon failure paths now lives in `tests/integration/daemon_chaos/` (worktree-setup failure, fix-cycle cap exhaustion, agent stall, squash-merge conflict, migration-rebase failure). See `docs/IW_AI_Core_Testing_Strategy.md` §2 **Layer 9 — Daemon chaos** and §5 gate rows (`make daemon-chaos-smoke`, `make daemon-chaos-full`).

### 4.8. Batch Completion

```python
def _check_batch_completion(self, batch: Batch, items: list[BatchItem]):
    """Check if all items in a batch are in terminal state."""
    statuses = [i.status for i in items]

    if all(s == 'merged' for s in statuses):
        batch.status = 'completed'
        batch.completed_at = datetime.utcnow()
        self.db.commit()
        self._emit('batch_completed', batch.id)

    elif all(s in ('merged', 'failed', 'skipped') for s in statuses):
        batch.status = 'completed_with_errors'
        batch.completed_at = datetime.utcnow()
        failed = [i.work_item_id for i in items if i.status == 'failed']
        self.db.commit()
        self._emit('batch_completed_with_errors', batch.id,
                    metadata={'failed_items': failed})

    # else: some items still executing — not done yet
```

### 4.8.1. Auto-Amend Scope Violations (CR-00087)
When a fix-cycle agent edits a file outside `scope.allowed_paths`, the daemon marks the cycle `escalated` and emits `scope_violation_escalation` as usual. If the project's `.iw-orch.json` configures an `auto_amend_scope` block with non-empty `auto_allow_patterns`, the daemon evaluates whether every violation matches one of those patterns and whether the total count is within `max_paths`. If so, it auto-amends the manifest and restarts the step inline without waiting for operator input.

**Decision conditions** (all must hold):
1. `auto_amend_scope.auto_allow_patterns` is non-empty (feature opt-in, default off).
2. Every violation in `scope_violations` matches at least one pattern — the same `scope_match` algorithm the violation detector uses.
3. `len(violations) <= max_paths` (or `max_paths` is null).

**Effect**: both `scope_violation_escalation` **and** `scope_auto_amended` events are emitted to preserve a full audit trail. The step is re-queued with a new `StepRun`, its `status` reset to `pending`, and any `WorkItemStatus.failed` parent transitions to `in_progress`. A second `db.commit()` is issued inside the auto-amend helper.

**Configuration** (`.iw-orch.json`, per-project):
```jsonc
{
  "auto_amend_scope": {
    "auto_allow_patterns": ["tests/**", "**/*.md", "docs/**", "ai-dev/**"],
    "max_paths": 10
  }
}
```

---

## 4.9. Cross-batch Overlap Gate (Configurable)

The daemon prevents two items in different batches from running concurrently when their `impacted_paths` overlap on non-test source files (F-00076). The gate is unconditional by default. `overlap_gate` makes it per-project configurable.

### Role

When a candidate item is about to launch, `scope_overlap.find_blocking_items()` computes the set of in-flight items whose `impacted_paths` intersect the candidate's. If overlaps exist, the candidate is held — it does not consume a `max_parallel` slot — until the blockers complete or the operator changes the policy.

### `.iw-orch.json` Schema

```json
{
  "overlap_gate": {
    "block_on_overlap": ["**/*"],
    "allow_on_overlap": [
      "tests/**",
      "test/**",
      "__tests__/**",
      "**/*conftest*",
      "**/*.test.*",
      "**/*.spec.*"
    ]
  }
}
```

| Field | Type | Default | Effect |
|-------|------|---------|--------|
| `block_on_overlap` | `list[glob]` | `["**/*"]` | Item is held when any glob matches an in-flight item's `impacted_paths`. Empty list disables the gate entirely. |
| `allow_on_overlap` | `list[glob]` | test-pattern list above | Applied **per conflicting glob** after the intersection step. A glob matched by any allow pattern is dropped. |

**Allow precedence semantics**: after `find_blocking_items` returns the list of conflicting globs (from the candidate's side), each glob is filtered against `allow_on_overlap`. A glob that matches any allow pattern is dropped. If the filtered list is empty, the candidate launches.

### Decision Tree

```
┌─────────────────────────────────────────────────────────────┐
│  Candidate item ready to launch                             │
└──────────────────────┬──────────────────────────────────────┘
                       ▼
        find_blocking_items(candidate, in_flight,
                            block_patterns, allow_patterns)
                       │
                       ▼
        Overlapping globs list ──► Filter against allow_on_overlap
                       │                    │
                       ▼                    ▼
              ┌───────────────┐    ┌───────────────────────┐
              │ non-empty?    │    │  glob matched by any  │
              │               │    │  allow pattern → drop │
              └───────┬───────┘    └───────────────────────┘
                      │                      │
                      ▼                      ▼
          ┌───────────────────┐    ┌──────────────────┐
          │ HOLD candidate    │    │ Dropped globs    │
          │ Emit              │    │ removed from list│
          │ item_held_for_    │    └────────┬─────────┘
          │ scope (per        │             ▼
          │  blocking item)   │    ┌──────────────────┐
          └───────────────────┘    │ Remaining non-   │
                                  │ empty?            │
                                  └───────┬──────────┘
                                          │          │
                              ┌───────────┘          └──────────┐
                              ▼                                      ▼
                    ┌──────────────────┐              ┌────────────────────────┐
                    │ HOLD candidate   │              │ LAUNCH candidate       │
                    │ Emit item_held_   │              │ Emit                   │
                    │ for_scope        │              │ item_overlap_allowed_  │
                    │                  │              │ by_policy (once)       │
                    └──────────────────┘              └────────────────────────┘
```

### Events

**`item_held_for_scope`** — emitted per blocking item per poll cycle while the candidate is held.

```python
DaemonEvent(
    project_id=project_id,
    event_type='item_held_for_scope',
    entity_id=candidate_item_id,
    message="Item held: overlapping scope with {blocking_item_id}",
    metadata={
        'blocking_item_id': blocking_item_id,
        'conflicting_globs': ['dashboard/**/*.js', 'orch/daemon/*.py']
    }
)
```

**`item_overlap_allowed_by_policy`** — emitted once when a launch decision is reached and the filtered-overlap list is empty but the default-strict policy (block everything) would have held the item. Does not fire when the default policy would also have allowed the item.

```python
DaemonEvent(
    project_id=project_id,
    event_type='item_overlap_allowed_by_policy',
    entity_id=candidate_item_id,
    message="Item launched despite overlap by policy",
    metadata={
        'candidate_item_id': candidate_item_id,
        'in_flight_item_ids': ['I-00087', 'I-00088'],
        'matched_allow_patterns': ['docs/**'],
        'dropped_block_globs': ['docs/Foo.md', 'docs/Bar.md']
    }
)
```

### SIGHUP Reload

Operator edits `.iw-orch.json`, runs `./ai-core.sh daemon reload`. The daemon receives SIGHUP, re-reads the file, and the next poll cycle uses the new `overlap_gate` policy. In-flight items (already launched) are unaffected — the policy is evaluated only at launch decision time.

### Operator Guidance

If you relax `overlap_gate` for a directory, consider enabling `scope_gate_enabled` to catch divergence at merge time. The two flags are independent today; they may be coupled in a future CR. See [`ai-dev/active/AUTO_MERGE_RESOLUTION.md`](ai-dev/active/AUTO_MERGE_RESOLUTION.md) for the motivation behind relaxing the cross-batch gate.

---

## 5. Dashboard Action Handlers

These are called when the user clicks action buttons in the dashboard. They mutate DB state; the daemon picks up changes on the next poll cycle.

### 5.1. Kill a Running Step

```python
def kill_step(project_id: str, item_id: str, step_number: int):
    """Kill a running step. Called from dashboard API."""
    step = get_step(project_id, item_id, step_number)
    run = get_active_run(step)

    if run.status != 'running':
        raise InvalidAction(f"Step is not running (status: {run.status})")

    # Send SIGTERM immediately (don't wait for daemon poll)
    if run.pid and is_pid_alive(run.pid):
        os.kill(run.pid, signal.SIGTERM)

    run.status = 'killed'
    run.completed_at = datetime.utcnow()
    run.duration_secs = (run.completed_at - run.started_at).total_seconds()
    run.error_message = "Killed by user from dashboard"

    step.status = 'failed'
    step.completed_at = datetime.utcnow()

    db.commit()
    emit_event('step_killed', project_id, item_id)
```

### 5.2. Restart a Failed Step

```python
def restart_step(project_id: str, item_id: str, step_number: int):
    """Restart a failed step. Creates a new step_run, daemon launches it."""
    step = get_step(project_id, item_id, step_number)

    if step.status not in ('failed', 'skipped'):
        raise InvalidAction(f"Cannot restart: step status is '{step.status}'")

    # Get the last run to copy command and worktree info
    last_run = get_last_run(step)

    # Create a new pending run
    new_run = StepRun(
        step_id=step.id,
        run_number=last_run.run_number + 1,
        status='pending',
        command=last_run.command,
        worktree_path=last_run.worktree_path,
        cli_tool=last_run.cli_tool,
        timeout_secs=last_run.timeout_secs,
    )
    db.add(new_run)

    # Reset step status
    step.status = 'pending'
    step.started_at = None
    step.completed_at = None

    # Ensure work item is in_progress
    item = get_work_item(project_id, item_id)
    if item.status == 'failed':
        item.status = 'in_progress'

    db.commit()
    emit_event('step_restarted', project_id, item_id)
    # Daemon picks up the pending run on next poll cycle
```

### 5.3. Skip a Step

```python
def skip_step(project_id: str, item_id: str, step_number: int):
    """Skip a failed step. Marks as skipped, workflow advances."""
    step = get_step(project_id, item_id, step_number)

    if step.status not in ('failed', 'needs_fix'):
        raise InvalidAction(f"Cannot skip: step status is '{step.status}'")

    step.status = 'skipped'
    step.completed_at = datetime.utcnow()

    db.commit()
    emit_event('step_skipped', project_id, item_id)
    # Daemon will launch the next step on the next poll cycle
```

### 5.4. Restart from Step N

```python
def restart_from_step(project_id: str, item_id: str, from_step_number: int):
    """Reset all steps >= N to pending. Daemon re-runs from step N."""
    steps = db.query(WorkflowStep).filter(
        WorkflowStep.project_id == project_id,
        WorkflowStep.work_item_id == item_id,
        WorkflowStep.step_number >= from_step_number
    ).all()

    for step in steps:
        step.status = 'pending'
        step.started_at = None
        step.completed_at = None
        step.report_file = None

    # Create a pending run for the first step
    first_step = min(steps, key=lambda s: s.step_number)
    last_run = get_last_run(first_step)
    if last_run:
        new_run = StepRun(
            step_id=first_step.id,
            run_number=last_run.run_number + 1,
            status='pending',
            command=last_run.command,
            worktree_path=last_run.worktree_path,
            cli_tool=last_run.cli_tool,
            timeout_secs=last_run.timeout_secs,
        )
        db.add(new_run)

    # Ensure work item is in_progress
    item = get_work_item(project_id, item_id)
    item.status = 'in_progress'

    db.commit()
    emit_event('step_restarted', project_id, item_id,
               metadata={'from_step': from_step_number, 'steps_reset': len(steps)})
```

---

## 6. Project Configuration Reload

The daemon re-reads `projects.toml` when the file's mtime changes (checked every poll cycle). This allows adding, removing, or disabling projects without restarting the daemon.

```python
def _reload_projects_if_stale(self):
    """Re-read projects.toml if the file has been modified."""
    current_mtime = self.config.projects_toml.stat().st_mtime
    if current_mtime == self._projects_mtime:
        return

    self._projects_mtime = current_mtime
    logger.info("projects.toml changed — reloading")

    new_config = load_projects_toml(self.config.projects_toml)

    # Detect additions
    for pid, cfg in new_config.items():
        if pid not in self.projects:
            logger.info("New project discovered: %s", pid)
            self.projects[pid] = cfg
            self.managers[pid] = BatchManager(pid, cfg, self.db)
            self._emit('project_discovered', pid)

    # Detect removals / disablement
    for pid in list(self.projects.keys()):
        if pid not in new_config:
            logger.info("Project removed: %s", pid)
            del self.projects[pid]
            del self.managers[pid]
        elif not new_config[pid].enabled and self.projects[pid].enabled:
            logger.info("Project disabled: %s", pid)
            self.projects[pid].enabled = False
            self._emit('project_disabled', pid)
```

SIGHUP also triggers a reload:

```python
def _setup_signal_handlers(self):
    signal.signal(signal.SIGTERM, self._handle_shutdown)
    signal.signal(signal.SIGINT, self._handle_shutdown)
    signal.signal(signal.SIGHUP, self._handle_reload)

def _handle_reload(self, signum, frame):
    logger.info("SIGHUP received — reloading projects")
    self._reload_projects_if_stale()  # Force reload regardless of mtime
```

---

## 7. Timeout Configuration

Dynamic timeouts are resolved per step type with a layered override system:

```python
# Priority order (highest to lowest):
# 1. Step-level override (in workflow_steps.config JSONB)
# 2. Project-level override (in .iw-orch.json timeout_overrides)
# 3. Platform defaults (below)

PLATFORM_DEFAULTS = {
    'implementation':           2700,   # 45 min
    'code_review':              1800,   # 30 min
    'code_review_fix':          2700,   # 45 min
    'code_review_final':        2400,   # 40 min
    'code_review_fix_final':    2700,   # 45 min
    'quality_validation':        600,   # 10 min
    'qv_fix':                   1800,   # 30 min
    'browser_verification':      900,   # 15 min
}

def _get_timeout(self, step_type: str) -> int:
    """Resolve timeout for a step type using the override chain."""
    # Check project overrides first
    overrides = self.project_config.config.get('timeout_overrides', {})
    if step_type in overrides:
        return overrides[step_type]
    return PLATFORM_DEFAULTS.get(step_type, 1800)  # 30 min fallback
```

---

## 8. Orphan Detection (Startup)

On startup, the daemon checks for inconsistencies between DB state and filesystem reality:

```python
def _startup_health_check(self):
    """Detect and report orphans from previous crashes."""

    # 1. Running step_runs with dead PIDs
    running = self.db.query(StepRun).filter(StepRun.status == 'running').all()
    for run in running:
        if not self._is_pid_alive(run.pid):
            run.status = 'failed'
            run.error_message = "Daemon restarted — process was dead (orphan recovery)"
            run.completed_at = datetime.utcnow()
            self._emit('orphan_detected', metadata={
                'type': 'dead_pid', 'pid': run.pid, 'step_id': run.step_id
            })
    self.db.commit()

    # 2. Worktrees on disk with no matching executing batch_item
    for project_id, config in self.projects.items():
        worktree_base = Path(config.repo_root) / config.worktree_base
        if not worktree_base.exists():
            continue
        for entry in worktree_base.iterdir():
            if not entry.is_dir():
                continue
            item_id = entry.name
            batch_item = self.db.query(BatchItem).filter(
                BatchItem.project_id == project_id,
                BatchItem.work_item_id == item_id,
                BatchItem.status.in_(['setting_up', 'executing'])
            ).first()
            if not batch_item:
                logger.warning("Orphaned worktree: %s (no active batch_item)", entry)
                self._emit('orphan_detected', project_id, metadata={
                    'type': 'orphaned_worktree', 'path': str(entry), 'item_id': item_id
                })

    logger.info("Startup health check complete")
```

The daemon does NOT automatically clean up orphaned worktrees — it reports them. The user decides whether to delete them or investigate.

---

## 9. Sleep with Interruption

The daemon sleep between poll cycles must be interruptible by signals:

```python
def _sleep(self, seconds: int):
    """Sleep for the specified duration, interruptible by signals."""
    # Use Event.wait() instead of time.sleep() so SIGTERM/SIGHUP
    # wake us immediately instead of waiting for the full interval.
    self._wake_event.wait(timeout=seconds)
    self._wake_event.clear()

def _handle_shutdown(self, signum, frame):
    self._running = False
    self._wake_event.set()  # Wake from sleep immediately

def _handle_reload(self, signum, frame):
    self._wake_event.set()  # Wake from sleep to process reload
```

---

## 10. Summary: What the Daemon Guarantees

| Guarantee | How |
|-----------|-----|
| **Never loses track of work** | All state in DB. Crash recovery reads DB on startup. |
| **Never leaves zombie processes** | PID health check every poll cycle. Dead PIDs detected and marked. |
| **Never corrupts DB state** | All writes are transactional. Partial failures roll back. |
| **Never blocks on one project** | Per-project try/except in the main loop. One project's error doesn't block others. |
| **Never kills agents on shutdown** | `start_new_session=True` detaches agents. SIGTERM to daemon doesn't propagate. |
| **Never exceeds parallelism limits** | Executing count checked before each launch. |
| **Never merges concurrently** | One merge at a time per project (merge queue). |
| **Always recoverable** | Every step_run has command + worktree_path. Restart = re-run the stored command. |
| **Always observable** | Every action emits a daemon_event. Dashboard queries events for display. |

### Migration safety net

`tests/integration/test_migration_roundtrip.py` runs an upgrade/downgrade/upgrade cycle for the **latest 3** alembic revisions on each test run. The window is dynamic — adding a new migration auto-shifts it without code edits.

`alembic check` runs on every PR via `.github/workflows/schema-validation.yml` to catch drift between model definitions and migrations.

Older revisions are not roundtripped on every PR (pragmatic choice — they were verified at the time via the daemon's pre-merge dry-run).
