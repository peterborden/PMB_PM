from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

USERNAME_MIN_LENGTH = 3
USERNAME_MAX_LENGTH = 32
PASSWORD_MIN_LENGTH = 8
BOARD_NAME_MAX_LENGTH = 80


class CredentialsRequest(BaseModel):
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def _normalize_username(cls, value: str) -> str:
        return value.strip()


class RegisterRequest(CredentialsRequest):
    @field_validator("username")
    @classmethod
    def _validate_username(cls, value: str) -> str:
        value = value.strip()
        if not (USERNAME_MIN_LENGTH <= len(value) <= USERNAME_MAX_LENGTH):
            raise ValueError(
                f"Username must be between {USERNAME_MIN_LENGTH} and {USERNAME_MAX_LENGTH} characters"
            )
        if not all(char.isalnum() or char in {"-", "_", "."} for char in value):
            raise ValueError(
                "Username may only contain letters, numbers, '-', '_', and '.'"
            )
        return value

    @field_validator("password")
    @classmethod
    def _validate_password(cls, value: str) -> str:
        if len(value) < PASSWORD_MIN_LENGTH:
            raise ValueError(
                f"Password must be at least {PASSWORD_MIN_LENGTH} characters"
            )
        return value


class SessionResponse(BaseModel):
    authenticated: bool
    username: str | None = None


class BoardName(BaseModel):
    name: str = Field(default="My Board")

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Board name must not be empty")
        if len(value) > BOARD_NAME_MAX_LENGTH:
            raise ValueError(
                f"Board name must be at most {BOARD_NAME_MAX_LENGTH} characters"
            )
        return value


class CreateBoardRequest(BoardName):
    pass


class RenameBoardRequest(BoardName):
    pass


class BoardMeta(BaseModel):
    id: int
    name: str
    version: int
    createdAt: str
    updatedAt: str
    # 'owner' or 'editor' from the requesting user's perspective.
    role: str = "owner"
    ownerUsername: str | None = None


class BoardListResponse(BaseModel):
    boards: list[BoardMeta]


class AddMemberRequest(BaseModel):
    username: str
    role: Literal["editor"] = "editor"

    @field_validator("username")
    @classmethod
    def _normalize_username(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Username must not be empty")
        return trimmed


class BoardMember(BaseModel):
    username: str
    role: str


class BoardMembersResponse(BaseModel):
    members: list[BoardMember]


CARD_MAX_LABELS = 10
CARD_LABEL_MAX_LENGTH = 24


class Card(BaseModel):
    id: str
    title: str
    details: str
    # Optional metadata. Defaults keep older board_json (without these keys)
    # valid, so the fields are backward compatible.
    labels: list[str] = Field(default_factory=list)
    dueDate: str | None = None
    # Username of the assigned board participant (owner or member), or None.
    assignee: str | None = None

    @field_validator("assignee")
    @classmethod
    def _normalize_assignee(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            return None
        if len(trimmed) > USERNAME_MAX_LENGTH:
            raise ValueError(
                f"assignee must be at most {USERNAME_MAX_LENGTH} characters"
            )
        return trimmed

    @field_validator("labels")
    @classmethod
    def _normalize_labels(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        for label in value:
            trimmed = label.strip()
            if not trimmed or trimmed in cleaned:
                continue
            if len(trimmed) > CARD_LABEL_MAX_LENGTH:
                raise ValueError(
                    f"Label must be at most {CARD_LABEL_MAX_LENGTH} characters"
                )
            cleaned.append(trimmed)
        if len(cleaned) > CARD_MAX_LABELS:
            raise ValueError(f"A card may have at most {CARD_MAX_LABELS} labels")
        return cleaned

    @field_validator("dueDate")
    @classmethod
    def _normalize_due_date(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            return None
        # Expect an ISO calendar date (YYYY-MM-DD), the shape an <input type=date> emits.
        try:
            date.fromisoformat(trimmed)
        except ValueError as error:
            raise ValueError("dueDate must be an ISO date (YYYY-MM-DD)") from error
        return trimmed


class Column(BaseModel):
    id: str
    title: str
    cardIds: list[str] = Field(default_factory=list)


class BoardData(BaseModel):
    columns: list[Column]
    cards: dict[str, Card]

    @model_validator(mode="after")
    def validate_card_references(self) -> "BoardData":
        column_ids = [column.id for column in self.columns]
        duplicate_columns = sorted(
            {column_id for column_id in column_ids if column_ids.count(column_id) > 1}
        )
        if duplicate_columns:
            raise ValueError(f"Duplicate column ids: {', '.join(duplicate_columns)}")

        card_ids_from_columns = [card_id for col in self.columns for card_id in col.cardIds]

        missing_ids = sorted({card_id for card_id in card_ids_from_columns if card_id not in self.cards})
        if missing_ids:
            raise ValueError(f"Missing cards for ids: {', '.join(missing_ids)}")

        duplicate_placements = sorted(
            {card_id for card_id in card_ids_from_columns if card_ids_from_columns.count(card_id) > 1}
        )
        if duplicate_placements:
            raise ValueError(
                f"Cards placed in multiple columns: {', '.join(duplicate_placements)}"
            )

        placed_ids = set(card_ids_from_columns)
        orphan_ids = sorted(card_id for card_id in self.cards if card_id not in placed_ids)
        if orphan_ids:
            raise ValueError(f"Cards not placed in any column: {', '.join(orphan_ids)}")

        mismatched_ids = sorted(
            card_key for card_key, card in self.cards.items() if card.id != card_key
        )
        if mismatched_ids:
            raise ValueError(f"Card ids do not match keys: {', '.join(mismatched_ids)}")

        return self


class BoardResponse(BaseModel):
    board: BoardData
    version: int


class BoardDetailResponse(BaseModel):
    id: int
    name: str
    board: BoardData
    version: int


class BoardUpdateRequest(BaseModel):
    board: BoardData
    expectedVersion: int | None = None


class ChatHistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class AIChatRequest(BaseModel):
    message: str
    history: list[ChatHistoryMessage] = Field(default_factory=list)


class AIChatResponse(BaseModel):
    reply: str
    boardUpdated: bool
    board: BoardData
    version: int


class BoardAssistantOutput(BaseModel):
    reply: str
    updatedBoard: BoardData | None = None
