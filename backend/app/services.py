from pathlib import Path
from typing import Any

from fastapi import HTTPException, Request, Response

from .ai import AIConfigError, AIRequestError
from .models import (
    AIChatRequest,
    AIChatResponse,
    BoardDetailResponse,
    BoardListResponse,
    BoardMember,
    BoardMembersResponse,
    BoardMeta,
    BoardResponse,
    BoardUpdateRequest,
    CredentialsRequest,
    RegisterRequest,
    SessionResponse,
)
from .repository import (
    BoardNotFoundError,
    LastBoardError,
    ShareError,
    UsernameTakenError,
    UserNotFoundError,
    VersionConflictError,
    add_board_member,
    authenticate_user,
    create_board,
    create_session,
    create_user,
    delete_board,
    delete_session,
    get_board_by_id,
    get_default_board_id,
    get_session_user,
    list_board_members,
    list_boards,
    remove_board_member,
    rename_board,
    update_board_by_id,
)

SESSION_COOKIE_NAME = "pm_session"
SESSION_MAX_AGE_SECONDS = 60 * 60 * 24


# ---------------------------------------------------------------------------
# Session resolution
# ---------------------------------------------------------------------------


def _session_token(request: Request) -> str:
    return request.cookies.get(SESSION_COOKIE_NAME, "")


def resolve_user(request: Request, db_path: Path | None = None) -> dict | None:
    return get_session_user(_session_token(request), db_path=db_path)


def require_user(request: Request, db_path: Path | None = None) -> dict:
    user = resolve_user(request, db_path=db_path)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def session_status(request: Request, db_path: Path | None = None) -> SessionResponse:
    user = resolve_user(request, db_path=db_path)
    if user is None:
        return SessionResponse(authenticated=False)
    return SessionResponse(authenticated=True, username=user["username"])


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=SESSION_MAX_AGE_SECONDS,
        path="/",
    )


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def register(
    payload: RegisterRequest, response: Response, db_path: Path | None = None
) -> SessionResponse:
    try:
        user_id = create_user(payload.username, payload.password, db_path=db_path)
    except UsernameTakenError as error:
        raise HTTPException(status_code=409, detail="Username already taken") from error

    token = create_session(user_id, db_path=db_path)
    _set_session_cookie(response, token)
    return SessionResponse(authenticated=True, username=payload.username)


def login(
    payload: CredentialsRequest, response: Response, db_path: Path | None = None
) -> SessionResponse:
    user = authenticate_user(payload.username, payload.password, db_path=db_path)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_session(user["id"], db_path=db_path)
    _set_session_cookie(response, token)
    return SessionResponse(authenticated=True, username=user["username"])


def logout(request: Request, response: Response, db_path: Path | None = None) -> None:
    delete_session(_session_token(request), db_path=db_path)
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")


# ---------------------------------------------------------------------------
# Boards
# ---------------------------------------------------------------------------


def list_user_boards(
    request: Request, db_path: Path | None = None
) -> BoardListResponse:
    user = require_user(request, db_path=db_path)
    boards = list_boards(user["id"], db_path=db_path)
    return BoardListResponse(boards=[BoardMeta(**board) for board in boards])


def create_user_board(
    request: Request, name: str, db_path: Path | None = None
) -> BoardMeta:
    user = require_user(request, db_path=db_path)
    meta = create_board(user["id"], name, db_path=db_path)
    return BoardMeta(**meta)


def get_board_detail(
    request: Request, board_id: int, db_path: Path | None = None
) -> BoardDetailResponse:
    user = require_user(request, db_path=db_path)
    try:
        board_data, version, name = get_board_by_id(
            board_id, user["id"], db_path=db_path
        )
    except BoardNotFoundError as error:
        raise HTTPException(status_code=404, detail="Board not found") from error
    return BoardDetailResponse(id=board_id, name=name, board=board_data, version=version)


def save_board_detail(
    request: Request,
    board_id: int,
    payload: BoardUpdateRequest,
    db_path: Path | None = None,
) -> BoardDetailResponse:
    user = require_user(request, db_path=db_path)
    board_dict = payload.board.model_dump()
    try:
        version = update_board_by_id(
            board_id,
            user["id"],
            board=board_dict,
            expected_version=payload.expectedVersion,
            db_path=db_path,
        )
    except BoardNotFoundError as error:
        raise HTTPException(status_code=404, detail="Board not found") from error
    except VersionConflictError as conflict:
        raise HTTPException(
            status_code=409,
            detail=f"Version conflict. Current version is {conflict.current_version}.",
        ) from conflict
    # name is unchanged by a board save; re-read is unnecessary, reuse request name.
    _, _, name = get_board_by_id(board_id, user["id"], db_path=db_path)
    return BoardDetailResponse(id=board_id, name=name, board=payload.board, version=version)


def rename_user_board(
    request: Request, board_id: int, name: str, db_path: Path | None = None
) -> BoardMeta:
    user = require_user(request, db_path=db_path)
    try:
        meta = rename_board(board_id, user["id"], name, db_path=db_path)
    except BoardNotFoundError as error:
        raise HTTPException(status_code=404, detail="Board not found") from error
    return BoardMeta(**meta)


def delete_user_board(
    request: Request, board_id: int, db_path: Path | None = None
) -> None:
    user = require_user(request, db_path=db_path)
    try:
        delete_board(board_id, user["id"], db_path=db_path)
    except BoardNotFoundError as error:
        raise HTTPException(status_code=404, detail="Board not found") from error
    except LastBoardError as error:
        raise HTTPException(
            status_code=409, detail="Cannot delete the only remaining board"
        ) from error


# ---------------------------------------------------------------------------
# Board members (sharing)
# ---------------------------------------------------------------------------


def list_board_members_for_user(
    request: Request, board_id: int, db_path: Path | None = None
) -> BoardMembersResponse:
    user = require_user(request, db_path=db_path)
    try:
        members = list_board_members(board_id, user["id"], db_path=db_path)
    except BoardNotFoundError as error:
        raise HTTPException(status_code=404, detail="Board not found") from error
    return BoardMembersResponse(members=[BoardMember(**member) for member in members])


def add_board_member_for_user(
    request: Request,
    board_id: int,
    username: str,
    role: str,
    db_path: Path | None = None,
) -> BoardMember:
    user = require_user(request, db_path=db_path)
    try:
        member = add_board_member(
            board_id, user["id"], username, role=role, db_path=db_path
        )
    except BoardNotFoundError as error:
        raise HTTPException(status_code=404, detail="Board not found") from error
    except UserNotFoundError as error:
        raise HTTPException(status_code=404, detail="User not found") from error
    except ShareError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return BoardMember(**member)


def remove_board_member_for_user(
    request: Request,
    board_id: int,
    username: str,
    db_path: Path | None = None,
) -> None:
    user = require_user(request, db_path=db_path)
    try:
        remove_board_member(board_id, user["id"], username, db_path=db_path)
    except BoardNotFoundError as error:
        raise HTTPException(status_code=404, detail="Board not found") from error
    except UserNotFoundError as error:
        raise HTTPException(status_code=404, detail="User not found") from error


# ---------------------------------------------------------------------------
# Legacy single-board endpoints (operate on the user's default board)
# ---------------------------------------------------------------------------


def read_board(request: Request, db_path: Path | None = None) -> BoardResponse:
    user = require_user(request, db_path=db_path)
    board_id = get_default_board_id(user["id"], db_path=db_path)
    board_data, version, _ = get_board_by_id(board_id, user["id"], db_path=db_path)
    return BoardResponse(board=board_data, version=version)


def save_board(
    request: Request,
    payload: BoardUpdateRequest,
    db_path: Path | None = None,
) -> BoardResponse:
    user = require_user(request, db_path=db_path)
    board_id = get_default_board_id(user["id"], db_path=db_path)
    board_dict = payload.board.model_dump()
    try:
        version = update_board_by_id(
            board_id,
            user["id"],
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


# ---------------------------------------------------------------------------
# AI chat (scoped to a board)
# ---------------------------------------------------------------------------


def run_ai_chat_for_board(
    request: Request,
    board_id: int,
    payload: AIChatRequest,
    ai_client: Any,
    db_path: Path | None = None,
) -> AIChatResponse:
    user = require_user(request, db_path=db_path)
    try:
        board_dict, version, _ = get_board_by_id(
            board_id, user["id"], db_path=db_path
        )
    except BoardNotFoundError as error:
        raise HTTPException(status_code=404, detail="Board not found") from error

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
        next_version = update_board_by_id(
            board_id,
            user["id"],
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


def run_ai_chat(
    request: Request,
    payload: AIChatRequest,
    ai_client: Any,
    db_path: Path | None = None,
) -> AIChatResponse:
    """Legacy AI chat: operates on the user's default board."""
    user = require_user(request, db_path=db_path)
    board_id = get_default_board_id(user["id"], db_path=db_path)
    return run_ai_chat_for_board(
        request=request,
        board_id=board_id,
        payload=payload,
        ai_client=ai_client,
        db_path=db_path,
    )
