"""
get_due_cards.py
-----------------
Lambda handler: returns cards in a deck that are due for review today,
based on each card's next_review date (SM-2 scheduling).

Expected event (API Gateway proxy integration, query string param):
  GET /decks/{deck_id}/due
"""

import json
from datetime import date

from db import get_cards_for_deck
from sm2 import CardState, is_due


def _card_to_state(card: dict) -> CardState:
    return CardState(
        repetitions=int(card.get("repetitions", 0)),
        interval_days=int(card.get("interval_days", 0)),
        easiness_factor=float(card.get("easiness_factor", 2.5)),
        next_review=date.fromisoformat(card["next_review"]) if card.get("next_review") else None,
    )


def handler(event, context):
    try:
        deck_id = (event.get("pathParameters") or {}).get("deck_id")
        if not deck_id:
            return _response(400, {"error": "deck_id is required"})

        cards = get_cards_for_deck(deck_id)
        today = date.today()

        due_cards = [
            {"card_id": c["card_id"], "front": c["front"], "back": c["back"]}
            for c in cards
            if is_due(_card_to_state(c), today)
        ]

        return _response(200, {"deck_id": deck_id, "due_cards": due_cards, "total_due": len(due_cards)})

    except Exception as e:
        return _response(500, {"error": str(e)})


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body),
    }
