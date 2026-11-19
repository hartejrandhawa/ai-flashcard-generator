import json
from datetime import timedelta
from unittest.mock import patch

import pytest

import submit_review
from common import utc_today
from db import ConflictError, add_card, create_deck, get_card
from submit_review import handler


def _review(make_event, card_id, quality, user_id="user-1", **extra):
    return handler(
        make_event(
            user_id=user_id,
            body={"card_id": card_id, "quality": quality, **extra},
            method="POST",
        ),
        None,
    )


@pytest.fixture
def card_id(dynamodb_tables):
    return add_card(create_deck("user-1", "Deck"), "Q", "A")


def test_good_review_schedules_next_day_for_new_card(card_id, make_event):
    res = _review(make_event, card_id, 4)
    body = json.loads(res["body"])

    assert res["statusCode"] == 200
    assert body["interval_days"] == 1
    assert body["next_review"] == (utc_today() + timedelta(days=1)).isoformat()
    assert get_card(card_id)["repetitions"] == 1


def test_failed_review_resets_progress(card_id, make_event):
    _review(make_event, card_id, 5)
    _review(make_event, card_id, 5)
    res = _review(make_event, card_id, 1)

    assert json.loads(res["body"])["interval_days"] == 1
    assert get_card(card_id)["repetitions"] == 0


def test_schedule_follows_client_local_date(card_id, make_event):
    local_today = utc_today() + timedelta(days=1)
    res = _review(make_event, card_id, 4, today=local_today.isoformat())

    assert (
        json.loads(res["body"])["next_review"]
        == (local_today + timedelta(days=1)).isoformat()
    )


@pytest.mark.parametrize("quality", [-1, 6, 3.5, "4", True, False, None])
def test_invalid_quality_returns_400(card_id, make_event, quality):
    assert _review(make_event, card_id, quality)["statusCode"] == 400


def test_missing_card_id_returns_400(dynamodb_tables, make_event):
    res = handler(make_event(body={"quality": 3}, method="POST"), None)
    assert res["statusCode"] == 400


def test_unknown_card_returns_404(dynamodb_tables, make_event):
    assert _review(make_event, "does-not-exist", 3)["statusCode"] == 404


def test_cannot_review_someone_elses_card(card_id, make_event):
    res = _review(make_event, card_id, 5, user_id="intruder")

    assert res["statusCode"] == 404
    assert get_card(card_id)["repetitions"] == 0  # untouched


def test_malformed_body_is_400_not_500(dynamodb_tables, make_event):
    res = handler(make_event(raw_body="{oops", method="POST"), None)
    assert res["statusCode"] == 400


def test_concurrent_review_conflict_returns_409(card_id, make_event):
    with patch.object(
        submit_review, "update_card_schedule", side_effect=ConflictError("race")
    ):
        res = _review(make_event, card_id, 4)
    assert res["statusCode"] == 409


def test_stale_double_submit_is_rejected_end_to_end(card_id, make_event):
    """Two requests that both read the original state: only the first may write."""
    from db import get_owned_card as real_get

    stale = real_get(card_id, "user-1")
    assert _review(make_event, card_id, 4)["statusCode"] == 200  # first review lands

    with patch.object(submit_review, "get_owned_card", return_value=stale):
        res = _review(make_event, card_id, 4)  # second request had read the old state

    assert res["statusCode"] == 409
    assert get_card(card_id)["repetitions"] == 1
