from pydantic import BaseModel, Field, model_validator


class Card(BaseModel):
    id: str
    title: str
    details: str


class Column(BaseModel):
    id: str
    title: str
    cardIds: list[str] = Field(default_factory=list)


class BoardData(BaseModel):
    columns: list[Column]
    cards: dict[str, Card]

    @model_validator(mode="after")
    def validate_card_references(self) -> "BoardData":
        card_ids_from_columns = [card_id for col in self.columns for card_id in col.cardIds]
        missing_ids = sorted({card_id for card_id in card_ids_from_columns if card_id not in self.cards})
        if missing_ids:
            raise ValueError(f"Missing cards for ids: {', '.join(missing_ids)}")

        mismatched_ids = sorted(
            card_key for card_key, card in self.cards.items() if card.id != card_key
        )
        if mismatched_ids:
            raise ValueError(f"Card ids do not match keys: {', '.join(mismatched_ids)}")

        return self


class BoardResponse(BaseModel):
    board: BoardData
    version: int


class BoardUpdateRequest(BaseModel):
    board: BoardData
    expectedVersion: int | None = None
