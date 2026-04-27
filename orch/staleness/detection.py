"""orch.staleness.detection — Process and container detection engine.

Implements four detection strategies (port, pidfile, docker, pgrep) and
cross-checks process cwd against the project's repo_root to scope detection
to the main worktree only (not agent worktrees).

All shell-outs use subprocess.run with explicit 2s timeout and check=False.
Failures always return None and log — they never raise to callers.
"""

from __future__ import annotations

import contextlib
import logging
import os
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from orch.staleness.config import ServiceDetect

logger = logging.getLogger(__name__)

# Patchable proc root for testing
PROC_ROOT = Path("/proc")

_SUBPROCESS_TIMEOUT = 2  # seconds for port/pid detection
_DOCKER_TIMEOUT = 2  # seconds for docker inspect calls


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _pid_alive(pid: int) -> bool:
    """Return True if the process is alive (os.kill(pid, 0) succeeds)."""
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def _iter_proc_pids() -> list[int]:
    """Return a list of integer PIDs from PROC_ROOT directories."""
    pids: list[int] = []
    try:
        for entry in PROC_ROOT.iterdir():
            with contextlib.suppress(ValueError):
                pids.append(int(entry.name))
    except OSError:
        pass
    return pids


def _read_cmdline(pid: int) -> str:
    """Read /proc/<pid>/cmdline and return as a space-joined string."""
    try:
        raw = (PROC_ROOT / str(pid) / "cmdline").read_bytes()
        return raw.replace(b"\x00", b" ").decode(errors="replace").strip()
    except OSError:
        return ""


def _boot_time_epoch(proc_root: Path = PROC_ROOT) -> float:
    """Return the system boot time as a Unix epoch float.

    Reads /proc/uptime (seconds since boot) and subtracts from time.time().
    This avoids reading /proc/stat which requires root on some systems.
    """
    import time

    uptime_path = proc_root / "uptime"
    try:
        uptime_str = uptime_path.read_text().split()[0]
        uptime_secs = float(uptime_str)
        return time.time() - uptime_secs
    except (OSError, ValueError, IndexError) as exc:
        raise OSError(f"Cannot read boot time from {uptime_path}: {exc}") from exc


# ---------------------------------------------------------------------------
# is_cwd_under
# ---------------------------------------------------------------------------


def is_cwd_under(pid: int, repo_root: Path) -> bool:
    """Return True when /proc/<pid>/cwd resolves inside repo_root.

    A process is only counted as "the project's process" if its cwd is
    inside the main worktree. Agent worktrees (which are subdirectories of
    the project's .worktrees/ dir but outside repo_root itself) would need
    a separate check; here we just confirm the cwd is anywhere under repo_root.

    Returns False on any I/O error (process gone, no permission, etc.).
    """
    cwd_link = PROC_ROOT / str(pid) / "cwd"
    try:
        cwd = cwd_link.resolve()
        repo_resolved = repo_root.resolve()
        return cwd == repo_resolved or repo_resolved in cwd.parents
    except OSError:
        return False


# ---------------------------------------------------------------------------
# read_process_start_time
# ---------------------------------------------------------------------------


def read_process_start_time(pid: int) -> datetime:
    """Return the wall-clock start time of a process in UTC.

    Reads field 22 (starttime, 0-indexed at 21) from /proc/<pid>/stat —
    this is the number of clock ticks since system boot. Converts to
    wall-clock time using /proc/uptime and os.sysconf("SC_CLK_TCK").

    Raises:
        OSError: If /proc/<pid>/stat cannot be read.
        ValueError: If the stat file cannot be parsed.
    """
    stat_path = PROC_ROOT / str(pid) / "stat"
    stat_text = stat_path.read_text()

    # The process name in parentheses may contain spaces and parens, so we
    # strip it out before splitting.
    # Find the last ')' to locate where the fixed fields resume.
    rparen = stat_text.rfind(")")
    if rparen == -1:
        raise ValueError(f"Cannot parse /proc/{pid}/stat: no closing ')' found")

    rest = stat_text[rparen + 1 :].split()
    # After '(comm)' the fields are: state ppid pgroup sess tty_nr tpgid
    # flags minflt cminflt majflt cmajflt utime stime cutime cstime
    # priority nice num_threads itrealvalue starttime
    # That's 20 more fields, so rest[19] is starttime.
    if len(rest) < 20:
        raise ValueError(
            f"Cannot parse /proc/{pid}/stat: expected >= 20 fields after comm, got {len(rest)}"
        )

    starttime_jiffies = int(rest[19])
    clk_tck = os.sysconf("SC_CLK_TCK")
    starttime_secs = starttime_jiffies / clk_tck

    boot_epoch = _boot_time_epoch(PROC_ROOT)
    wall_epoch = boot_epoch + starttime_secs

    return datetime.fromtimestamp(wall_epoch, tz=UTC)


# ---------------------------------------------------------------------------
# read_container_start_time
# ---------------------------------------------------------------------------


def read_container_start_time(container_id: str) -> datetime:
    """Return the start time of a Docker container in UTC.

    Invokes ``docker inspect --format '{{.State.StartedAt}}'`` and parses
    the ISO 8601 timestamp.

    Raises:
        RuntimeError: If docker inspect fails or output cannot be parsed.
    """
    try:
        result = subprocess.run(  # noqa: S603,S607  system-installed CLI; args are a list, no shell injection risk
            ["docker", "inspect", container_id, "--format", "{{.State.StartedAt}}"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=_DOCKER_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"docker inspect timed out for container {container_id!r}") from exc

    if result.returncode != 0:
        raise RuntimeError(f"docker inspect failed for {container_id!r}: {result.stderr.strip()}")

    raw_ts = result.stdout.strip()
    # Docker timestamps are like "2024-01-15T10:30:00.123456789Z"
    # Strip sub-second nanoseconds: keep up to 6 fractional digits.
    return _parse_docker_timestamp(raw_ts)


def _parse_docker_timestamp(raw: str) -> datetime:
    """Parse a Docker ISO 8601 timestamp with optional nanoseconds."""
    # Normalise nanoseconds to microseconds (Python datetime supports up to 6 digits)
    raw = raw.rstrip("Z").rstrip("z")
    if "." in raw:
        base, frac = raw.split(".", 1)
        frac = frac[:6].ljust(6, "0")
        raw = f"{base}.{frac}"
    dt = datetime.fromisoformat(raw)
    return dt.replace(tzinfo=UTC)


# ---------------------------------------------------------------------------
# find_running_container — docker detect
# ---------------------------------------------------------------------------


def find_running_container(detect: ServiceDetect) -> str | None:
    """Return the container name/id if it is currently running, else None.

    Invokes ``docker inspect <container> --format '{{.State.Running}} {{.Created}}'``.
    Returns None on any failure (container not found, docker unavailable, etc.).
    """
    if detect.type != "docker" or not detect.container:
        return None

    try:
        result = subprocess.run(  # noqa: S603,S607  system-installed CLI; args are a list, no shell injection risk
            [  # noqa: S607
                "docker",
                "inspect",
                detect.container,
                "--format",
                "{{.State.Running}} {{.Created}}",
            ],
            capture_output=True,
            text=True,
            timeout=_DOCKER_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired:
        logger.warning(
            "[staleness] docker inspect timed out for container %r",
            detect.container,
        )
        return None
    except OSError as exc:
        logger.warning("[staleness] docker inspect failed: %s", exc)
        return None

    if result.returncode != 0:
        logger.debug(
            "[staleness] docker inspect returned %d for %r: %s",
            result.returncode,
            detect.container,
            result.stderr.strip(),
        )
        return None

    parts = result.stdout.strip().split(None, 1)
    if not parts:
        return None

    running = parts[0].lower()
    if running == "true":
        return detect.container

    return None


# ---------------------------------------------------------------------------
# _parse_ss_pids — parse ss -ltnp output
# ---------------------------------------------------------------------------

# Matches: users:(("proc_name",pid=1234,fd=5)) or users:(("proc",pid=1234,fd=5),("p",pid=6789,fd=1))
_SS_PID_RE = re.compile(r"pid=(\d+)")


def _parse_ss_pids(output: str, port: int) -> list[int]:
    """Extract PIDs from ``ss -ltnp`` output for a given port."""
    pids: list[int] = []
    port_str = f":{port}"
    for line in output.splitlines():
        if port_str not in line:
            continue
        for m in _SS_PID_RE.finditer(line):
            pid = int(m.group(1))
            if pid not in pids:
                pids.append(pid)
    return pids


# ---------------------------------------------------------------------------
# find_running_pid — main entry point
# ---------------------------------------------------------------------------


def find_running_pid(detect: ServiceDetect, repo_root: Path) -> int | None:
    """Return the PID of the running service, or None if not detected.

    Dispatches to the appropriate strategy based on detect.type:
    - ``port``: uses ``ss -ltnp`` to find the listening PID.
    - ``pidfile``: reads the PID from the file; validates it is alive.
    - ``pgrep``: scans /proc cmdlines for a regex match.
    - ``docker``: not handled here — use find_running_container instead.

    In all cases, cross-checks that the PID's cwd is inside repo_root
    to ensure we're looking at the main worktree process, not an agent.

    Returns None on any failure.
    """
    if detect.type == "pidfile":
        return _find_pid_by_pidfile(detect, repo_root)
    if detect.type == "port":
        return _find_pid_by_port(detect, repo_root)
    if detect.type == "pgrep":
        return _find_pid_by_pgrep(detect, repo_root)
    # docker type is handled by find_running_container; log and return None
    logger.debug(
        "[staleness] find_running_pid called with detect.type=%r"
        " — use find_running_container instead",
        detect.type,
    )
    return None


def _find_pid_by_pidfile(detect: ServiceDetect, repo_root: Path) -> int | None:
    """PID file strategy: read PID from file, validate alive + cwd."""
    if not detect.path:
        return None

    pid_path = repo_root / detect.path
    if not pid_path.exists():
        logger.debug("[staleness] pidfile %s not found", pid_path)
        return None

    try:
        pid = int(pid_path.read_text().strip())
    except (ValueError, OSError) as exc:
        logger.warning("[staleness] Cannot read pidfile %s: %s", pid_path, exc)
        return None

    if not _pid_alive(pid):
        logger.debug("[staleness] pidfile %s holds stale PID %d", pid_path, pid)
        return None

    if not is_cwd_under(pid, repo_root):
        logger.debug(
            "[staleness] PID %d from %s has cwd outside repo_root %s — ignoring",
            pid,
            pid_path,
            repo_root,
        )
        return None

    return pid


def _find_pid_by_port(detect: ServiceDetect, repo_root: Path) -> int | None:
    """Port strategy: run ss -ltnp and find PID listening on the port."""
    if detect.port is None:
        return None

    try:
        result = subprocess.run(  # noqa: S603,S607  system-installed CLI; args are a list, no shell injection risk
            ["ss", "-ltnp"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.warning("[staleness] ss -ltnp failed: %s", exc)
        return None

    pids = _parse_ss_pids(result.stdout, detect.port)
    if not pids:
        return None

    # Prefer a PID whose cwd is inside repo_root; if multiple, take the first.
    for pid in pids:
        if _pid_alive(pid) and is_cwd_under(pid, repo_root):
            return pid

    logger.debug(
        "[staleness] port %d has listener(s) %s but none have cwd inside %s",
        detect.port,
        pids,
        repo_root,
    )
    return None


def _find_pid_by_pgrep(detect: ServiceDetect, repo_root: Path) -> int | None:
    """Pgrep strategy: scan /proc cmdlines for a regex match.

    When multiple processes match, returns the oldest by start time and
    logs a warning (the user should prefer pidfile or port for unambiguous results).
    """
    if not detect.pattern:
        return None

    try:
        pattern = re.compile(detect.pattern)
    except re.error as exc:
        logger.warning("[staleness] invalid pgrep pattern %r: %s", detect.pattern, exc)
        return None

    matches: list[int] = []
    for pid in _iter_proc_pids():
        cmdline = _read_cmdline(pid)
        if not cmdline:
            continue
        if pattern.search(cmdline) and _pid_alive(pid) and is_cwd_under(pid, repo_root):
            matches.append(pid)

    if not matches:
        return None

    if len(matches) == 1:
        return matches[0]

    # Multiple matches — pick the oldest by start time.
    logger.warning(
        "[staleness] pgrep pattern %r matched %d PIDs %s in %s — using oldest",
        detect.pattern,
        len(matches),
        matches,
        repo_root,
    )

    oldest_pid: int | None = None
    oldest_start: float = float("inf")
    for pid in matches:
        try:
            start = read_process_start_time(pid)
            epoch = start.timestamp()
            if epoch < oldest_start:
                oldest_start = epoch
                oldest_pid = pid
        except Exception as exc:  # noqa: BLE001
            logger.debug("[staleness] Cannot read start time for PID %d: %s", pid, exc)

    return oldest_pid if oldest_pid is not None else matches[0]
