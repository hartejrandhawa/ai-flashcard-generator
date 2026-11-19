import json
from datetime import timedelta

import pytest

from common import (
    ApiError,
    api_handler,
    get_user_id,
    parse_body,
    parse_today,
    response,
    utc_today,
)


def test_response_has_cors_header(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGIN", "https://app.example.com")
    res = response(200, {"ok": True})
    assert res["headers"]["Access-Control-Allow-Origin"] == "https://app.example.com"
    assert json.loads(res["body"]) == {"ok": True}


def test_parse_body_rejects_invalid_json():
    with pytest.raises(ApiError) as exc:
        parse_body({"body": "{not json"})
    assert exc.value.status_code == 400


@pytest.mark.parametrize("raw", ["[1, 2]", '"text"', "42"])
def test_parse_body_rejects_non_objects(raw):
    with pytest.raises(ApiError) as exc:
        parse_body({"body": raw})
    assert exc.value.status_code == 400


def test_parse_body_missing_body_is_empty_object():
    assert parse_body({"body": None}) == {}


def test_get_user_id_reads_cognito_sub(make_event):
    assert get_user_id(make_event(user_id="abc")) == "abc"


def test_get_user_id_without_authorizer_is_401(make_event):
    with pytest.raises(ApiError) as exc:
        get_user_id(make_event(user_id=None))
    assert exc.value.status_code == 401


def test_parse_today_defaults_to_utc_today():
    assert parse_today(None) == utc_today()


def test_parse_today_accepts_adjacent_day():
    tomorrow = utc_today() + timedelta(days=1)
    assert parse_today(tomorrow.isoformat()) == tomorrow


@pytest.mark.parametrize("raw", ["not-a-date", "2026-13-45"])
def test_parse_today_rejects_garbage(raw):
    with pytest.raises(ApiError):
        parse_today(raw)


def test_parse_today_rejects_far_away_dates():
    with pytest.raises(ApiError):
        parse_today((utc_today() + timedelta(days=30)).isoformat())


def test_api_handler_hides_internal_errors():
    @api_handler
    def boom(event, context):
        raise RuntimeError("secret internal detail")

    res = boom({}, None)
    assert res["statusCode"] == 500
    assert "secret" not in res["body"]
