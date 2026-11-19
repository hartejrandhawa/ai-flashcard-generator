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
    STATUS_READY,
    add_cards,
    claim_generation,
    delete_cards_for_deck,
    set_deck_status,
)
from llm import GenerationError, generate_cards

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

GENERIC_FAILURE = "Something went wrong while creating the flashcards. Please try again."


def handler(event, context):
    deck_id = event["deck_id"]

    # Idempotency: async invokes can be delivered more than once, and each
    # attempt costs a model call. The claim is a single conditional write, so
    # only one delivery ever gets past it.
    if not claim_generation(deck_id):
        logger.info("Skipping deck %s (missing, finished, or already claimed)", deck_id)
        return

    try:
        cards = generate_cards(event["notes_text"])
        count = add_cards(deck_id, cards)
    except GenerationError as e:
        set_deck_status(deck_id, STATUS_FAILED, error=e.user_message)
        return
    except Exception:
        logger.exception("Generation failed for deck %s", deck_id)
        set_deck_status(deck_id, STATUS_FAILED, error=GENERIC_FAILURE)
        return

    if not set_deck_status(deck_id, STATUS_READY, card_count=count):
        # The user deleted the deck while the model was running. Its cards
        # were written after the delete, so remove them rather than orphan them.
        logger.info("Deck %s was deleted during generation; removing its cards", deck_id)
        delete_cards_for_deck(deck_id)
