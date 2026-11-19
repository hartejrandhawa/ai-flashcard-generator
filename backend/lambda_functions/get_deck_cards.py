"""
get_deck_cards.py  (GET /decks/{deck_id}/cards)
-----------------------------------------------
Returns every card in one of the user's decks, plus the deck itself. Used by
the deck page (review/edit generated cards) and for CSV export.
"""

from common import ApiError, api_handler, get_user_id, path_param, response
from db import deck_status, get_cards_for_deck, get_owned_deck


@api_handler
def handler(event, context):
    user_id = get_user_id(event)
    deck_id = path_param(event, "deck_id")

    deck = get_owned_deck(deck_id, user_id)
    if not deck:
        raise ApiError(404, "Deck not found")

    cards = sorted(get_cards_for_deck(deck_id), key=lambda c: c["front"].lower())
    status, error = deck_status(deck)
    return response(
        200,
        {
            "deck": {
                "deck_id": deck_id,
                "deck_name": deck["deck_name"],
                "status": status,
                "error": error,
            },
            "cards": [
                {
                    "card_id": c["card_id"],
                    "front": c["front"],
                    "back": c["back"],
                    "next_review": c.get("next_review"),
                }
                for c in cards
            ],
        },
    )
