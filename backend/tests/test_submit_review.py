import json

from db import add_card, create_deck, get_card
from submit_review import handler


def test_submit_review_updates_schedule(dynamodb_tables):
    deck_id = create_deck("user-1", "Deck")
    card_id = add_card(deck_id, "Q", "A")

    res = handler({"body": json.dumps({"card_id": card_id, "quality": 4})}, None)
    body = json.loads(res["body"])

    assert res["statusCode"] == 200
    assert res["headers"]["Access-Control-Allow-Origin"] == "*"
    assert body["interval_days"] == 1

    card = get_card(card_id)
    assert card["repetitions"] == 1


def test_invalid_quality_returns_400(dynamodb_tables):
    res = handler({"body": json.dumps({"card_id": "x", "quality": 9})}, None)
    assert res["statusCode"] == 400


def test_missing_card_returns_404(dynamodb_tables):
    res = handler({"body": json.dumps({"card_id": "does-not-exist", "quality": 4})}, None)
    assert res["statusCode"] == 404
