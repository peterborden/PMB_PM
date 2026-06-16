from pathlib import Path

from fastapi import HTTPException, Request, Response
from pydantic import BaseModel

from .models import BoardResponse, BoardUpdateRequest
from .repository import MVP_USERNAME, VersionConflictError, get_board, update_board

SESSION_COOKIE_NAME = "pm_session"
SESSION_COOKIE_VALUE = "authenticated"
SESSION_MAX_AGE_SECONDS = 60 * 60 * 24
VALID_USERNAME = "user"
VALID_PASSWORD = "password"


class LoginRequest(BaseModel):
    username: str
    password: str


def validate_credentials(username: str, password: str) -> bool:
    return username == VALID_USERNAME and password == VALID_PASSWORD


def session_authenticated(request: Request) -> bool:
    return request.cookies.get(SESSION_COOKIE_NAME) == SESSION_COOKIE_VALUE


def require_authenticated_username(request: Request) -> str:
    if not session_authenticated(request):
        raise HTTPException(status_code=401, detail="Authentication required")
    return MVP_USERNAME


def login(payload: LoginRequest, response: Response) -> None:
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


def logout(response: Response) -> None:
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")


def read_board(request: Request, db_path: Path | None = None) -> BoardResponse:
    username = require_authenticated_username(request)
    board_data, version = get_board(username, db_path=db_path)
    return BoardResponse(board=board_data, version=version)


def save_board(
    request: Request,
    payload: BoardUpdateRequest,
    db_path: Path | None = None,
) -> BoardResponse:
    username = require_authenticated_username(request)
    board_dict = payload.board.model_dump()
    try:
        version = update_board(
            username,
            board=board_dict,
            expected_version=payload.expectedVersion,
            db_path=db_path,
        )
    except VersionConflictError as conflict:
        raise HTTPException(
            status_code=409,
            detail=f"Version conflict. Current version is {conflict.current_version}.",
        ) from conflict

    return BoardResponse(board=payload.board, version=version)
