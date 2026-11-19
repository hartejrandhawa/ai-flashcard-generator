"""
generate_worker.py  (invoked asynchronously by generate_flashcards.py)
----------------------------------------------------------------------
Does the slow part of deck creation: calls Claude, saves the cards, and
records the outcome on the deck ("ready" or "failed" with a user-safe
message) so the frontend can show what happened.

Event: {"deck_id": "...", "notes_text": "..."}
"""

import logging

from db import (
    STATUS_FAILED,
    STATUS_GENERATING,
    STATUS_READY,
    add_cards,
    get_deck,
    set_deck_status,
)
from llm import GenerationError, generate_cards

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

GENERIC_FAILURE = (
    "Something went wrong while creating the flashcards. Please try again."
)


def handler(event, context):
    deck_id = event["deck_id"]

    # Idempotency: async invokes can be delivered more than once, and each
    # attempt costs a model call. Only a deck still "generating" is worked on.
    deck = get_deck(deck_id)
    if not deck or deck.get("status") != STATUS_GENERATING:
        logger.info("Skipping deck %s (missing or not generating)", deck_id)
        return

    try:
        cards = generate_cards(event["notes_text"])
        count = add_cards(deck_id, cards)
        set_deck_status(deck_id, STATUS_READY, card_count=count)
    except GenerationError as e:
        set_deck_status(deck_id, STATUS_FAILED, error=e.user_message)
    except Exception:
        logger.exception("Generation failed for deck %s", deck_id)
        set_deck_status(deck_id, STATUS_FAILED, error=GENERIC_FAILURE)
