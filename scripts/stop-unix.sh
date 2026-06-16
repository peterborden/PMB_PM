#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-docker}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="$ROOT_DIR/.run"

stop_process() {
  local name="$1"
  local pid_file="$RUN_DIR/$name.pid"

  if [[ ! -f "$pid_file" ]]; then
    echo "$name is not running (no pid file)."
    return
  fi

  local pid
  pid="$(cat "$pid_file")"
  if kill -0 "$pid" 2>/dev/null; then
    kill "$pid"
    echo "Stopped $name (pid $pid)"
  else
    echo "$name pid $pid was not active."
  fi

  rm -f "$pid_file"
}

stop_docker() {
  (
    cd "$ROOT_DIR"
    docker compose down
  )
  echo "Docker app stopped."
}

stop_local() {
  stop_process "frontend"
  stop_process "backend"
}

case "$MODE" in
docker)
  stop_docker
  ;;
local)
  stop_local
  ;;
*)
  echo "Usage: $0 [docker|local]"
  exit 1
  ;;
esac
