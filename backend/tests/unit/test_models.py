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
