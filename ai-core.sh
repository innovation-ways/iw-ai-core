#!/usr/bin/env bash
# =============================================================================
# ai-core.sh — IW AI Core management
#
# Usage (interactive):  ./ai-core.sh
# Usage (CLI):          ./ai-core.sh start
#                       ./ai-core.sh daemon status
#                       ./ai-core.sh --status
# =============================================================================

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# =============================================================================
# LOAD .env
# =============================================================================

load_env() {
  if [[ -f "$SCRIPT_DIR/.env" ]]; then
    local tmp_env
    tmp_env=$(mktemp)
    tr -d '\r' < "$SCRIPT_DIR/.env" > "$tmp_env"

    # Preserve variables already set in the caller's environment
    local -a _pre_keys=()
    local -A _pre_vals=()
    local _line _key
    while IFS= read -r _line || [[ -n "$_line" ]]; do
      [[ "$_line" =~ ^[[:space:]]*(#|$) ]] && continue
      [[ "$_line" =~ ^([A-Za-z_][A-Za-z_0-9]*)= ]] || continue
      _key="${BASH_REMATCH[1]}"
      if [[ -v "$_key" ]]; then
        _pre_keys+=("$_key")
        _pre_vals["$_key"]="${!_key}"
      fi
    done < "$tmp_env"

    set -a
    # shellcheck disable=SC1090
    source "$tmp_env"
    set +a
    rm -f "$tmp_env"

    for _key in "${_pre_keys[@]}"; do
      export "$_key=${_pre_vals[$_key]}"
    done
  fi
}

load_env

# =============================================================================
# CONFIG (defaults mirror .env.example)
# =============================================================================

DB_HOST="${IW_CORE_DB_HOST:-localhost}"
DB_PORT="${IW_CORE_DB_PORT:-5433}"
DB_NAME="${IW_CORE_DB_NAME:-iw_orch}"
DB_USER="${IW_CORE_DB_USER:-iw_orch}"
DB_PASSWORD="${IW_CORE_DB_PASSWORD:-iw_orch_dev}"
DASHBOARD_PORT="${IW_CORE_DASHBOARD_PORT:-9900}"
DAEMON_PID_FILE="${IW_CORE_PID_FILE:-.daemon.pid}"
DAEMON_LOG_FILE="${IW_CORE_LOG_FILE:-./logs/daemon.log}"
DASHBOARD_PID_FILE=".dashboard.pid"
DASHBOARD_LOG_FILE="./logs/dashboard.log"

# =============================================================================
# COLORS & OUTPUT HELPERS
# =============================================================================

RED=$'\033[0;31m'
GREEN=$'\033[0;32m'
YELLOW=$'\033[1;33m'
BLUE=$'\033[0;34m'
CYAN=$'\033[0;36m'
BOLD=$'\033[1m'
DIM=$'\033[2m'
NC=$'\033[0m'

print_ok()   { echo -e "  ${GREEN}✓${NC}  $*"; }
print_err()  { echo -e "  ${RED}✗${NC}  $*"; }
print_warn() { echo -e "  ${YELLOW}!${NC}  $*"; }
print_info() { echo -e "  ${CYAN}→${NC}  $*"; }
print_dim()  { echo -e "  ${DIM}$*${NC}"; }

print_header() {
  echo ""
  echo -e "${BOLD}${BLUE}=== $1 ===${NC}"
  echo ""
}

confirm() {
  local prompt="${1:-Are you sure?}"
  echo ""
  read -r -p "  ${YELLOW}${prompt} [y/N]${NC} " answer
  case "$answer" in
    [yY][eE][sS]|[yY]) return 0 ;;
    *) return 1 ;;
  esac
}

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

pid_alive() {
  local pid="$1"
  [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

read_pid() {
  local file="$1"
  if [[ -f "$file" ]]; then
    cat "$file" 2>/dev/null || true
  fi
}

port_listening() {
  ss -tlnp "sport = :$1" 2>/dev/null | grep -q LISTEN
}

db_ready() {
  if command -v pg_isready &>/dev/null; then
    PGPASSWORD="$DB_PASSWORD" pg_isready \
      -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
      -q 2>/dev/null
  else
    nc -z -w3 "$DB_HOST" "$DB_PORT" &>/dev/null
  fi
}

wait_for_port() {
  local port="$1" label="$2" attempts="${3:-15}"
  local i=0
  while ! port_listening "$port"; do
    i=$((i + 1))
    if [[ $i -ge $attempts ]]; then
      print_err "$label did not come up on port $port after ${attempts}s"
      return 1
    fi
    sleep 1
  done
}

wait_for_db() {
  local attempts="${1:-20}"
  local i=0
  while ! db_ready; do
    i=$((i + 1))
    if [[ $i -ge $attempts ]]; then
      print_err "Database not ready after ${attempts}s"
      return 1
    fi
    sleep 1
  done
}

ensure_log_dir() {
  mkdir -p "$(dirname "$DAEMON_LOG_FILE")"
  mkdir -p "$(dirname "$DASHBOARD_LOG_FILE")"
}

# Returns the PID that currently holds the LISTEN socket for the given port,
# or empty if nothing is listening. Uses ss, which only shows PIDs for
# sockets the current user owns — good enough for our own processes.
port_listener_pid() {
  local port="$1"
  ss -H -tlnp "sport = :$port" 2>/dev/null \
    | grep -oE 'pid=[0-9]+' \
    | head -1 \
    | cut -d= -f2
}

# is_descendant <child_pid> <ancestor_pid>
# True iff walking ppid chain from child reaches ancestor. Bounded to 10 hops.
is_descendant() {
  local child="$1" ancestor="$2" cur="$1"
  [[ -z "$child" || -z "$ancestor" ]] && return 1
  local hops=0
  while [[ -n "$cur" && "$cur" != "1" && "$cur" != "0" && $hops -lt 10 ]]; do
    [[ "$cur" == "$ancestor" ]] && return 0
    cur=$(ps -o ppid= -p "$cur" 2>/dev/null | tr -d ' ')
    hops=$((hops + 1))
  done
  return 1
}

# http_ok <url>  — 2xx/3xx within 3s counts as healthy.
http_ok() {
  local url="$1" code
  code=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 3 "$url" 2>/dev/null) || return 1
  [[ "$code" =~ ^[23] ]]
}

# ps_line <pid>  — one-line "pid user cmd" summary, quietly empty if pid gone.
ps_line() {
  ps -p "$1" -o pid,user,cmd --no-headers 2>/dev/null || true
}

# =============================================================================
# DATABASE
# =============================================================================

cmd_db() {
  local sub="${1:-help}"
  shift || true
  case "$sub" in
    start)
      if db_ready; then
        print_ok "Database already accepting connections (${DB_HOST}:${DB_PORT}/${DB_NAME})"
        return 0
      fi
      print_info "Starting database container..."
      COMPOSE_PROJECT_NAME=iw-ai-core docker compose -f docker-compose.bootstrap.yml up -d db
      print_info "Waiting for PostgreSQL..."
      wait_for_db 20 || return 1
      print_ok "Database ready (${DB_HOST}:${DB_PORT}/${DB_NAME})"
      ;;
    stop)
      print_info "Stopping database container..."
      COMPOSE_PROJECT_NAME=iw-ai-core docker compose -f docker-compose.bootstrap.yml stop db
      print_ok "Database stopped"
      ;;
    restart)
      cmd_db stop; cmd_db start
      ;;
    status)
      local cs
      cs=$(docker ps --filter "publish=${DB_PORT}" --format "{{.Names}}: {{.Status}}" 2>/dev/null | head -1)
      if [[ -z "$cs" ]]; then
        print_warn "DB container: not found on port ${DB_PORT} (may be embedded in compose)"
      else
        print_ok "Container: $cs"
      fi
      if db_ready; then
        print_ok "PostgreSQL: accepting connections (${DB_HOST}:${DB_PORT}/${DB_NAME})"
      else
        print_err "PostgreSQL: not reachable"
      fi
      ;;
    migrate)
      print_info "Running Alembic migrations..."
      uv run alembic upgrade head
      print_ok "Migrations complete"
      ;;
    revision)
      local msg="${1:-}"
      if [[ -z "$msg" ]]; then
        print_err "Usage: $0 db revision <message>"
        return 1
      fi
      uv run alembic revision --autogenerate -m "$msg"
      ;;
    logs)
      COMPOSE_PROJECT_NAME=iw-ai-core docker compose -f docker-compose.bootstrap.yml logs -f db
      ;;
    shell)
      print_info "Opening psql (${DB_USER}@${DB_HOST}:${DB_PORT}/${DB_NAME})..."
      PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME"
      ;;
    *)
      echo "  Usage: $0 db {start|stop|restart|status|migrate|revision <msg>|logs|shell}"
      ;;
  esac
}

# =============================================================================
# DAEMON
# =============================================================================

cmd_daemon() {
  local sub="${1:-help}"
  shift || true
  case "$sub" in
    start)
      local existing_pid
      existing_pid=$(read_pid "$DAEMON_PID_FILE")
      if pid_alive "$existing_pid"; then
        print_warn "Daemon already running (PID $existing_pid)"
        return 0
      elif [[ -n "$existing_pid" ]]; then
        # Stale PID file — remove it quietly before spawning
        rm -f "$DAEMON_PID_FILE"
      fi
      ensure_log_dir
      print_info "Starting daemon..."
      # The daemon writes its own PID file — do NOT pre-write it here or
      # _startup() will see the uv-run wrapper PID as a live process and
      # raise DaemonAlreadyRunning.
      nohup uv run python -m orch.daemon >> "$DAEMON_LOG_FILE" 2>&1 &
      local wrapper_pid=$!
      # Poll up to 15s: wrapper still alive AND daemon has written a live PID
      local i=0 daemon_pid=""
      while [[ $i -lt 15 ]]; do
        sleep 1
        i=$((i + 1))
        # If wrapper exited early, the daemon crashed at import/startup time
        if ! pid_alive "$wrapper_pid"; then
          print_err "Daemon process exited before writing PID file — check $DAEMON_LOG_FILE"
          tail -10 "$DAEMON_LOG_FILE" 2>/dev/null | sed 's/^/      /'
          rm -f "$DAEMON_PID_FILE"
          return 1
        fi
        daemon_pid=$(read_pid "$DAEMON_PID_FILE")
        if [[ -n "$daemon_pid" ]] && pid_alive "$daemon_pid"; then
          break
        fi
        daemon_pid=""
      done
      if [[ -z "$daemon_pid" ]]; then
        print_err "Daemon did not write a live PID file within 15s — check $DAEMON_LOG_FILE"
        tail -10 "$DAEMON_LOG_FILE" 2>/dev/null | sed 's/^/      /'
        rm -f "$DAEMON_PID_FILE"
        return 1
      fi
      print_ok "Daemon started (PID $daemon_pid) — log: $DAEMON_LOG_FILE"
      ;;
    stop)
      local pid
      pid=$(read_pid "$DAEMON_PID_FILE")
      if [[ -z "$pid" ]]; then
        print_warn "No PID file — daemon may not be running"
        return 0
      fi
      if ! pid_alive "$pid"; then
        print_warn "Stale PID file (PID $pid dead) — cleaning up"
        rm -f "$DAEMON_PID_FILE"
        return 0
      fi
      print_info "Stopping daemon (PID $pid)..."
      kill -TERM "$pid"
      local i=0
      while pid_alive "$pid"; do
        i=$((i + 1))
        if [[ $i -ge 15 ]]; then
          print_warn "Did not stop gracefully — sending SIGKILL"
          kill -KILL "$pid" 2>/dev/null || true
          break
        fi
        sleep 1
      done
      rm -f "$DAEMON_PID_FILE"
      print_ok "Daemon stopped"
      ;;
    restart)
      cmd_daemon stop; cmd_daemon start
      ;;
    status)
      local pid
      pid=$(read_pid "$DAEMON_PID_FILE")
      if [[ -n "$pid" ]] && pid_alive "$pid"; then
        print_ok "Daemon: running (PID $pid)"
      elif [[ -n "$pid" ]]; then
        print_err "Daemon: PID $pid in file but process is dead (stale PID file)"
      else
        print_err "Daemon: not running"
      fi
      if [[ -f "$DAEMON_LOG_FILE" ]]; then
        echo ""
        print_info "Last 5 log lines:"
        tail -5 "$DAEMON_LOG_FILE" | sed 's/^/      /'
      fi
      ;;
    reload)
      local pid
      pid=$(read_pid "$DAEMON_PID_FILE")
      if [[ -n "$pid" ]] && pid_alive "$pid"; then
        print_info "Sending SIGHUP (PID $pid) — reloading projects.toml..."
        kill -HUP "$pid"
        print_ok "SIGHUP sent"
      else
        print_err "Daemon is not running"
        return 1
      fi
      ;;
    logs)
      local lines="${1:-50}"
      if [[ -f "$DAEMON_LOG_FILE" ]]; then
        tail -f -n "$lines" "$DAEMON_LOG_FILE"
      else
        print_err "Log file not found: $DAEMON_LOG_FILE"
      fi
      ;;
    *)
      echo "  Usage: $0 daemon {start|stop|restart|status|reload|logs [lines]}"
      ;;
  esac
}

# =============================================================================
# DASHBOARD
# =============================================================================

cmd_dashboard() {
  local sub="${1:-help}"
  shift || true
  case "$sub" in
    start)
      local existing_pid
      existing_pid=$(read_pid "$DASHBOARD_PID_FILE")
      if pid_alive "$existing_pid"; then
        print_warn "Dashboard already running (PID $existing_pid)"
        return 0
      elif [[ -n "$existing_pid" ]]; then
        # Stale PID file — remove it quietly before spawning
        rm -f "$DASHBOARD_PID_FILE"
      fi
      # Pre-check: refuse if a foreign process already holds the port
      local foreign_pid
      foreign_pid=$(port_listener_pid "$DASHBOARD_PORT")
      if [[ -n "$foreign_pid" ]]; then
        print_err "Port $DASHBOARD_PORT is already in use by a foreign process:"
        print_err "  $(ps_line "$foreign_pid")"
        print_err "Stop that process first, or choose a different DASHBOARD_PORT."
        return 1
      fi
      ensure_log_dir
      print_info "Starting dashboard on port $DASHBOARD_PORT..."
      nohup uv run uvicorn dashboard.app:create_app \
        --factory \
        --host 0.0.0.0 \
        --port "$DASHBOARD_PORT" \
        >> "$DASHBOARD_LOG_FILE" 2>&1 &
      local wrapper_pid=$!
      echo "$wrapper_pid" > "$DASHBOARD_PID_FILE"
      print_info "Waiting for dashboard to accept connections..."
      # Poll up to 15s: wrapper alive AND port owned by our descendant AND HTTP OK
      local i=0 ready=false listener_pid=""
      while [[ $i -lt 15 ]]; do
        sleep 1
        i=$((i + 1))
        if ! pid_alive "$wrapper_pid"; then
          print_err "Dashboard process exited before binding port $DASHBOARD_PORT — check $DASHBOARD_LOG_FILE"
          tail -10 "$DASHBOARD_LOG_FILE" 2>/dev/null | sed 's/^/      /'
          rm -f "$DASHBOARD_PID_FILE"
          return 1
        fi
        listener_pid=$(port_listener_pid "$DASHBOARD_PORT")
        if [[ -n "$listener_pid" ]] \
            && is_descendant "$listener_pid" "$wrapper_pid" \
            && http_ok "http://127.0.0.1:${DASHBOARD_PORT}/"; then
          ready=true
          break
        fi
      done
      if [[ "$ready" != true ]]; then
        print_err "Dashboard did not become healthy within 15s — check $DASHBOARD_LOG_FILE"
        tail -10 "$DASHBOARD_LOG_FILE" 2>/dev/null | sed 's/^/      /'
        rm -f "$DASHBOARD_PID_FILE"
        return 1
      fi
      print_ok "Dashboard running (PID $wrapper_pid) — http://${DB_HOST}:${DASHBOARD_PORT}"
      ;;
    stop)
      local pid
      pid=$(read_pid "$DASHBOARD_PID_FILE")
      if [[ -z "$pid" ]]; then
        print_warn "No PID file — dashboard may not be running"
        return 0
      fi
      if ! pid_alive "$pid"; then
        print_warn "Stale PID file (PID $pid dead) — cleaning up"
        rm -f "$DASHBOARD_PID_FILE"
        return 0
      fi
      print_info "Stopping dashboard (PID $pid)..."
      kill -TERM "$pid"
      local i=0
      while pid_alive "$pid"; do
        i=$((i + 1))
        if [[ $i -ge 10 ]]; then
          kill -KILL "$pid" 2>/dev/null || true
          break
        fi
        sleep 1
      done
      rm -f "$DASHBOARD_PID_FILE"
      print_ok "Dashboard stopped"
      ;;
    restart)
      cmd_dashboard stop; cmd_dashboard start
      ;;
    status)
      local pid
      pid=$(read_pid "$DASHBOARD_PID_FILE")
      if [[ -n "$pid" ]] && pid_alive "$pid"; then
        print_ok "Dashboard: running (PID $pid) — http://${DB_HOST}:${DASHBOARD_PORT}"
      elif [[ -n "$pid" ]]; then
        print_err "Dashboard: PID $pid in file but process is dead (stale PID file)"
      elif port_listening "$DASHBOARD_PORT"; then
        print_warn "Dashboard: port $DASHBOARD_PORT in use but no PID file"
      else
        print_err "Dashboard: not running"
      fi
      ;;
    dev)
      print_info "Starting dashboard in dev mode (foreground, --reload)..."
      uv run uvicorn dashboard.app:create_app \
        --factory \
        --host 0.0.0.0 \
        --port "$DASHBOARD_PORT" \
        --reload
      ;;
    logs)
      local lines="${1:-50}"
      if [[ -f "$DASHBOARD_LOG_FILE" ]]; then
        tail -f -n "$lines" "$DASHBOARD_LOG_FILE"
      else
        print_err "Log file not found: $DASHBOARD_LOG_FILE"
      fi
      ;;
    *)
      echo "  Usage: $0 dashboard {start|stop|restart|status|dev|logs [lines]}"
      ;;
  esac
}

# =============================================================================
# COMPOUND COMMANDS
# =============================================================================

cmd_start() {
  print_header "Starting IW AI Core"
  cmd_db start || return 1
  # Fail-fast on identity mismatch before touching anything else
  if ! uv run iw db-identity check >/dev/null 2>&1; then
    local id_err
    id_err=$(uv run iw db-identity check 2>&1)
    print_err "DB identity mismatch — refusing to start."
    echo "$id_err" | sed 's/^/  /' >&2
    return 1
  fi
  print_info "Running migrations..."
  uv run alembic upgrade head || { print_err "Alembic migrations failed — aborting start"; return 1; }
  print_ok "Migrations up to date"
  cmd_daemon start || { print_err "Daemon failed to start — aborting"; return 1; }
  cmd_dashboard start || return 1
  echo ""
  print_ok "All services started"
  print_dim "Dashboard → http://${DB_HOST}:${DASHBOARD_PORT}"
}

cmd_stop() {
  print_header "Stopping IW AI Core"
  cmd_dashboard stop
  cmd_daemon stop
  cmd_db stop
  echo ""
  print_ok "All services stopped"
}

cmd_status() {
  print_header "IW AI Core — Status"

  # Database
  echo -e "  ${BOLD}Database${NC}"
  local cs
  cs=$(docker ps --filter "publish=${DB_PORT}" --format "{{.Names}}: {{.Status}}" 2>/dev/null | head -1)
  if [[ -n "$cs" ]]; then
    print_ok "Container: $cs"
  else
    print_warn "Container: not found on port ${DB_PORT} (may be embedded in compose)"
  fi
  if db_ready; then
    print_ok "PostgreSQL: accepting connections (${DB_HOST}:${DB_PORT}/${DB_NAME})"
  else
    print_err "PostgreSQL: not reachable"
  fi

  # DB identity check
  local identity_output identity_exit
  identity_output=$(uv run iw db-identity check 2>&1); identity_exit=$?
  if [[ "$identity_exit" -eq 0 ]]; then
    local short_uuid
    short_uuid=$(echo "$identity_output" | grep -oE '[0-9a-f]{8}' | head -1 || echo "?")
    if echo "$identity_output" | grep -q "BOOTSTRAP"; then
      print_warn "DB identity: UNVERIFIED (bootstrap mode — add IW_CORE_EXPECTED_INSTANCE_ID to .env)"
    else
      print_ok "DB identity: PASS ($short_uuid)"
    fi
  elif [[ "$identity_exit" -eq 2 ]]; then
    print_err "DB identity: FAIL (expected!=actual)"
    echo "$identity_output" | sed 's/^/      /' >&2
  elif [[ "$identity_exit" -eq 3 ]]; then
    print_err "DB identity: row missing from iw_core_instance"
  else
    print_err "DB identity: could not connect"
  fi

  # Daemon
  echo ""
  echo -e "  ${BOLD}Daemon${NC}"
  local daemon_pid
  daemon_pid=$(read_pid "$DAEMON_PID_FILE")
  if [[ -n "$daemon_pid" ]] && pid_alive "$daemon_pid"; then
    print_ok "Daemon: running (PID $daemon_pid)"
  elif [[ -n "$daemon_pid" ]]; then
    print_err "Daemon: stale PID file (PID $daemon_pid dead)"
  else
    print_err "Daemon: not running"
  fi

  # Dashboard
  echo ""
  echo -e "  ${BOLD}Dashboard${NC}"
  local dash_pid
  dash_pid=$(read_pid "$DASHBOARD_PID_FILE")
  if [[ -n "$dash_pid" ]] && pid_alive "$dash_pid"; then
    print_ok "Dashboard: running (PID $dash_pid) — http://${DB_HOST}:${DASHBOARD_PORT}"
  elif port_listening "$DASHBOARD_PORT"; then
    print_warn "Dashboard: port $DASHBOARD_PORT in use but no PID file"
  else
    print_err "Dashboard: not running"
  fi

  # Recent daemon events (if DB is up)
  if db_ready; then
    echo ""
    echo -e "  ${BOLD}Recent Daemon Events${NC}"
    PGPASSWORD="$DB_PASSWORD" psql \
      -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
      -t -A -F " │ " \
      -c "SELECT to_char(created_at,'HH24:MI:SS'), COALESCE(project_id,'system'), event_type, COALESCE(LEFT(message,60),'') FROM daemon_events ORDER BY id DESC LIMIT 8;" \
      2>/dev/null | sed 's/^/    /' || true
  fi
  echo ""
}

cmd_logs() {
  ensure_log_dir
  local files=()
  [[ -f "$DAEMON_LOG_FILE" ]]    && files+=("$DAEMON_LOG_FILE")
  [[ -f "$DASHBOARD_LOG_FILE" ]] && files+=("$DASHBOARD_LOG_FILE")

  if [[ ${#files[@]} -eq 0 ]]; then
    print_err "No log files found yet"
    return 1
  fi

  print_info "Tailing: ${files[*]}"
  tail -f -n 30 "${files[@]}"
}

cmd_install() {
  print_header "Installing IW AI Core"
  print_info "Syncing Python dependencies..."
  uv sync

  # Optional diagram tool availability check (non-blocking)
  echo ""
  echo "Checking optional diagram tools..."
  if ! command -v mmdc &>/dev/null && [ ! -f "$HOME/.local/bin/mmdc" ]; then
    echo -e "  \033[33m⚠ mmdc not found — Mermaid server-side rendering disabled.\033[0m"
    echo    "    To enable: npm install -g @mermaid-js/mermaid-cli"
  else
    echo    "  ✓ mmdc available"
  fi
  if ! command -v d2 &>/dev/null; then
    echo -e "  \033[33m⚠ d2 not found — D2 diagram rendering disabled.\033[0m"
    echo    "    To enable: go install oss.terrastruct.com/d2@latest"
  else
    echo    "  ✓ d2 available"
  fi

  print_info "Starting database..."
  cmd_db start
  print_info "Running migrations..."
  uv run alembic upgrade head
  print_ok "Done — run './ai-core.sh start' to launch all services"
}

# =============================================================================
# STATUS HELPER (single-line, for menu header)
# =============================================================================

_svc_badge() {
  # _svc_badge <label> <running:true|false>
  local label="$1" ok="$2"
  if [[ "$ok" == true ]]; then
    echo -e "${GREEN}▲ ${label}${NC}"
  else
    echo -e "${RED}▼ ${label}${NC}"
  fi
}

get_status_line() {
  # DB
  local db_ok=false
  db_ready 2>/dev/null && db_ok=true

  # Daemon
  local daemon_ok=false
  local dpid
  dpid=$(read_pid "$DAEMON_PID_FILE")
  pid_alive "$dpid" && daemon_ok=true

  # Dashboard
  local dash_ok=false
  local shpid
  shpid=$(read_pid "$DASHBOARD_PID_FILE")
  pid_alive "$shpid" && dash_ok=true

  echo -e "  $(_svc_badge "db" "$db_ok")   $(_svc_badge "daemon" "$daemon_ok")   $(_svc_badge "dashboard" "$dash_ok")"
}

# =============================================================================
# INTERACTIVE MENUS
# =============================================================================

menu_database() {
  while true; do
    print_header "Database"
    cmd_db status
    echo ""
    echo -e "  ${CYAN}1)${NC} Start"
    echo -e "  ${CYAN}2)${NC} Stop"
    echo -e "  ${CYAN}3)${NC} Restart"
    echo -e "  ${CYAN}4)${NC} Run migrations  (alembic upgrade head)"
    echo -e "  ${CYAN}5)${NC} Generate migration  (revision --autogenerate)"
    echo -e "  ${CYAN}6)${NC} Open psql shell"
    echo -e "  ${CYAN}7)${NC} Tail DB container logs"
    echo -e "  ${CYAN}0)${NC} Back"
    echo ""
    read -r -p "  Choice: " choice
    case "$choice" in
      1) cmd_db start ;;
      2) cmd_db stop ;;
      3) cmd_db restart ;;
      4) cmd_db migrate ;;
      5)
        echo ""
        read -r -p "  Migration message: " msg
        cmd_db revision "$msg"
        ;;
      6) cmd_db shell ;;
      7) cmd_db logs ;;
      0|"") return ;;
      *) print_warn "Invalid choice" ;;
    esac
    echo ""
    read -r -p "  Press Enter to continue..."
  done
}

menu_daemon() {
  while true; do
    print_header "Daemon"
    local pid
    pid=$(read_pid "$DAEMON_PID_FILE")
    if [[ -n "$pid" ]] && pid_alive "$pid"; then
      echo -e "  Status: ${GREEN}▲ running${NC} (PID $pid)"
    else
      echo -e "  Status: ${RED}▼ stopped${NC}"
    fi
    echo ""
    echo -e "  ${CYAN}1)${NC} Start"
    echo -e "  ${CYAN}2)${NC} Stop"
    echo -e "  ${CYAN}3)${NC} Restart"
    echo -e "  ${CYAN}4)${NC} Status (with recent log lines)"
    echo -e "  ${CYAN}5)${NC} Reload  (SIGHUP — re-reads projects.toml)"
    echo -e "  ${CYAN}6)${NC} Last 50 log lines"
    echo -e "  ${CYAN}7)${NC} Tail log (live)"
    echo -e "  ${CYAN}0)${NC} Back"
    echo ""
    read -r -p "  Choice: " choice
    case "$choice" in
      1) cmd_daemon start ;;
      2) cmd_daemon stop ;;
      3) cmd_daemon restart ;;
      4) cmd_daemon status ;;
      5) cmd_daemon reload ;;
      6) [[ -f "$DAEMON_LOG_FILE" ]] && tail -n 50 "$DAEMON_LOG_FILE" || print_warn "No log file" ;;
      7) [[ -f "$DAEMON_LOG_FILE" ]] && tail -f "$DAEMON_LOG_FILE" || print_warn "No log file" ;;
      0|"") return ;;
      *) print_warn "Invalid choice" ;;
    esac
    echo ""
    read -r -p "  Press Enter to continue..."
  done
}

menu_dashboard() {
  while true; do
    print_header "Dashboard"
    local pid
    pid=$(read_pid "$DASHBOARD_PID_FILE")
    if [[ -n "$pid" ]] && pid_alive "$pid"; then
      echo -e "  Status: ${GREEN}▲ running${NC} (PID $pid) — http://${DB_HOST}:${DASHBOARD_PORT}"
    else
      echo -e "  Status: ${RED}▼ stopped${NC}"
    fi
    echo ""
    echo -e "  ${CYAN}1)${NC} Start"
    echo -e "  ${CYAN}2)${NC} Stop"
    echo -e "  ${CYAN}3)${NC} Restart"
    echo -e "  ${CYAN}4)${NC} Status"
    echo -e "  ${CYAN}5)${NC} Last 50 log lines"
    echo -e "  ${CYAN}6)${NC} Tail log (live)"
    echo -e "  ${CYAN}7)${NC} Dev mode  (foreground, --reload)"
    echo -e "  ${CYAN}0)${NC} Back"
    echo ""
    read -r -p "  Choice: " choice
    case "$choice" in
      1) cmd_dashboard start ;;
      2) cmd_dashboard stop ;;
      3) cmd_dashboard restart ;;
      4) cmd_dashboard status ;;
      5) [[ -f "$DASHBOARD_LOG_FILE" ]] && tail -n 50 "$DASHBOARD_LOG_FILE" || print_warn "No log file" ;;
      6) [[ -f "$DASHBOARD_LOG_FILE" ]] && tail -f "$DASHBOARD_LOG_FILE" || print_warn "No log file" ;;
      7) cmd_dashboard dev ;;
      0|"") return ;;
      *) print_warn "Invalid choice" ;;
    esac
    echo ""
    read -r -p "  Press Enter to continue..."
  done
}

menu_logs() {
  while true; do
    print_header "Logs"
    echo -e "  ${CYAN}1)${NC} Tail all logs  (daemon + dashboard together)"
    echo -e "  ${CYAN}2)${NC} Tail daemon log"
    echo -e "  ${CYAN}3)${NC} Tail dashboard log"
    echo -e "  ${CYAN}4)${NC} Last 100 lines — daemon"
    echo -e "  ${CYAN}5)${NC} Last 100 lines — dashboard"
    echo -e "  ${CYAN}0)${NC} Back"
    echo ""
    read -r -p "  Choice: " choice
    case "$choice" in
      1) cmd_logs ;;
      2) cmd_daemon logs ;;
      3) cmd_dashboard logs ;;
      4) [[ -f "$DAEMON_LOG_FILE" ]]    && tail -n 100 "$DAEMON_LOG_FILE"    || print_warn "No daemon log file" ;;
      5) [[ -f "$DASHBOARD_LOG_FILE" ]] && tail -n 100 "$DASHBOARD_LOG_FILE" || print_warn "No dashboard log file" ;;
      0|"") return ;;
      *) print_warn "Invalid choice" ;;
    esac
    echo ""
    read -r -p "  Press Enter to continue..."
  done
}

menu_main() {
  while true; do
    clear
    echo -e "${BOLD}${BLUE}"
    echo "  ╔══════════════════════════════════════╗"
    echo "  ║   IW AI Core                         ║"
    echo "  ║   Orchestration Platform             ║"
    echo "  ╚══════════════════════════════════════╝"
    echo -e "${NC}"

    get_status_line
    echo ""

    echo -e "  ${CYAN}1)${NC} Start all        (db → migrate → daemon → dashboard)"
    echo -e "  ${CYAN}2)${NC} Stop all"
    echo -e "  ${CYAN}3)${NC} Restart all"
    echo -e "  ${CYAN}4)${NC} Status"
    echo ""
    echo -e "  ${CYAN}5)${NC} Database"
    echo -e "  ${CYAN}6)${NC} Daemon"
    echo -e "  ${CYAN}7)${NC} Dashboard"
    echo -e "  ${CYAN}8)${NC} Logs"
    echo ""
    echo -e "  ${CYAN}0)${NC} Exit"
    echo ""
    read -r -p "  Choice: " choice
    case "$choice" in
      1) cmd_start ;;
      2) cmd_stop ;;
      3) cmd_stop; cmd_start ;;
      4) cmd_status ;;
      5) menu_database ;;
      6) menu_daemon ;;
      7) menu_dashboard ;;
      8) menu_logs ;;
      0|q|Q|exit|quit) echo ""; exit 0 ;;
      *) print_warn "Invalid choice" ;;
    esac
    echo ""
    read -r -p "  Press Enter to continue..."
  done
}

# =============================================================================
# CLI ENTRY POINT
# =============================================================================

usage() {
  cat <<EOF

${BOLD}ai-core.sh${NC} — IW AI Core management

${BOLD}USAGE${NC}
  ./ai-core.sh                      Interactive menu
  ./ai-core.sh <command> [args]     CLI mode

${BOLD}COMPOUND${NC}
  start                             db → migrate → daemon → dashboard
  stop                              dashboard → daemon → db
  restart                           stop + start
  status                            Full status summary
  logs                              Tail daemon + dashboard logs together
  install                           uv sync + db start + migrate  (first-time setup)

${BOLD}DATABASE${NC}
  db start|stop|restart|status
  db migrate                        alembic upgrade head
  db revision <msg>                 alembic revision --autogenerate
  db logs                           Tail DB container logs
  db shell                          Open psql session

${BOLD}DAEMON${NC}
  daemon start|stop|restart|status
  daemon reload                     SIGHUP — re-reads projects.toml
  daemon logs [N]                   Tail daemon log (default 50 lines)

${BOLD}DASHBOARD${NC}
  dashboard start|stop|restart|status
  dashboard dev                     Foreground with --reload
  dashboard logs [N]                Tail dashboard log (default 50 lines)

${BOLD}EXAMPLES${NC}
  ./ai-core.sh start
  ./ai-core.sh status
  ./ai-core.sh daemon reload
  ./ai-core.sh dashboard dev
  ./ai-core.sh db revision "add index on work_items"

EOF
}

CMD="${1:-}"
shift || true

case "$CMD" in
  "")           menu_main ;;
  start)        cmd_start ;;
  stop)         cmd_stop ;;
  restart)      cmd_stop; cmd_start ;;
  status)       cmd_status ;;
  logs)         cmd_logs ;;
  install)      cmd_install ;;
  db)           cmd_db "$@" ;;
  daemon)       cmd_daemon "$@" ;;
  dashboard)    cmd_dashboard "$@" ;;
  # Legacy --flag aliases (backwards compat with old callers)
  --status)     cmd_status ;;
  --start)      cmd_start ;;
  --stop)       cmd_stop ;;
  help|--help|-h) usage ;;
  *)
    print_err "Unknown command: $CMD"
    usage
    exit 1
    ;;
esac
