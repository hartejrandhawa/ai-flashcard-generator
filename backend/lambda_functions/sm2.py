"""
sm2.py
------
Implementation of the SM-2 spaced-repetition algorithm (the same core
algorithm behind Anki and SuperMemo). Given a card's current scheduling
state and how well the user recalled it (0-5), computes the next review
date, updated interval, and updated easiness factor.

Quality scale (standard SM-2):
  0 - complete blackout
  1 - incorrect, but felt familiar
  2 - incorrect, but easy to recall once shown
  3 - correct, with serious difficulty
  4 - correct, with some hesitation
  5 - correct, perfect recall
"""

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass
class CardState:
    repetitions: int = 0
    interval_days: int = 0
    easiness_factor: float = 2.5
    last_reviewed: date | None = None
    next_review: date | None = None


def review_card(state: CardState, quality: int, today: date | None = None) -> CardState:
    if not (0 <= quality <= 5):
        raise ValueError("quality must be between 0 and 5")

    today = today or date.today()

    ef = state.easiness_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    ef = max(ef, 1.3)  # SM-2 floors easiness factor at 1.3

    if quality < 3:
        # Forgotten — reset repetitions, review again tomorrow
        repetitions = 0
        interval = 1
    else:
        repetitions = state.repetitions + 1
        if repetitions == 1:
            interval = 1
        elif repetitions == 2:
            interval = 6
        else:
            interval = round(state.interval_days * ef)

    return CardState(
        repetitions=repetitions,
        interval_days=interval,
        easiness_factor=ef,
        last_reviewed=today,
        next_review=today + timedelta(days=interval),
    )


def is_due(state: CardState, today: date | None = None) -> bool:
    today = today or date.today()
    return state.next_review is None or state.next_review <= today
