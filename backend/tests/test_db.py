from decimal import Decimal

from db import (
    add_card,
    create_deck,
    get_card,
    get_cards_for_deck,
    list_decks_for_user,
    update_card_schedule,
)


def test_create_and_list_decks(dynamodb_tables):
    deck_id = create_deck("user-1", "Biology Chapter 4")
    decks = list_decks_for_user("user-1")

    assert len(decks) == 1
    assert decks[0]["deck_id"] == deck_id
    assert decks[0]["deck_name"] == "Biology Chapter 4"


def test_list_decks_only_returns_matching_user(dynamodb_tables):
    create_deck("user-1", "Deck A")
    create_deck("user-2", "Deck B")

    decks = list_decks_for_user("user-1")

    assert len(decks) == 1
    assert decks[0]["deck_name"] == "Deck A"


def test_add_card_and_query_by_deck(dynamodb_tables):
    deck_id = create_deck("user-1", "Deck")
    card_id = add_card(deck_id, "What is mitosis?", "Cell division producing two identical cells")

    cards = get_cards_for_deck(deck_id)

    assert len(cards) == 1
    assert cards[0]["card_id"] == card_id
    assert cards[0]["easiness_factor"] == Decimal("2.5")


def test_get_card(dynamodb_tables):
    deck_id = create_deck("user-1", "Deck")
    card_id = add_card(deck_id, "Q", "A")

    card = get_card(card_id)

    assert card["front"] == "Q"
    assert card["back"] == "A"
    assert get_card("does-not-exist") is None


def test_update_card_schedule_stores_decimal(dynamodb_tables):
    deck_id = create_deck("user-1", "Deck")
    card_id = add_card(deck_id, "Q", "A")

    update_card_schedule(
        card_id=card_id,
        repetitions=1,
        interval_days=6,
        easiness_factor=2.7,
        last_reviewed="2026-01-01",
        next_review="2026-01-07",
    )

    card = get_card(card_id)
    assert card["easiness_factor"] == Decimal("2.7")
    assert card["interval_days"] == 6
    assert card["next_review"] == "2026-01-07"
