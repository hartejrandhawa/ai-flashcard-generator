"""
list_decks.py
--------------
Lambda handler: returns all decks belonging to a user.

Expected event (API Gateway proxy integration, query string param):
  GET /decks?user_id=...
"""

import json

from db import list_decks_for_user


def handler(event, context):
    try:
        user_id = (event.get("queryStringParameters") or {}).get("user_id")
        if not user_id:
            return _response(400, {"error": "user_id is required"})

        decks = list_decks_for_user(user_id)
        return _response(200, {"decks": decks})

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
