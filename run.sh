#!/usr/bin/env bash
#
# ReturnShield AI local stack manager.
#
# Commands:
#   ./run.sh install [backend|frontend|all]
#   ./run.sh load demo [auto|local|compose]
#   ./run.sh load cricket [local]
#   ./run.sh run [backend|frontend|all|dev]
#   ./run.sh restart [backend|frontend|all]
#   ./run.sh check [backend|frontend|all]
#   ./run.sh test [backend|frontend|all]
#   ./run.sh stop [backend|frontend|all]
#   ./run.sh status
#   ./run.sh logs [backend|frontend]

set -o pipefail

RED=$'\e[0;31m'; GREEN=$'\e[0;32m'; YELLOW=$'\e[1;33m'
BLUE=$'\e[0;34m'; PURPLE=$'\e[0;35m'; NC=$'\e[0m'

print_info() { echo "${BLUE}[INFO]${NC} $1"; }
print_ok() { echo "${GREEN}[OK]${NC} $1"; }
print_warn() { echo "${YELLOW}[WARN]${NC} $1"; }
print_err() { echo "${RED}[ERR]${NC} $1"; }
print_header() { echo "${PURPLE}== $1 ==${NC}"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$SCRIPT_DIR"
BACKEND_DIR="$ROOT/backend"
FRONTEND_DIR="$ROOT/frontend"
RUN_DIR="$ROOT/.run"
mkdir -p "$RUN_DIR"

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

BACKEND_PID="$RUN_DIR/backend.pid"
BACKEND_LOG="$RUN_DIR/backend.log"
FRONTEND_PID="$RUN_DIR/frontend.pid"
FRONTEND_LOG="$RUN_DIR/frontend.log"

command_exists() { command -v "$1" >/dev/null 2>&1; }

compose_exec() {
  if command_exists docker && docker compose version >/dev/null 2>&1; then
    docker compose "$@"
  elif command_exists docker-compose; then
    docker-compose "$@"
  else
    print_err "docker compose is required for compose mode"
    return 1
  fi
}

backend_python() {
  if [ -x "$BACKEND_DIR/.venv/bin/python" ]; then
    echo "$BACKEND_DIR/.venv/bin/python"
  else
    echo "python3"
  fi
}

frontend_npm() {
  if command_exists npm; then
    echo "npm"
  else
    print_err "npm is required for frontend commands"
    return 1
  fi
}

backend_venv_python() {
  echo "$BACKEND_DIR/.venv/bin/python"
}

is_running() {
  local pidfile="$1"
  [ -f "$pidfile" ] || return 1
  local pid
  pid="$(cat "$pidfile" 2>/dev/null || true)"
  [ -n "$pid" ] && kill -0 "$pid" >/dev/null 2>&1
}

wait_for_http() {
  local url="$1"
  local attempts="${2:-30}"
  local delay="${3:-1}"
  local i
  for ((i = 1; i <= attempts; i++)); do
    if command_exists curl && curl -fsS "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep "$delay"
  done
  return 1
}

ensure_backend_venv() {
  if [ ! -x "$(backend_venv_python)" ]; then
    print_info "creating backend virtual environment"
    python3 -m venv "$BACKEND_DIR/.venv"
  fi
}

install_backend() {
  print_header "Installing backend dependencies"
  ensure_backend_venv
  "$BACKEND_DIR/.venv/bin/pip" install -r "$BACKEND_DIR/requirements.txt"
  print_ok "backend dependencies installed"
}

install_frontend() {
  print_header "Installing frontend dependencies"
  (cd "$FRONTEND_DIR" && npm install)
  print_ok "frontend dependencies installed"
}

install_all() {
  install_backend
  install_frontend
}

start_backend() {
  if is_running "$BACKEND_PID"; then
    print_warn "backend already running (pid $(cat "$BACKEND_PID"))"
    return 0
  fi
  ensure_backend_venv
  source_env_file || return 1
  setsid env PYTHONPATH="$ROOT" "$BACKEND_DIR/.venv/bin/python" -u -m uvicorn backend.app.main:app --host 127.0.0.1 --port "$BACKEND_PORT" >>"$BACKEND_LOG" 2>&1 </dev/null &
  echo $! >"$BACKEND_PID"
  if wait_for_http "http://127.0.0.1:${BACKEND_PORT}/api/health" 120 2; then
    print_ok "backend running on http://127.0.0.1:${BACKEND_PORT}"
  else
    print_err "backend did not become ready; see $BACKEND_LOG"
    return 1
  fi
}


start_frontend() {
  if is_running "$FRONTEND_PID"; then
    print_warn "frontend already running (pid $(cat "$FRONTEND_PID"))"
    return 0
  fi
  if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
    print_err "frontend dependencies missing; run ./run.sh install frontend first"
    return 1
  fi
  print_header "Starting frontend"
  setsid env FRONTEND_DIR="$FRONTEND_DIR" FRONTEND_PORT="$FRONTEND_PORT" bash -lc 'cd "$FRONTEND_DIR" && exec npm run dev -- --host 127.0.0.1 --port "$FRONTEND_PORT"' >>"$FRONTEND_LOG" 2>&1 </dev/null &
  echo $! >"$FRONTEND_PID"
  if wait_for_http "http://127.0.0.1:${FRONTEND_PORT}" 40 1; then
    print_ok "frontend running on http://127.0.0.1:${FRONTEND_PORT}"
  else
    print_err "frontend did not become ready; see $FRONTEND_LOG"
    return 1
  fi
}



stop_backend() {
  if is_running "$BACKEND_PID"; then
    local pid
    pid="$(cat "$BACKEND_PID")"
    kill "$pid" >/dev/null 2>&1 || true
    rm -f "$BACKEND_PID"
    print_ok "backend stopped"
  else
    print_warn "backend not running"
  fi
}

stop_frontend() {
  if is_running "$FRONTEND_PID"; then
    local pid
    pid="$(cat "$FRONTEND_PID")"
    kill "$pid" >/dev/null 2>&1 || true
    rm -f "$FRONTEND_PID"
    print_ok "frontend stopped"
  else
    print_warn "frontend not running"
  fi
}

stop_all() {
  stop_frontend
  stop_backend
}

restart_backend() {
  stop_backend
  start_backend
}

restart_frontend() {
  stop_frontend
  start_frontend
}
restart_all() {
  stop_all
  start_backend
  start_frontend
}

seed_production_demo() {
  print_info "Seeding PostgreSQL demo data"
  "$BACKEND_DIR/.venv/bin/python" -m backend.app.scripts.seed_demo_data
  print_info "Creating PostgreSQL secondary indexes"
  "$BACKEND_DIR/.venv/bin/python" -m backend.app.scripts.create_indexes
}

seed_cricket_demo() {
  print_info "Seeding cricket-ball return data"
  "$BACKEND_DIR/.venv/bin/python" -m backend.app.scripts.seed_cricket_returns
}


load_demo() {
  local mode="${1:-auto}"
  print_header "Loading demo data"
  source_env_file || return 1
  case "$mode" in
    local|dev|postgres)
      print_info "Using local Postgres seed"
      if is_running "$BACKEND_PID"; then
        stop_backend
      fi
      start_backend
      seed_production_demo
      print_ok "demo data loaded via PostgreSQL seed"
      ;;
    compose|docker)
      if ! command_exists docker && ! command_exists docker-compose; then
        print_err "Docker Compose is not available"
        return 1
      fi
      print_info "Loading demo stack through containers"
      stop_all
      compose_load_demo
      ;;
    auto|"")
      if command_exists docker || command_exists docker-compose; then
        print_info "Docker Compose detected; loading demo stack through containers"
        stop_all
        compose_load_demo
      else
        print_info "Docker Compose not available; using local Postgres seed"
        if is_running "$BACKEND_PID"; then
          stop_backend
        fi
        start_backend
        seed_production_demo
        print_ok "demo data loaded via PostgreSQL seed"
      fi
      ;;
    *)
      print_err "unknown load mode: $mode"
      return 1
      ;;
  esac
}




check_backend() {
  print_header "Checking backend"
  ensure_backend_venv
  source_env_file || return 1
  "$BACKEND_DIR/.venv/bin/python" -m compileall "$BACKEND_DIR/app"
  print_ok "backend syntax check passed"
}
check_frontend() {
  print_header "Checking frontend"
  if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
    print_warn "frontend dependencies missing; running build may fail"
  fi
  if (cd "$FRONTEND_DIR" && npm run build); then
    print_ok "frontend build check passed"
  else
    print_err "frontend build check failed"
    return 1
  fi
}

check_all() {
  check_backend
  check_frontend
}

test_backend() {
  print_header "Testing backend"
  ensure_backend_venv
  source_env_file || return 1
  if [ -d "$BACKEND_DIR/tests" ] && find "$BACKEND_DIR/tests" -name 'test_*.py' -o -name '*_test.py' | grep -q .; then
    (cd "$BACKEND_DIR" && .venv/bin/pytest -q)
  else
    "$BACKEND_DIR/.venv/bin/python" -m compileall "$BACKEND_DIR/app"
    "$BACKEND_DIR/.venv/bin/python" -c "from backend.app.main import app; print('backend import smoke ok')"
    if is_running "$BACKEND_PID"; then
      wait_for_http "http://127.0.0.1:${BACKEND_PORT}/api/health" 5 1 || {
        print_err "backend health endpoint not reachable"
        return 1
      }
    fi
  fi
  print_ok "backend tests passed"
}

test_frontend() {
  print_header "Testing frontend"
  if [ -d "$FRONTEND_DIR/node_modules" ]; then
    if (cd "$FRONTEND_DIR" && npm run build); then
      print_ok "frontend tests passed"
    else
      print_err "frontend tests failed"
      return 1
    fi
  else
    print_err "frontend dependencies missing; run './run.sh install frontend' first"
    return 1
  fi
}

test_all() {
  test_backend
  test_frontend
}


status() {
  print_header "Service status"
  if is_running "$BACKEND_PID"; then
    print_ok "backend: running on :$BACKEND_PORT (pid $(cat "$BACKEND_PID"))"
  else
    print_warn "backend: not running"
  fi
  if is_running "$FRONTEND_PID"; then
    print_ok "frontend: running on :$FRONTEND_PORT (pid $(cat "$FRONTEND_PID"))"
  else
    print_warn "frontend: not running"
  fi
}

logs() {
  case "${1:-all}" in
    backend) tail -f "$BACKEND_LOG" ;;
    frontend) tail -f "$FRONTEND_LOG" ;;
    all|*) tail -f "$BACKEND_LOG" "$FRONTEND_LOG" ;;
  esac
}

compose_up() {
  local target="${1:-all}"
  print_header "Starting Docker Compose stack"
  case "$target" in
    backend|frontend|postgres|all) compose_exec up -d --build ${target/all/} ;;
    *) print_err "unknown compose target: $target"; return 1 ;;
  esac
  print_ok "compose stack started"
}

compose_down() {
  print_header "Stopping Docker Compose stack"
  compose_exec down
  print_ok "compose stack stopped"
}

compose_restart() {
  local target="${1:-all}"
  print_header "Restarting Docker Compose stack"
  case "$target" in
    backend|frontend|postgres|all) compose_exec restart ${target/all/} ;;
    *) print_err "unknown compose target: $target"; return 1 ;;
  esac
  print_ok "compose stack restarted"
}

compose_status() {
  print_header "Docker Compose status"
  compose_exec ps
}

compose_logs() {
  local target="${1:-all}"
  case "$target" in
    backend|frontend|postgres|all) compose_exec logs -f ${target/all/} ;;
    *) print_err "unknown compose target: $target"; return 1 ;;
  esac
}

compose_load_demo() {
  print_header "Loading compose demo data"
  compose_exec down -v
  compose_exec up -d --build
  print_ok "compose demo loaded"
}

show_help() {
  cat <<EOF
ReturnShield AI local stack manager

Usage:
  ./run.sh [--env-file <path>] <command> [args...]

Global flags:
  --env-file, -e <path>   Source env file before running the command

Commands:
  install [backend|frontend|all]
  load demo [auto|local|compose]
  run [backend|frontend|all|dev]
  restart [backend|frontend|all|dev]
  check [backend|frontend|all|dev]
  test [backend|frontend|all|dev]
  stop [backend|frontend|all|dev]
  status
  logs [backend|frontend]
  compose [up|down|restart|status|logs|load]
  help

Examples:
  ./run.sh --env-file .env.test test backend
  ./run.sh -e .env.production run backend
  ./run.sh test backend

Defaults:
  - backend runs on http://127.0.0.1:${BACKEND_PORT}
  - frontend runs on http://127.0.0.1:${FRONTEND_PORT}
  - local demo data is loaded into PostgreSQL
EOF
}

# Parse global flags (--env-file) from any position
ENV_FILE=""
PASSTHROUGH_ARGS=()
SKIP_NEXT=false
for arg in "$@"; do
  if $SKIP_NEXT; then
    ENV_FILE="$arg"
    SKIP_NEXT=false
  elif [ "$arg" = "--env-file" ] || [ "$arg" = "-e" ]; then
    SKIP_NEXT=true
  else
    PASSTHROUGH_ARGS+=("$arg")
  fi
done
# Re-set positional args without the flag
set -- "${PASSTHROUGH_ARGS[@]}"

# Source env file if provided
source_env_file() {
  if [ -n "$ENV_FILE" ]; then
    if [ -f "$ENV_FILE" ]; then
      print_info "Sourcing env file: $ENV_FILE"
      set -a
      # shellcheck disable=SC1090
      . "$ENV_FILE"
      set +a
    else
      print_err "env file not found: $ENV_FILE"
      return 1
    fi
  elif [ -f "$ROOT/.env.local" ]; then
    print_info "Sourcing env file: $ROOT/.env.local"
    set -a
    # shellcheck disable=SC1090
    . "$ROOT/.env.local"
    set +a
  elif [ -f "$ROOT/.env.production" ]; then
    print_info "Sourcing env file: $ROOT/.env.production"
    set -a
    # shellcheck disable=SC1090
    . "$ROOT/.env.production"
    set +a
  fi
}
case "${1:-help}" in
  help|-h|--help) show_help ;;
  install)
    case "${2:-all}" in
      backend) install_backend ;;
      frontend) install_frontend ;;
      all) install_all ;;
      *) print_err "unknown install target: $2"; exit 1 ;;
    esac
    ;;
  load)
    case "${2:-demo}" in
      demo) load_demo "${3:-auto}" ;;
      cricket)
        if is_running "$BACKEND_PID"; then
          stop_backend
        fi
        start_backend
        seed_cricket_demo
        print_ok "cricket return data loaded via PostgreSQL seed"
        ;;
      *) print_err "unknown load target: $2"; exit 1 ;;
    esac
    ;;
  run|start|up|dev)
    case "${2:-all}" in
      backend) start_backend ;;
      frontend) start_frontend ;;
      all|dev) start_backend; start_frontend ;;
      *) print_err "unknown run target: $2"; exit 1 ;;
    esac
    ;;
  restart|bounce)
    case "${2:-all}" in
      backend) restart_backend ;;
      frontend) restart_frontend ;;
      all|dev) restart_all ;;
      *) print_err "unknown restart target: $2"; exit 1 ;;
    esac
    ;;
  stop)
    case "${2:-all}" in
      backend) stop_backend ;;
      frontend) stop_frontend ;;
      all|dev) stop_all ;;
      *) print_err "unknown stop target: $2"; exit 1 ;;
    esac
    ;;
  check)
    case "${2:-all}" in
      backend) check_backend ;;
      frontend) check_frontend ;;
      all|dev) check_all ;;
      *) print_err "unknown check target: $2"; exit 1 ;;
    esac
    ;;
  test|tests)
    case "${2:-all}" in
      backend) test_backend ;;
      frontend) test_frontend ;;
      all|dev) test_all ;;
      *) print_err "unknown test target: $2"; exit 1 ;;
    esac
    ;;
  status) status ;;
  logs) logs "${2:-all}" ;;
  compose)
    case "${2:-status}" in
      up) compose_up "${3:-all}" ;;
      down) compose_down ;;
      restart) compose_restart "${3:-all}" ;;
      status) compose_status ;;
      logs) compose_logs "${3:-all}" ;;
      load) compose_load_demo ;;
      *) print_err "unknown compose action: $2"; exit 1 ;;
    esac
    ;;
  *)
    print_err "unknown command: ${1}"
    print_info "Run './run.sh help' for usage."
    exit 1
    ;;
esac
