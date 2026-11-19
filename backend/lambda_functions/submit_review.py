"""
submit_review.py  (POST /reviews)
---------------------------------
Takes a card_id and a recall quality (0-5), runs SM-2 to compute the next
review date, and saves the card's new schedule.

Request body: {"card_id": "...", "quality": 4, "today": "YYYY-MM-DD"}   ("today" optional)
"""

from common import ApiError, api_handler, get_user_id, parse_body, parse_today, response
from db import NEW_CARD_DUE, ConflictError, get_owned_card, update_card_schedule
from sm2 import review_card, state_from_item


@api_handler
def handler(event, context):
    user_id = get_user_id(event)
    body = parse_body(event)
    card_id = body.get("card_id")
    quality = body.get("quality")

    if not isinstance(card_id, str) or not card_id or quality is None:
        raise ApiError(400, "card_id and quality are required")
    # bool is a subclass of int in Python, so True would otherwise pass as 1.
    if (
        isinstance(quality, bool)
        or not isinstance(quality, int)
        or not (0 <= quality <= 5)
    ):
        raise ApiError(400, "quality must be an integer between 0 and 5")
    today = parse_today(body.get("today"))

    card = get_owned_card(card_id, user_id)
    if not card:
        raise ApiError(404, "Card not found")

    current_state = state_from_item(card)
    new_state = review_card(current_state, quality, today)

    try:
        update_card_schedule(
            card_id=card_id,
            repetitions=new_state.repetitions,
            interval_days=new_state.interval_days,
            easiness_factor=new_state.easiness_factor,
            last_reviewed=today.isoformat(),
            next_review=new_state.next_review.isoformat(),
            # Only write if the card is still in the state we read, so two
            # simultaneous reviews can't both apply SM-2 to the same starting point.
            expected_repetitions=current_state.repetitions,
            expected_next_review=card.get("next_review") or NEW_CARD_DUE,
        )
    except ConflictError:
        raise ApiError(409, "This card was just reviewed. Please reload.") from None

    return response(
        200,
        {
            "card_id": card_id,
            "next_review": new_state.next_review.isoformat(),
            "interval_days": new_state.interval_days,
            "easiness_factor": round(new_state.easiness_factor, 2),
        },
    )
