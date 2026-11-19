"""
generate_flashcards.py  (POST /decks)
-------------------------------------
Starts flashcard generation and returns immediately (HTTP 202).

Generating cards means a slow LLM call, which can easily exceed API
Gateway's 29-second limit. So this handler only validates, creates the deck
with status "generating", and asynchronously invokes the worker
(generate_worker.py) that does the real work. The frontend polls
GET /decks until the status becomes "ready" or "failed".

Request body: {"deck_name": "...", "notes_text": "..."}
The user comes from the verified auth token, never from the body.
"""

import functools
import json
import logging
import os

import boto3

from common import ApiError, api_handler, get_user_id, parse_body, response, utc_today
from db import STATUS_GENERATING, consume_generation_quota, create_deck, delete_deck

logger = logging.getLogger(__name__)

MAX_DECK_NAME_CHARS = 100
# Async Lambda invocation payloads are capped at 256 KB. 50k characters is
# at most ~200 KB even if every character is 4 bytes, so it always fits.
MAX_NOTES_CHARS = 50_000


@functools.lru_cache(maxsize=1)
def _lambda_client():
    return boto3.client("lambda")


@api_handler
def handler(event, context):
    user_id = get_user_id(event)
    body = parse_body(event)

    deck_name = body.get("deck_name")
    notes_text = body.get("notes_text")
    if not isinstance(deck_name, str) or not deck_name.strip():
        raise ApiError(400, "deck_name is required")
    if len(deck_name.strip()) > MAX_DECK_NAME_CHARS:
        raise ApiError(
            400, f"deck_name must be at most {MAX_DECK_NAME_CHARS} characters"
        )
    if not isinstance(notes_text, str) or not notes_text.strip():
        raise ApiError(400, "notes_text is required")
    if len(notes_text) > MAX_NOTES_CHARS:
        raise ApiError(400, f"notes_text must be at most {MAX_NOTES_CHARS} characters")

    # Every generation is a paid model call, so cap how many one user can start.
    limit = int(os.environ.get("DAILY_GENERATION_LIMIT", "20"))
    if not consume_generation_quota(user_id, limit, utc_today().isoformat()):
        raise ApiError(429, "Daily generation limit reached. Try again tomorrow.")

    deck_id = create_deck(user_id, deck_name.strip(), STATUS_GENERATING)
    try:
        _lambda_client().invoke(
            FunctionName=os.environ["WORKER_FUNCTION_NAME"],
            InvocationType="Event",  # fire-and-forget
            Payload=json.dumps({"deck_id": deck_id, "notes_text": notes_text}).encode(),
        )
    except Exception:
        # Don't leave a deck stuck on "generating" that nothing will ever finish.
        logger.exception("Could not start generation worker")
        delete_deck(deck_id)
        raise ApiError(502, "Could not start generation. Please try again.")

    return response(
        202,
        {
            "deck_id": deck_id,
            "deck_name": deck_name.strip(),
            "status": STATUS_GENERATING,
        },
    )
