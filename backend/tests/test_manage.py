"""Tests for the deck/card management endpoints and the cards listing."""

import json

import pytest

import get_deck_cards
import manage_card
import manage_deck
from db import add_card, add_cards, create_deck, get_card, get_cards_for_deck, get_deck


@pytest.fixture
def deck_id(dynamodb_tables):
    return create_deck("user-1", "Biology")


# ---- GET /decks/{id}/cards


def test_lists_all_cards_in_a_deck(deck_id, make_event):
    add_cards(
        deck_id,
        [{"front": "b question", "back": "x"}, {"front": "A question", "back": "y"}],
    )

    res = get_deck_cards.handler(make_event(path={"deck_id": deck_id}), None)
    body = json.loads(res["body"])

    assert res["statusCode"] == 200
    assert body["deck"]["deck_name"] == "Biology"
    assert [c["front"] for c in body["cards"]] == ["A question", "b question"]


def test_cards_of_other_users_deck_is_404(deck_id, make_event):
    add_card(deck_id, "Q", "A")
    res = get_deck_cards.handler(
        make_event(user_id="intruder", path={"deck_id": deck_id}), None
    )
    assert res["statusCode"] == 404


# ---- PATCH / DELETE /decks/{id}


def test_rename_deck(deck_id, make_event):
    event = make_event(
        path={"deck_id": deck_id}, body={"deck_name": "  Chem  "}, method="PATCH"
    )
    res = manage_deck.handler(event, None)

    assert res["statusCode"] == 200
    assert get_deck(deck_id)["deck_name"] == "Chem"


@pytest.mark.parametrize("name", ["", "   ", None, 7, "x" * 101])
def test_rename_deck_validates_name(deck_id, make_event, name):
    event = make_event(
        path={"deck_id": deck_id}, body={"deck_name": name}, method="PATCH"
    )
    assert manage_deck.handler(event, None)["statusCode"] == 400
    assert get_deck(deck_id)["deck_name"] == "Biology"


def test_delete_deck_removes_cards_too(deck_id, make_event):
    add_cards(deck_id, [{"front": "Q", "back": "A"}])

    res = manage_deck.handler(
        make_event(path={"deck_id": deck_id}, method="DELETE"), None
    )

    assert res["statusCode"] == 200
    assert get_deck(deck_id) is None
    assert get_cards_for_deck(deck_id) == []


@pytest.mark.parametrize("method", ["PATCH", "DELETE"])
def test_cannot_modify_someone_elses_deck(deck_id, make_event, method):
    event = make_event(
        user_id="intruder",
        path={"deck_id": deck_id},
        body={"deck_name": "pwned"},
        method=method,
    )

    assert manage_deck.handler(event, None)["statusCode"] == 404
    assert get_deck(deck_id)["deck_name"] == "Biology"


def test_unsupported_method_is_405(deck_id, make_event):
    event = make_event(path={"deck_id": deck_id}, method="PUT")
    assert manage_deck.handler(event, None)["statusCode"] == 405


# ---- PATCH / DELETE /cards/{id}


def test_edit_card(deck_id, make_event):
    card_id = add_card(deck_id, "old Q", "old A")
    event = make_event(
        path={"card_id": card_id},
        body={"front": " new Q ", "back": "new A"},
        method="PATCH",
    )

    res = manage_card.handler(event, None)

    assert res["statusCode"] == 200
    assert (get_card(card_id)["front"], get_card(card_id)["back"]) == ("new Q", "new A")


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"front": "Q"},
        {"front": "", "back": "A"},
        {"front": "Q", "back": "  "},
        {"front": 1, "back": "A"},
        {"front": "q" * 501, "back": "A"},
        {"front": "Q", "back": "a" * 1501},
    ],
)
def test_edit_card_validates_fields(deck_id, make_event, body):
    card_id = add_card(deck_id, "old Q", "old A")
    res = manage_card.handler(
        make_event(path={"card_id": card_id}, body=body, method="PATCH"), None
    )

    assert res["statusCode"] == 400
    assert get_card(card_id)["front"] == "old Q"


def test_delete_card(deck_id, make_event):
    card_id = add_card(deck_id, "Q", "A")
    res = manage_card.handler(
        make_event(path={"card_id": card_id}, method="DELETE"), None
    )

    assert res["statusCode"] == 200
    assert get_card(card_id) is None


@pytest.mark.parametrize("method", ["PATCH", "DELETE"])
def test_cannot_modify_someone_elses_card(deck_id, make_event, method):
    card_id = add_card(deck_id, "Q", "A")
    event = make_event(
        user_id="intruder",
        path={"card_id": card_id},
        body={"front": "x", "back": "y"},
        method=method,
    )

    assert manage_card.handler(event, None)["statusCode"] == 404
    assert get_card(card_id)["front"] == "Q"
