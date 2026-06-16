This folder contains start and stop scripts for Mac, Linux, and Windows.

- `start-*.sh` / `stop-*.sh` are Unix wrappers
- `start-unix.sh` / `stop-unix.sh` provide shared Unix behavior
- `start-windows.ps1` / `stop-windows.ps1` provide Windows behavior

Each start/stop script supports:
- `docker` mode (default): uses `docker compose up/down`
- `local` mode: manages local backend/frontend processes with pid files in `.run/`