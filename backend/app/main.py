import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from .ai import AIConfigError, AIRequestError, OpenRouterClient
from .models import AIChatRequest, AIChatResponse, BoardResponse, BoardUpdateRequest
from .repository import initialize_database
from .services import (
    LoginRequest,
    login,
    logout,
    read_board,
    require_authenticated_username,
    run_ai_chat,
    save_board,
    session_authenticated,
)

class AIDiagnosticResponse(BaseModel):
    model: str
    prompt: str
    answer: str


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


def create_app(
    frontend_static_dir: Path | None = None,
    db_path: Path | None = None,
    ai_client: Any | None = None,
) -> FastAPI:
    app = FastAPI(
        title="Project Management MVP Backend",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    initialize_database(db_path)
    resolved_frontend_dir = _resolve_frontend_static_dir(frontend_static_dir)
    if ai_client is None:
        try:
            resolved_ai_client = OpenRouterClient.from_env()
        except AIConfigError:
            resolved_ai_client = None
    else:
        resolved_ai_client = ai_client

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/auth/session")
    def auth_session(request: Request) -> dict[str, bool]:
        return {"authenticated": session_authenticated(request)}

    @app.post("/api/auth/login")
    def auth_login(payload: LoginRequest, response: Response) -> dict[str, bool]:
        login(payload, response)
        return {"authenticated": True}

    @app.post("/api/auth/logout")
    def auth_logout(response: Response) -> dict[str, bool]:
        logout(response)
        return {"authenticated": False}

    @app.get("/api/hello")
    def hello(request: Request) -> dict[str, str]:
        require_authenticated_username(request)
        return {"message": "hello world"}

    @app.get("/api/ai/diagnostic", response_model=AIDiagnosticResponse)
    def ai_diagnostic(request: Request) -> AIDiagnosticResponse:
        require_authenticated_username(request)
        if resolved_ai_client is None:
            raise HTTPException(status_code=503, detail="OPENROUTER_API_KEY is not configured")
        try:
            result = resolved_ai_client.run_diagnostic()
        except AIConfigError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        except AIRequestError as error:
            raise HTTPException(status_code=502, detail=str(error)) from error
        return AIDiagnosticResponse(**result)

    @app.post("/api/ai/chat", response_model=AIChatResponse)
    def ai_chat(request: Request, payload: AIChatRequest) -> AIChatResponse:
        if resolved_ai_client is None:
            raise HTTPException(status_code=503, detail="OPENROUTER_API_KEY is not configured")
        return run_ai_chat(
            request=request,
            payload=payload,
            ai_client=resolved_ai_client,
            db_path=db_path,
        )

    @app.get("/api/board", response_model=BoardResponse)
    def get_board(request: Request) -> BoardResponse:
        return read_board(request, db_path=db_path)

    @app.put("/api/board", response_model=BoardResponse)
    def put_board(request: Request, payload: BoardUpdateRequest) -> BoardResponse:
        return save_board(request, payload, db_path=db_path)

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
