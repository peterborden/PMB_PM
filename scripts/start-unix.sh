#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-docker}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="$ROOT_DIR/.run"

mkdir -p "$RUN_DIR"

start_process() {
  local name="$1"
  local command="$2"
  local pid_file="$RUN_DIR/$name.pid"
  local log_file="$RUN_DIR/$name.log"

  if [[ -f "$pid_file" ]] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
    echo "$name is already running (pid $(cat "$pid_file"))."
    return
  fi

  nohup bash -lc "$command" >"$log_file" 2>&1 &
  echo "$!" >"$pid_file"
  echo "Started $name (pid $!)"
}

start_docker() {
  (
    cd "$ROOT_DIR"
    docker compose up --build -d
  )
  echo "Docker app started at http://127.0.0.1:8000"
}

start_local() {
  command -v uv >/dev/null 2>&1 || {
    echo "uv is required for local backend start."
    exit 1
  }
  command -v npm >/dev/null 2>&1 || {
    echo "npm is required for local frontend start."
    exit 1
  }

  start_process "backend" "cd \"$ROOT_DIR\" && uv run --project backend uvicorn backend.app.main:app --host 127.0.0.1 --port 8000"
  start_process "frontend" "cd \"$ROOT_DIR/frontend\" && npm run dev -- --hostname 127.0.0.1 --port 3000"
  echo "Local services started:"
  echo "  Backend:  http://127.0.0.1:8000"
  echo "  Frontend: http://127.0.0.1:3000"
}

case "$MODE" in
docker)
  start_docker
  ;;
local)
  start_local
  ;;
*)
  echo "Usage: $0 [docker|local]"
  exit 1
  ;;
esac
