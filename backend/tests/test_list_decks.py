import json

from db import (
    STATUS_FAILED,
    STATUS_GENERATING,
    add_card,
    add_cards,
    create_deck,
    set_deck_status,
    update_card_schedule,
)
from list_decks import handler


def _decks(res):
    return json.loads(res["body"])["decks"]


def test_returns_counts_status_and_only_own_decks(dynamodb_tables, make_event):
    mine = create_deck("user-1", "Mine")
    add_cards(mine, [{"front": "Q1", "back": "A"}, {"front": "Q2", "back": "A"}])
    create_deck("user-2", "Theirs")

    res = handler(make_event(), None)

    assert res["statusCode"] == 200
    (deck,) = _decks(res)
    assert deck["deck_name"] == "Mine"
    assert deck["status"] == "ready"
    assert deck["card_count"] == 2
    assert deck["due_count"] == 2


def test_due_count_excludes_cards_scheduled_in_the_future(dynamodb_tables, make_event):
    deck_id = create_deck("user-1", "Deck")
    card_id = add_card(deck_id, "Q", "A")
    add_card(deck_id, "Q2", "A2")
    update_card_schedule(card_id, 1, 6, 2.5, "2026-01-01", "2999-01-01")

    (deck,) = _decks(handler(make_event(), None))

    assert deck["card_count"] == 2
    assert deck["due_count"] == 1


def test_generating_and_failed_decks_report_status_and_error(
    dynamodb_tables, make_event
):
    generating = create_deck("user-1", "Working", STATUS_GENERATING)
    failed = create_deck("user-1", "Broken", STATUS_GENERATING)
    set_deck_status(failed, STATUS_FAILED, error="Too long")

    by_name = {d["deck_name"]: d for d in _decks(handler(make_event(), None))}

    assert by_name["Working"]["status"] == STATUS_GENERATING
    assert by_name["Broken"]["status"] == STATUS_FAILED
    assert by_name["Broken"]["error"] == "Too long"
    assert by_name["Working"]["card_count"] == 0
    assert generating  # created


def test_newest_deck_first(dynamodb_tables, make_event):
    create_deck("user-1", "First")
    create_deck("user-1", "Second")

    names = [d["deck_name"] for d in _decks(handler(make_event(), None))]

    assert names == ["Second", "First"]


def test_unauthenticated_is_401(dynamodb_tables, make_event):
    assert handler(make_event(user_id=None), None)["statusCode"] == 401


def test_bad_today_param_is_400(dynamodb_tables, make_event):
    assert handler(make_event(query={"today": "nope"}), None)["statusCode"] == 400


def test_null_query_parameters_are_handled(dynamodb_tables, make_event):
    # API Gateway sends null (not {}) when there is no query string.
    assert handler(make_event(query=None), None)["statusCode"] == 200
