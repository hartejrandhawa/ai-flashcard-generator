from decimal import Decimal

import pytest

from db import (
    NEW_CARD_DUE,
    ConflictError,
    add_card,
    add_cards,
    consume_generation_quota,
    create_deck,
    delete_card,
    delete_deck,
    get_card,
    get_cards_for_deck,
    get_deck,
    get_owned_card,
    get_owned_deck,
    list_decks_for_user,
    rename_deck,
    update_card_schedule,
    update_card_text,
)


def test_create_and_list_decks(dynamodb_tables):
    deck_id = create_deck("user-1", "Biology Chapter 4")
    decks = list_decks_for_user("user-1")

    assert len(decks) == 1
    assert decks[0]["deck_id"] == deck_id
    assert decks[0]["deck_name"] == "Biology Chapter 4"
    assert decks[0]["status"] == "ready"


def test_list_decks_only_returns_matching_user(dynamodb_tables):
    create_deck("user-1", "Deck A")
    create_deck("user-2", "Deck B")

    decks = list_decks_for_user("user-1")

    assert len(decks) == 1
    assert decks[0]["deck_name"] == "Deck A"


def test_owned_deck_hides_other_users_decks(dynamodb_tables):
    deck_id = create_deck("user-1", "Mine")
    assert get_owned_deck(deck_id, "user-1")["deck_name"] == "Mine"
    assert get_owned_deck(deck_id, "user-2") is None
    assert get_owned_deck("missing", "user-1") is None


def test_rename_deck(dynamodb_tables):
    deck_id = create_deck("user-1", "Old")
    rename_deck(deck_id, "New")
    assert get_deck(deck_id)["deck_name"] == "New"


def test_add_card_and_query_by_deck(dynamodb_tables):
    deck_id = create_deck("user-1", "Deck")
    card_id = add_card(
        deck_id, "What is mitosis?", "Cell division producing two identical cells"
    )

    cards = get_cards_for_deck(deck_id)

    assert len(cards) == 1
    assert cards[0]["card_id"] == card_id
    assert cards[0]["easiness_factor"] == Decimal("2.5")


def test_new_cards_are_due_regardless_of_timezone(dynamodb_tables):
    deck_id = create_deck("user-1", "Deck")
    card_id = add_card(deck_id, "Q", "A")
    assert get_card(card_id)["next_review"] == NEW_CARD_DUE


def test_add_cards_writes_more_than_one_batch(dynamodb_tables):
    deck_id = create_deck("user-1", "Deck")
    added = add_cards(deck_id, [{"front": f"Q{i}", "back": "A"} for i in range(60)])

    assert added == 60
    assert len(get_cards_for_deck(deck_id)) == 60


def test_get_card(dynamodb_tables):
    deck_id = create_deck("user-1", "Deck")
    card_id = add_card(deck_id, "Q", "A")

    card = get_card(card_id)

    assert card["front"] == "Q"
    assert card["back"] == "A"
    assert get_card("does-not-exist") is None


def test_owned_card_resolves_through_deck(dynamodb_tables):
    deck_id = create_deck("user-1", "Deck")
    card_id = add_card(deck_id, "Q", "A")

    assert get_owned_card(card_id, "user-1")["card_id"] == card_id
    assert get_owned_card(card_id, "user-2") is None


def test_update_and_delete_card(dynamodb_tables):
    deck_id = create_deck("user-1", "Deck")
    card_id = add_card(deck_id, "Q", "A")

    update_card_text(card_id, "Q2", "A2")
    assert (get_card(card_id)["front"], get_card(card_id)["back"]) == ("Q2", "A2")

    delete_card(card_id)
    assert get_card(card_id) is None


def test_delete_deck_removes_its_cards_only(dynamodb_tables):
    keep = create_deck("user-1", "Keep")
    drop = create_deck("user-1", "Drop")
    add_card(keep, "K", "A")
    add_cards(drop, [{"front": f"Q{i}", "back": "A"} for i in range(30)])

    delete_deck(drop)

    assert get_deck(drop) is None
    assert get_cards_for_deck(drop) == []
    assert len(get_cards_for_deck(keep)) == 1


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


def test_conditional_schedule_update_rejects_stale_state(dynamodb_tables):
    deck_id = create_deck("user-1", "Deck")
    card_id = add_card(deck_id, "Q", "A")
    common = dict(
        card_id=card_id,
        interval_days=1,
        easiness_factor=2.5,
        last_reviewed="2026-01-01",
        expected_repetitions=0,
        expected_next_review=NEW_CARD_DUE,
    )

    update_card_schedule(
        repetitions=1, next_review="2026-01-02", **common
    )  # first review wins
    with pytest.raises(ConflictError):
        update_card_schedule(
            repetitions=1, next_review="2026-01-02", **common
        )  # same stale read


def test_generation_quota_counts_and_stops_at_limit(dynamodb_tables):
    results = [consume_generation_quota("user-1", 3, "2026-01-01") for _ in range(5)]
    assert results == [True, True, True, False, False]
    # A different day or a different user has its own counter.
    assert consume_generation_quota("user-1", 3, "2026-01-02") is True
    assert consume_generation_quota("user-2", 3, "2026-01-01") is True


def test_quota_items_never_show_up_as_decks(dynamodb_tables):
    consume_generation_quota("user-1", 3, "2026-01-01")
    assert list_decks_for_user("user-1") == []
