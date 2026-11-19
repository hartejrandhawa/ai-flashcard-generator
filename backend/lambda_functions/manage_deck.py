"""
manage_deck.py  (PATCH /decks/{deck_id}, DELETE /decks/{deck_id})
-----------------------------------------------------------------
Rename or delete one of the user's decks (deleting also removes its cards).
"""

from common import ApiError, api_handler, get_user_id, parse_body, path_param, response
from db import delete_deck, get_owned_deck, rename_deck

MAX_DECK_NAME_CHARS = 100


@api_handler
def handler(event, context):
    user_id = get_user_id(event)
    deck_id = path_param(event, "deck_id")
    method = event.get("httpMethod")

    if not get_owned_deck(deck_id, user_id):
        raise ApiError(404, "Deck not found")

    if method == "DELETE":
        delete_deck(deck_id)
        return response(200, {"deleted": deck_id})

    if method == "PATCH":
        name = parse_body(event).get("deck_name")
        if not isinstance(name, str) or not name.strip():
            raise ApiError(400, "deck_name is required")
        if len(name.strip()) > MAX_DECK_NAME_CHARS:
            raise ApiError(
                400, f"deck_name must be at most {MAX_DECK_NAME_CHARS} characters"
            )
        rename_deck(deck_id, name.strip())
        return response(200, {"deck_id": deck_id, "deck_name": name.strip()})

    raise ApiError(405, "Method not allowed")
