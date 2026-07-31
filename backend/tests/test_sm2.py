from datetime import date

import pytest
from sm2 import CardState, is_due, review_card


def test_interval_growth_with_consistent_good_recall():
    state = CardState()
    today = date(2026, 1, 1)
    expected_intervals = [1, 6, 15, 38, 95, 238]

    intervals = []
    for _ in expected_intervals:
        state = review_card(state, quality=4, today=today)
        intervals.append(state.interval_days)
        today = state.next_review

    assert intervals == expected_intervals


def test_forgotten_card_resets_to_one_day():
    state = CardState(repetitions=5, interval_days=95, easiness_factor=2.7)
    result = review_card(state, quality=1, today=date(2026, 1, 1))

    assert result.repetitions == 0
    assert result.interval_days == 1
    assert result.next_review == date(2026, 1, 2)


def test_easiness_factor_floors_at_1_3():
    state = CardState(easiness_factor=1.3)
    result = review_card(state, quality=0, today=date(2026, 1, 1))

    assert result.easiness_factor == 1.3


@pytest.mark.parametrize("quality", [-1, 6])
def test_invalid_quality_raises(quality):
    with pytest.raises(ValueError):
        review_card(CardState(), quality)


def test_is_due():
    assert is_due(CardState(next_review=None))
    assert is_due(CardState(next_review=date(2026, 1, 1)), today=date(2026, 1, 2))
    assert not is_due(CardState(next_review=date(2026, 1, 5)), today=date(2026, 1, 2))
