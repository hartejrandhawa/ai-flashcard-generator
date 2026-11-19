"""
list_decks.py  (GET /decks?today=YYYY-MM-DD)
--------------------------------------------
Lists the signed-in user's decks, newest first, with the card and due counts
the home screen needs and the generation status the frontend polls.
"""

from common import api_handler, get_user_id, parse_today, query_param, response
from db import STATUS_READY, get_cards_for_deck, list_decks_for_user
from sm2 import is_due, state_from_item


@api_handler
def handler(event, context):
    user_id = get_user_id(event)
    today = parse_today(query_param(event, "today"))

    decks = []
    for deck in sorted(
        list_decks_for_user(user_id),
        key=lambda d: d.get("created_at", ""),
        reverse=True,
    ):
        status = deck.get("status", STATUS_READY)
        card_count = due_count = 0
        if status == STATUS_READY:
            cards = get_cards_for_deck(deck["deck_id"])
            card_count = len(cards)
            due_count = sum(1 for c in cards if is_due(state_from_item(c), today))
        decks.append(
            {
                "deck_id": deck["deck_id"],
                "deck_name": deck["deck_name"],
                "created_at": deck.get("created_at"),
                "status": status,
                "error": deck.get("error"),
                "card_count": card_count,
                "due_count": due_count,
            }
        )

    return response(200, {"decks": decks})
