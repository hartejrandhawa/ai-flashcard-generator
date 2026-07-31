import json

from db import create_deck
from list_decks import handler


def test_returns_decks_for_user(dynamodb_tables):
    create_deck("user-1", "Deck A")
    create_deck("user-2", "Deck B")

    res = handler({"queryStringParameters": {"user_id": "user-1"}}, None)
    body = json.loads(res["body"])

    assert res["statusCode"] == 200
    assert res["headers"]["Access-Control-Allow-Origin"] == "*"
    assert len(body["decks"]) == 1
    assert body["decks"][0]["deck_name"] == "Deck A"


def test_missing_user_id_returns_400(dynamodb_tables):
    res = handler({"queryStringParameters": {}}, None)
    assert res["statusCode"] == 400


def test_null_query_string_parameters_returns_400_not_500(dynamodb_tables):
    # Real API Gateway proxy events set queryStringParameters to null
    # (not omit the key) when there's no query string.
    res = handler({"queryStringParameters": None}, None)
    assert res["statusCode"] == 400
