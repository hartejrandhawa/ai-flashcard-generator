"""
submit_review.py
------------------
Lambda handler: takes a card_id and a recall quality score (0-5), runs the
SM-2 algorithm to compute the next review date, and updates the card's
scheduling state in DynamoDB.

Expected event body (API Gateway proxy integration):
{
  "card_id": "...",
  "quality": 4
}
"""

import json
from datetime import date

from db import get_card, update_card_schedule
from sm2 import CardState, review_card


def handler(event, context):
    try:
        body = json.loads(event.get("body") or "{}")
        card_id = body.get("card_id")
        quality = body.get("quality")

        if card_id is None or quality is None:
            return _response(400, {"error": "card_id and quality are required"})
        if not isinstance(quality, int) or not (0 <= quality <= 5):
            return _response(400, {"error": "quality must be an integer between 0 and 5"})

        card = get_card(card_id)
        if not card:
            return _response(404, {"error": "Card not found"})

        current_state = CardState(
            repetitions=int(card.get("repetitions", 0)),
            interval_days=int(card.get("interval_days", 0)),
            easiness_factor=float(card.get("easiness_factor", 2.5)),
        )

        new_state = review_card(current_state, quality)

        update_card_schedule(
            card_id=card_id,
            repetitions=new_state.repetitions,
            interval_days=new_state.interval_days,
            easiness_factor=new_state.easiness_factor,
            last_reviewed=new_state.last_reviewed.isoformat(),
            next_review=new_state.next_review.isoformat(),
        )

        return _response(200, {
            "card_id": card_id,
            "next_review": new_state.next_review.isoformat(),
            "interval_days": new_state.interval_days,
            "easiness_factor": round(new_state.easiness_factor, 2),
        })

    except Exception as e:
        return _response(500, {"error": str(e)})


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }
