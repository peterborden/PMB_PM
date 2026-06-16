import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_for_server(url: str, timeout_seconds: float = 10.0) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urlopen(url, timeout=1):
                return
        except Exception:
            time.sleep(0.2)
    raise AssertionError(f"Server did not become ready: {url}")


def _start_server(backend_root: Path, port: int, env: dict[str, str]) -> subprocess.Popen:
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=backend_root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def test_live_server_serves_page_and_api() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory() as temp_dir:
        frontend_static_dir = Path(temp_dir)
        db_path = frontend_static_dir / "e2e.db"
        (frontend_static_dir / "index.html").write_text(
            "<!doctype html><html><body><h1>Kanban Studio</h1></body></html>",
            encoding="utf-8",
        )
        (frontend_static_dir / "_next" / "static").mkdir(parents=True, exist_ok=True)
        (frontend_static_dir / "_next" / "static" / "app.js").write_text(
            "console.log('kanban');",
            encoding="utf-8",
        )

        env = {
            **os.environ,
            "FRONTEND_STATIC_DIR": str(frontend_static_dir),
            "PM_DB_PATH": str(db_path),
        }
        port = _pick_free_port()
        process = _start_server(backend_root, port, env)

        try:
            _wait_for_server(f"http://127.0.0.1:{port}/api/health")
            with urlopen(f"http://127.0.0.1:{port}/", timeout=3) as response:
                html = response.read().decode("utf-8")
                assert "Kanban Studio" in html

            try:
                urlopen(f"http://127.0.0.1:{port}/api/hello", timeout=3)
                raise AssertionError("Expected /api/hello to require authentication")
            except HTTPError as error:
                assert error.code == 401

            cookie_jar = CookieJar()
            opener = build_opener(HTTPCookieProcessor(cookie_jar))
            login_request = Request(
                url=f"http://127.0.0.1:{port}/api/auth/login",
                data=json.dumps({"username": "user", "password": "password"}).encode(
                    "utf-8"
                ),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with opener.open(login_request, timeout=3) as response:
                payload = json.loads(response.read().decode("utf-8"))
                assert payload == {"authenticated": True}

            with opener.open(f"http://127.0.0.1:{port}/api/hello", timeout=3) as response:
                payload = json.loads(response.read().decode("utf-8"))
                assert payload == {"message": "hello world"}

            with opener.open(f"http://127.0.0.1:{port}/api/board", timeout=3) as response:
                board_payload = json.loads(response.read().decode("utf-8"))
                board = board_payload["board"]
                version = board_payload["version"]
                board["columns"][0]["title"] = "Persisted Column"

            update_request = Request(
                url=f"http://127.0.0.1:{port}/api/board",
                data=json.dumps(
                    {"board": board, "expectedVersion": version}
                ).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="PUT",
            )
            with opener.open(update_request, timeout=3) as response:
                updated_payload = json.loads(response.read().decode("utf-8"))
                assert updated_payload["version"] == version + 1
                assert (
                    updated_payload["board"]["columns"][0]["title"] == "Persisted Column"
                )

            with urlopen(
                f"http://127.0.0.1:{port}/_next/static/app.js",
                timeout=3,
            ) as response:
                javascript = response.read().decode("utf-8")
                assert "kanban" in javascript
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()

        second_port = _pick_free_port()
        second_process = _start_server(backend_root, second_port, env)
        try:
            _wait_for_server(f"http://127.0.0.1:{second_port}/api/health")
            cookie_jar = CookieJar()
            opener = build_opener(HTTPCookieProcessor(cookie_jar))
            login_request = Request(
                url=f"http://127.0.0.1:{second_port}/api/auth/login",
                data=json.dumps({"username": "user", "password": "password"}).encode(
                    "utf-8"
                ),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with opener.open(login_request, timeout=3):
                pass

            with opener.open(f"http://127.0.0.1:{second_port}/api/board", timeout=3) as response:
                persisted_payload = json.loads(response.read().decode("utf-8"))
                assert persisted_payload["board"]["columns"][0]["title"] == "Persisted Column"
        finally:
            second_process.terminate()
            try:
                second_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                second_process.kill()
