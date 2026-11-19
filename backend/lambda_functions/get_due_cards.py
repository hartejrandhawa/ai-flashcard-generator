"""
get_due_cards.py  (GET /decks/{deck_id}/due?today=YYYY-MM-DD)
-------------------------------------------------------------
Returns the cards in one of the user's decks that are due for review,
based on each card's SM-2 next_review date.
"""

from common import (
    ApiError,
    api_handler,
    get_user_id,
    parse_today,
    path_param,
    query_param,
    response,
)
from db import get_cards_for_deck, get_owned_deck
from sm2 import is_due, state_from_item


@api_handler
def handler(event, context):
    user_id = get_user_id(event)
    deck_id = path_param(event, "deck_id")
    today = parse_today(query_param(event, "today"))

    # 404 (not 403) for other people's decks, so deck ids can't be probed.
    if not get_owned_deck(deck_id, user_id):
        raise ApiError(404, "Deck not found")

    due = [c for c in get_cards_for_deck(deck_id) if is_due(state_from_item(c), today)]
    due.sort(key=lambda c: c.get("next_review") or "")

    return response(
        200,
        {
            "deck_id": deck_id,
            "due_cards": [
                {"card_id": c["card_id"], "front": c["front"], "back": c["back"]}
                for c in due
            ],
            "total_due": len(due),
        },
    )
