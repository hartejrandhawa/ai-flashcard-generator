"""
manage_card.py  (PATCH /cards/{card_id}, DELETE /cards/{card_id})
-----------------------------------------------------------------
Edit or delete a single card. Ownership is checked through the card's deck.
"""

from common import (
    MAX_BACK_CHARS,
    MAX_FRONT_CHARS,
    ApiError,
    api_handler,
    get_user_id,
    parse_body,
    path_param,
    response,
)
from db import delete_card, get_owned_card, update_card_text


@api_handler
def handler(event, context):
    user_id = get_user_id(event)
    card_id = path_param(event, "card_id")
    method = event.get("httpMethod")

    if not get_owned_card(card_id, user_id):
        raise ApiError(404, "Card not found")

    if method == "DELETE":
        delete_card(card_id)
        return response(200, {"deleted": card_id})

    if method == "PATCH":
        body = parse_body(event)
        front, back = body.get("front"), body.get("back")
        if (
            not isinstance(front, str)
            or not isinstance(back, str)
            or not front.strip()
            or not back.strip()
        ):
            raise ApiError(400, "front and back are required")
        front, back = front.strip(), back.strip()
        if len(front) > MAX_FRONT_CHARS or len(back) > MAX_BACK_CHARS:
            raise ApiError(400, "front or back is too long")
        update_card_text(card_id, front, back)
        return response(200, {"card_id": card_id, "front": front, "back": back})

    raise ApiError(405, "Method not allowed")
