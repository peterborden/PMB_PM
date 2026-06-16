import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

SESSION_COOKIE_NAME = "pm_session"
SESSION_COOKIE_VALUE = "authenticated"
SESSION_MAX_AGE_SECONDS = 60 * 60 * 24
VALID_USERNAME = "user"
VALID_PASSWORD = "password"


def _default_frontend_static_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "frontend" / "out"


def _resolve_frontend_static_dir(static_dir: Path | None = None) -> Path | None:
    configured = static_dir or Path(
        os.getenv("FRONTEND_STATIC_DIR", str(_default_frontend_static_dir()))
    )
    if not configured.exists():
        return None

    index_file = configured / "index.html"
    if not index_file.exists():
        return None

    return configured.resolve()


def _frontend_unavailable_html() -> str:
    return """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Frontend build missing</title>
  </head>
  <body>
    <main style="max-width: 720px; margin: 48px auto; font-family: sans-serif;">
      <h1>Frontend static build not found.</h1>
      <p>Build the frontend export or set FRONTEND_STATIC_DIR.</p>
    </main>
  </body>
</html>
"""


def _is_authenticated(request: Request) -> bool:
    return request.cookies.get(SESSION_COOKIE_NAME) == SESSION_COOKIE_VALUE


def _require_authenticated(request: Request) -> None:
    if not _is_authenticated(request):
        raise HTTPException(status_code=401, detail="Authentication required")


def validate_credentials(username: str, password: str) -> bool:
    return username == VALID_USERNAME and password == VALID_PASSWORD


class LoginRequest(BaseModel):
    username: str
    password: str


def create_app(frontend_static_dir: Path | None = None) -> FastAPI:
    app = FastAPI(
        title="Project Management MVP Backend",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    resolved_frontend_dir = _resolve_frontend_static_dir(frontend_static_dir)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/auth/session")
    def auth_session(request: Request) -> dict[str, bool]:
        return {"authenticated": _is_authenticated(request)}

    @app.post("/api/auth/login")
    def auth_login(payload: LoginRequest, response: Response) -> dict[str, bool]:
        if not validate_credentials(payload.username, payload.password):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=SESSION_COOKIE_VALUE,
            httponly=True,
            samesite="lax",
            max_age=SESSION_MAX_AGE_SECONDS,
            path="/",
        )
        return {"authenticated": True}

    @app.post("/api/auth/logout")
    def auth_logout(response: Response) -> dict[str, bool]:
        response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")
        return {"authenticated": False}

    @app.get("/api/hello")
    def hello(request: Request) -> dict[str, str]:
        _require_authenticated(request)
        return {"message": "hello world"}

    @app.get("/{path:path}")
    def serve_frontend(path: str = ""):
        if path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")

        if resolved_frontend_dir is None:
            return HTMLResponse(content=_frontend_unavailable_html(), status_code=503)

        if path == "":
            return FileResponse(resolved_frontend_dir / "index.html")

        requested_path = (resolved_frontend_dir / path).resolve()
        if not requested_path.is_relative_to(resolved_frontend_dir):
            raise HTTPException(status_code=404, detail="Not found")

        if requested_path.is_file():
            return FileResponse(requested_path)

        directory_index = requested_path / "index.html"
        if directory_index.is_file():
            return FileResponse(directory_index)

        if "." in Path(path).name:
            raise HTTPException(status_code=404, detail="Not found")

        return FileResponse(resolved_frontend_dir / "index.html")

    return app


app = create_app()
