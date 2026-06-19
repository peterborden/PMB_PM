import copy

import pytest

from app.models import Card
from app.repository import DEFAULT_BOARD
from app.models import BoardData


def test_card_defaults_have_empty_labels_and_no_due_date() -> None:
    card = Card(id="card-1", title="Title", details="Details")
    assert card.labels == []
    assert card.dueDate is None


def test_card_accepts_labels_and_iso_due_date() -> None:
    card = Card(
        id="card-1",
        title="Title",
        details="Details",
        labels=["urgent", "backend"],
        dueDate="2026-07-01",
    )
    assert card.labels == ["urgent", "backend"]
    assert card.dueDate == "2026-07-01"


def test_card_labels_are_trimmed_deduped_and_emptied() -> None:
    card = Card(
        id="card-1",
        title="Title",
        details="Details",
        labels=["  urgent ", "urgent", "", "  "],
    )
    assert card.labels == ["urgent"]


def test_card_blank_due_date_becomes_none() -> None:
    card = Card(id="card-1", title="Title", details="Details", dueDate="   ")
    assert card.dueDate is None


def test_card_defaults_have_no_assignee() -> None:
    card = Card(id="card-1", title="Title", details="Details")
    assert card.assignee is None


def test_card_accepts_and_trims_assignee() -> None:
    card = Card(id="card-1", title="Title", details="Details", assignee="  alice ")
    assert card.assignee == "alice"


def test_card_blank_assignee_becomes_none() -> None:
    card = Card(id="card-1", title="Title", details="Details", assignee="")
    assert card.assignee is None


def test_card_rejects_invalid_due_date() -> None:
    with pytest.raises(ValueError):
        Card(id="card-1", title="Title", details="Details", dueDate="not-a-date")


def test_card_rejects_too_many_labels() -> None:
    with pytest.raises(ValueError):
        Card(
            id="card-1",
            title="Title",
            details="Details",
            labels=[f"label-{index}" for index in range(11)],
        )


def test_default_board_still_validates_without_metadata() -> None:
    board = BoardData.model_validate(DEFAULT_BOARD)
    assert board.cards["card-1"].labels == []
    assert board.cards["card-1"].dueDate is None


def test_board_round_trips_card_metadata() -> None:
    board_dict = copy.deepcopy(DEFAULT_BOARD)
    board_dict["cards"]["card-1"]["labels"] = ["urgent"]
    board_dict["cards"]["card-1"]["dueDate"] = "2026-07-01"
    board = BoardData.model_validate(board_dict)
    dumped = board.model_dump()
    assert dumped["cards"]["card-1"]["labels"] == ["urgent"]
    assert dumped["cards"]["card-1"]["dueDate"] == "2026-07-01"
