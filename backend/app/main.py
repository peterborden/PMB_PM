import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from .ai import AIConfigError, AIRequestError, OpenRouterClient
from .models import (
    AIChatRequest,
    AIChatResponse,
    BoardDetailResponse,
    BoardListResponse,
    BoardMeta,
    BoardResponse,
    BoardUpdateRequest,
    CreateBoardRequest,
    CredentialsRequest,
    RegisterRequest,
    RenameBoardRequest,
    SessionResponse,
)
from .repository import initialize_database
from .services import (
    create_user_board,
    delete_user_board,
    get_board_detail,
    list_user_boards,
    login,
    logout,
    read_board,
    register,
    rename_user_board,
    require_user,
    run_ai_chat,
    run_ai_chat_for_board,
    save_board,
    save_board_detail,
    session_status,
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

    @app.get("/api/auth/session", response_model=SessionResponse)
    def auth_session(request: Request) -> SessionResponse:
        return session_status(request, db_path=db_path)

    @app.post("/api/auth/register", response_model=SessionResponse)
    def auth_register(payload: RegisterRequest, response: Response) -> SessionResponse:
        return register(payload, response, db_path=db_path)

    @app.post("/api/auth/login", response_model=SessionResponse)
    def auth_login(payload: CredentialsRequest, response: Response) -> SessionResponse:
        return login(payload, response, db_path=db_path)

    @app.post("/api/auth/logout", response_model=SessionResponse)
    def auth_logout(request: Request, response: Response) -> SessionResponse:
        logout(request, response, db_path=db_path)
        return SessionResponse(authenticated=False)

    @app.get("/api/hello")
    def hello(request: Request) -> dict[str, str]:
        require_user(request, db_path=db_path)
        return {"message": "hello world"}

    @app.get("/api/ai/diagnostic", response_model=AIDiagnosticResponse)
    def ai_diagnostic(request: Request) -> AIDiagnosticResponse:
        require_user(request, db_path=db_path)
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

    @app.post("/api/boards/{board_id}/ai/chat", response_model=AIChatResponse)
    def board_ai_chat(
        board_id: int, request: Request, payload: AIChatRequest
    ) -> AIChatResponse:
        if resolved_ai_client is None:
            raise HTTPException(status_code=503, detail="OPENROUTER_API_KEY is not configured")
        return run_ai_chat_for_board(
            request=request,
            board_id=board_id,
            payload=payload,
            ai_client=resolved_ai_client,
            db_path=db_path,
        )

    @app.get("/api/boards", response_model=BoardListResponse)
    def get_boards(request: Request) -> BoardListResponse:
        return list_user_boards(request, db_path=db_path)

    @app.post("/api/boards", response_model=BoardMeta, status_code=201)
    def post_board(request: Request, payload: CreateBoardRequest) -> BoardMeta:
        return create_user_board(request, payload.name, db_path=db_path)

    @app.get("/api/boards/{board_id}", response_model=BoardDetailResponse)
    def get_board_by_id_route(board_id: int, request: Request) -> BoardDetailResponse:
        return get_board_detail(request, board_id, db_path=db_path)

    @app.put("/api/boards/{board_id}", response_model=BoardDetailResponse)
    def put_board_by_id(
        board_id: int, request: Request, payload: BoardUpdateRequest
    ) -> BoardDetailResponse:
        return save_board_detail(request, board_id, payload, db_path=db_path)

    @app.patch("/api/boards/{board_id}", response_model=BoardMeta)
    def patch_board(
        board_id: int, request: Request, payload: RenameBoardRequest
    ) -> BoardMeta:
        return rename_user_board(request, board_id, payload.name, db_path=db_path)

    @app.delete("/api/boards/{board_id}", status_code=204)
    def delete_board_route(board_id: int, request: Request) -> Response:
        delete_user_board(request, board_id, db_path=db_path)
        return Response(status_code=204)

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
