import json
from datetime import date, timedelta

from db import add_card, create_deck, update_card_schedule
from get_due_cards import handler


def test_returns_only_due_cards(dynamodb_tables):
    deck_id = create_deck("user-1", "Deck")
    due_card = add_card(deck_id, "Due now", "A")
    future_card = add_card(deck_id, "Not due yet", "B")

    update_card_schedule(
        card_id=future_card,
        repetitions=1,
        interval_days=10,
        easiness_factor=2.5,
        last_reviewed=date.today().isoformat(),
        next_review=(date.today() + timedelta(days=10)).isoformat(),
    )

    res = handler({"pathParameters": {"deck_id": deck_id}}, None)
    body = json.loads(res["body"])

    assert res["statusCode"] == 200
    assert res["headers"]["Access-Control-Allow-Origin"] == "*"
    assert body["total_due"] == 1
    assert body["due_cards"][0]["card_id"] == due_card


def test_missing_deck_id_returns_400(dynamodb_tables):
    res = handler({"pathParameters": {}}, None)
    assert res["statusCode"] == 400


def test_null_path_parameters_returns_400_not_500(dynamodb_tables):
    res = handler({"pathParameters": None}, None)
    assert res["statusCode"] == 400
