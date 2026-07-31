import json
import os
from unittest.mock import patch

from generate_flashcards import generate_flashcards_with_claude, handler


def test_creates_deck_from_claude_response(dynamodb_tables):
    fake_cards = [{"front": "What is mitosis?", "back": "Cell division"}]
    with patch("generate_flashcards.generate_flashcards_with_claude", return_value=fake_cards):
        res = handler(
            {
                "body": json.dumps(
                    {"user_id": "user-1", "deck_name": "Bio", "notes_text": "Mitosis is..."}
                )
            },
            None,
        )

    body = json.loads(res["body"])
    assert res["statusCode"] == 200
    assert res["headers"]["Access-Control-Allow-Origin"] == "*"
    assert body["card_count"] == 1


def test_missing_fields_returns_400(dynamodb_tables):
    res = handler({"body": json.dumps({"user_id": "u"})}, None)
    assert res["statusCode"] == 400


def test_empty_cards_returns_422(dynamodb_tables):
    with patch("generate_flashcards.generate_flashcards_with_claude", return_value=[]):
        res = handler(
            {"body": json.dumps({"user_id": "u", "deck_name": "d", "notes_text": "n"})},
            None,
        )
    assert res["statusCode"] == 422


def test_invalid_json_from_claude_returns_502(dynamodb_tables):
    with patch(
        "generate_flashcards.generate_flashcards_with_claude",
        side_effect=json.JSONDecodeError("msg", "doc", 0),
    ):
        res = handler(
            {"body": json.dumps({"user_id": "u", "deck_name": "d", "notes_text": "n"})},
            None,
        )
    assert res["statusCode"] == 502


class _FakeTextBlock:
    def __init__(self, text):
        self.text = text


class _FakeResponse:
    def __init__(self, text):
        self.content = [_FakeTextBlock(text)]


def test_strips_markdown_code_fence_from_claude_response():
    fake_client = type(
        "FakeClient",
        (),
        {
            "messages": type(
                "FakeMessages",
                (),
                {
                    "create": staticmethod(
                        lambda **kw: _FakeResponse('```json\n[{"front": "Q", "back": "A"}]\n```')
                    )
                },
            )()
        },
    )()

    os.environ["ANTHROPIC_API_KEY"] = "test-key"
    with patch("anthropic.Anthropic", return_value=fake_client):
        cards = generate_flashcards_with_claude("some notes")

    assert cards == [{"front": "Q", "back": "A"}]
