from pathlib import Path
from typing import Any

from fastapi import HTTPException, Request, Response
from pydantic import BaseModel

from .ai import AIConfigError, AIRequestError
from .models import AIChatRequest, AIChatResponse, BoardResponse, BoardUpdateRequest
from .repository import (
    MVP_USERNAME,
    VersionConflictError,
    get_board,
    update_board,
)

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


def run_ai_chat(
    request: Request,
    payload: AIChatRequest,
    ai_client: Any,
    db_path: Path | None = None,
) -> AIChatResponse:
    username = require_authenticated_username(request)
    board_dict, version = get_board(username, db_path=db_path)

    history = [message.model_dump() for message in payload.history]
    try:
        ai_result = ai_client.run_board_assistant(
            board=board_dict,
            history=history,
            user_message=payload.message,
        )
    except AIConfigError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except AIRequestError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error

    updated_board = ai_result.get("updatedBoard")
    if updated_board is None:
        return AIChatResponse(
            reply=ai_result["reply"],
            boardUpdated=False,
            board=board_dict,
            version=version,
        )

    try:
        next_version = update_board(
            username=username,
            board=updated_board,
            expected_version=version,
            db_path=db_path,
        )
    except VersionConflictError as conflict:
        raise HTTPException(
            status_code=409,
            detail=f"Version conflict. Current version is {conflict.current_version}.",
        ) from conflict

    return AIChatResponse(
        reply=ai_result["reply"],
        boardUpdated=True,
        board=updated_board,
        version=next_version,
    )
