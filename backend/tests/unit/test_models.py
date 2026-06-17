import copy

import pytest

from app.models import BoardData
from app.repository import DEFAULT_BOARD


def test_board_model_accepts_default_board() -> None:
    board = BoardData.model_validate(DEFAULT_BOARD)
    assert len(board.columns) == 5
    assert "card-1" in board.cards


def test_board_model_rejects_missing_card_references() -> None:
    invalid_board = copy.deepcopy(DEFAULT_BOARD)
    invalid_board["columns"][0]["cardIds"].append("card-does-not-exist")

    with pytest.raises(ValueError):
        BoardData.model_validate(invalid_board)


def test_board_model_rejects_card_key_mismatch() -> None:
    invalid_board = copy.deepcopy(DEFAULT_BOARD)
    invalid_board["cards"]["card-1"]["id"] = "different-id"

    with pytest.raises(ValueError):
        BoardData.model_validate(invalid_board)


def test_board_model_rejects_duplicate_column_ids() -> None:
    invalid_board = copy.deepcopy(DEFAULT_BOARD)
    invalid_board["columns"][1]["id"] = invalid_board["columns"][0]["id"]

    with pytest.raises(ValueError, match="Duplicate column ids"):
        BoardData.model_validate(invalid_board)


def test_board_model_rejects_card_in_multiple_columns() -> None:
    invalid_board = copy.deepcopy(DEFAULT_BOARD)
    invalid_board["columns"][1]["cardIds"].append("card-1")

    with pytest.raises(ValueError, match="multiple columns"):
        BoardData.model_validate(invalid_board)


def test_board_model_rejects_orphan_cards() -> None:
    invalid_board = copy.deepcopy(DEFAULT_BOARD)
    invalid_board["cards"]["card-orphan"] = {
        "id": "card-orphan",
        "title": "Orphan",
        "details": "Not placed in any column.",
    }

    with pytest.raises(ValueError, match="not placed in any column"):
        BoardData.model_validate(invalid_board)
