import json

from db import add_card, create_deck, update_card_schedule
from get_due_cards import handler


def test_returns_only_due_cards(dynamodb_tables, make_event):
    deck_id = create_deck("user-1", "Deck")
    due = add_card(deck_id, "Due Q", "Due A")
    future = add_card(deck_id, "Future Q", "Future A")
    update_card_schedule(future, 1, 6, 2.5, "2026-01-01", "2999-01-01")

    res = handler(make_event_for(make_event, deck_id), None)
    body = json.loads(res["body"])

    assert res["statusCode"] == 200
    assert body["total_due"] == 1
    assert body["due_cards"] == [{"card_id": due, "front": "Due Q", "back": "Due A"}]


def make_event_for(make_event, deck_id, user_id="user-1", query=None):
    return make_event(user_id=user_id, path={"deck_id": deck_id}, query=query)


def test_client_local_date_decides_what_is_due(dynamodb_tables, make_event):
    from datetime import timedelta

    from common import utc_today

    deck_id = create_deck("user-1", "Deck")
    card_id = add_card(deck_id, "Q", "A")
    tomorrow = utc_today() + timedelta(days=1)
    update_card_schedule(card_id, 1, 1, 2.5, "2026-01-01", tomorrow.isoformat())

    not_yet = handler(make_event_for(make_event, deck_id), None)
    ahead_of_utc = handler(
        make_event_for(make_event, deck_id, query={"today": tomorrow.isoformat()}), None
    )

    assert json.loads(not_yet["body"])["total_due"] == 0
    assert json.loads(ahead_of_utc["body"])["total_due"] == 1


def test_other_users_deck_is_404(dynamodb_tables, make_event):
    deck_id = create_deck("user-1", "Deck")
    add_card(deck_id, "Q", "A")

    res = handler(make_event_for(make_event, deck_id, user_id="intruder"), None)

    assert res["statusCode"] == 404
    assert "Q" not in res["body"]


def test_missing_deck_is_404(dynamodb_tables, make_event):
    assert handler(make_event_for(make_event, "nope"), None)["statusCode"] == 404


def test_missing_deck_id_is_400(dynamodb_tables, make_event):
    assert handler(make_event(path=None), None)["statusCode"] == 400


def test_unauthenticated_is_401(dynamodb_tables, make_event):
    deck_id = create_deck("user-1", "Deck")
    assert (
        handler(make_event_for(make_event, deck_id, user_id=None), None)["statusCode"]
        == 401
    )
