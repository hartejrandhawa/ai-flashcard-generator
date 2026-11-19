import json
from unittest.mock import MagicMock, patch

import pytest

import generate_flashcards
from db import STATUS_GENERATING, list_decks_for_user
from generate_flashcards import handler


@pytest.fixture(autouse=True)
def worker_env(monkeypatch):
    monkeypatch.setenv("WORKER_FUNCTION_NAME", "worker-fn")
    monkeypatch.setenv("DAILY_GENERATION_LIMIT", "20")


@pytest.fixture
def lambda_client():
    client = MagicMock()
    with patch.object(generate_flashcards, "_lambda_client", return_value=client):
        yield client


def _valid(**overrides):
    return {"deck_name": "Bio", "notes_text": "Mitosis is cell division.", **overrides}


def test_starts_generation_and_returns_202(dynamodb_tables, lambda_client, make_event):
    res = handler(make_event(body=_valid(), method="POST"), None)

    body = json.loads(res["body"])
    assert res["statusCode"] == 202
    assert res["headers"]["Access-Control-Allow-Origin"] == "*"
    assert body["status"] == STATUS_GENERATING

    (deck,) = list_decks_for_user("user-1")
    assert deck["deck_id"] == body["deck_id"]
    assert deck["status"] == STATUS_GENERATING

    kwargs = lambda_client.invoke.call_args.kwargs
    assert kwargs["FunctionName"] == "worker-fn"
    assert kwargs["InvocationType"] == "Event"
    payload = json.loads(kwargs["Payload"])
    assert payload == {
        "deck_id": body["deck_id"],
        "notes_text": "Mitosis is cell division.",
    }


def test_worker_payload_is_compact_utf8(dynamodb_tables, lambda_client, make_event):
    # 50k CJK characters would be ~300 KB with \uXXXX escapes; raw UTF-8 is 150 KB.
    notes = "細胞分裂" * 12_500
    handler(make_event(body={"deck_name": "Bio", "notes_text": notes}, method="POST"), None)

    payload = lambda_client.invoke.call_args.kwargs["Payload"]
    assert len(payload) < 256 * 1024
    assert json.loads(payload)["notes_text"] == notes


def test_user_comes_from_token_not_body(dynamodb_tables, lambda_client, make_event):
    handler(
        make_event(user_id="real-user", body=_valid(user_id="attacker"), method="POST"),
        None,
    )

    assert len(list_decks_for_user("real-user")) == 1
    assert list_decks_for_user("attacker") == []


def test_unauthenticated_returns_401(dynamodb_tables, lambda_client, make_event):
    res = handler(make_event(user_id=None, body=_valid(), method="POST"), None)
    assert res["statusCode"] == 401
    lambda_client.invoke.assert_not_called()


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"deck_name": "x"},
        {"notes_text": "x"},
        {"deck_name": "   ", "notes_text": "x"},
        {"deck_name": "x", "notes_text": "   "},
        {"deck_name": 5, "notes_text": "x"},
        {"deck_name": "x", "notes_text": ["list"]},
        {"deck_name": "n" * 101, "notes_text": "x"},
        {"deck_name": "x", "notes_text": "n" * 50_001},
    ],
)
def test_invalid_input_returns_400(dynamodb_tables, lambda_client, make_event, body):
    res = handler(make_event(body=body, method="POST"), None)
    assert res["statusCode"] == 400
    lambda_client.invoke.assert_not_called()


@pytest.mark.parametrize("raw", ["{broken", "[1,2]"])
def test_malformed_body_is_a_400_not_a_model_error(dynamodb_tables, lambda_client, make_event, raw):
    res = handler(make_event(raw_body=raw, method="POST"), None)
    assert res["statusCode"] == 400
    assert "Claude" not in res["body"]


def test_daily_quota_returns_429(dynamodb_tables, lambda_client, make_event, monkeypatch):
    monkeypatch.setenv("DAILY_GENERATION_LIMIT", "2")
    codes = [handler(make_event(body=_valid(), method="POST"), None)["statusCode"] for _ in range(3)]
    assert codes == [202, 202, 429]
    assert len(list_decks_for_user("user-1")) == 2


def test_quota_is_per_user(dynamodb_tables, lambda_client, make_event, monkeypatch):
    monkeypatch.setenv("DAILY_GENERATION_LIMIT", "1")
    handler(make_event(user_id="a", body=_valid(), method="POST"), None)
    res = handler(make_event(user_id="b", body=_valid(), method="POST"), None)
    assert res["statusCode"] == 202


def test_worker_start_failure_cleans_up_the_deck(dynamodb_tables, lambda_client, make_event):
    lambda_client.invoke.side_effect = RuntimeError("throttled")
    res = handler(make_event(body=_valid(), method="POST"), None)

    assert res["statusCode"] == 502
    assert "throttled" not in res["body"]
    assert list_decks_for_user("user-1") == []
