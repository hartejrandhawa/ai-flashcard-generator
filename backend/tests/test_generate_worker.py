from unittest.mock import patch

from db import (
    STATUS_FAILED,
    STATUS_GENERATING,
    STATUS_READY,
    claim_generation,
    create_deck,
    delete_deck,
    get_cards_for_deck,
    get_deck,
    set_deck_status,
)
from generate_worker import GENERIC_FAILURE, handler
from llm import GenerationError

CARDS = [{"front": "Q1", "back": "A1"}, {"front": "Q2", "back": "A2"}]


def _deck():
    return create_deck("user-1", "Bio", STATUS_GENERATING)


def test_success_saves_cards_and_marks_ready(dynamodb_tables):
    deck_id = _deck()
    with patch("generate_worker.generate_cards", return_value=CARDS):
        handler({"deck_id": deck_id, "notes_text": "notes"}, None)

    deck = get_deck(deck_id)
    assert deck["status"] == STATUS_READY
    assert deck["card_count"] == 2
    assert {c["front"] for c in get_cards_for_deck(deck_id)} == {"Q1", "Q2"}


def test_generation_error_marks_failed_with_user_message(dynamodb_tables):
    deck_id = _deck()
    with patch(
        "generate_worker.generate_cards",
        side_effect=GenerationError("Too long, try less"),
    ):
        handler({"deck_id": deck_id, "notes_text": "notes"}, None)

    deck = get_deck(deck_id)
    assert deck["status"] == STATUS_FAILED
    assert deck["error"] == "Too long, try less"
    assert get_cards_for_deck(deck_id) == []


def test_unexpected_error_marks_failed_without_leaking_details(dynamodb_tables):
    deck_id = _deck()
    with patch(
        "generate_worker.generate_cards",
        side_effect=RuntimeError("db password is hunter2"),
    ):
        handler({"deck_id": deck_id, "notes_text": "notes"}, None)

    deck = get_deck(deck_id)
    assert deck["status"] == STATUS_FAILED
    assert deck["error"] == GENERIC_FAILURE


def test_redelivered_event_does_not_call_the_model_again(dynamodb_tables):
    deck_id = _deck()
    set_deck_status(deck_id, STATUS_READY, card_count=2)
    with patch("generate_worker.generate_cards") as gen:
        handler({"deck_id": deck_id, "notes_text": "notes"}, None)
    gen.assert_not_called()


def test_deleted_deck_is_skipped(dynamodb_tables):
    with patch("generate_worker.generate_cards") as gen:
        handler({"deck_id": "gone", "notes_text": "notes"}, None)
    gen.assert_not_called()
    assert get_deck("gone") is None  # no ownerless item created


def test_only_one_concurrent_delivery_claims_the_deck(dynamodb_tables):
    deck_id = _deck()
    assert claim_generation(deck_id) is True
    # A duplicate delivery arriving while the first is still running.
    with patch("generate_worker.generate_cards") as gen:
        handler({"deck_id": deck_id, "notes_text": "notes"}, None)
    gen.assert_not_called()


def test_deck_deleted_during_generation_leaves_nothing_behind(dynamodb_tables):
    deck_id = _deck()

    def generate_then_user_deletes(_notes):
        delete_deck(deck_id)
        return CARDS

    with patch("generate_worker.generate_cards", side_effect=generate_then_user_deletes):
        handler({"deck_id": deck_id, "notes_text": "notes"}, None)

    assert get_deck(deck_id) is None
    assert get_cards_for_deck(deck_id) == []
