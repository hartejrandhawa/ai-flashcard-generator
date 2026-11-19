"""
db.py
-----
DynamoDB access for decks and cards.

Table: Decks
  PK: deck_id (string)
  Attributes: user_id, deck_name, created_at, status, card_count, error
  GSI: user_id-index (list a user's decks)
  Also holds per-user daily generation counters under deck_id
  "quota#<user_id>#<date>". They have no user_id attribute, so they never
  appear in the GSI, and a TTL attribute (expires_at) removes them.

Table: Cards
  PK: card_id (string)
  Attributes: deck_id, front, back, repetitions, interval_days,
              easiness_factor, last_reviewed, next_review
  GSI: deck_id-index (query all cards in a deck)
"""

import functools
import os
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

DECKS_TABLE = os.environ.get("DECKS_TABLE", "Decks")
CARDS_TABLE = os.environ.get("CARDS_TABLE", "Cards")

# New cards are due immediately. A fixed past date (rather than "today in UTC")
# means a card is due for every user regardless of their timezone.
NEW_CARD_DUE = "1970-01-01"

STATUS_GENERATING = "generating"
STATUS_READY = "ready"
STATUS_FAILED = "failed"


class ConflictError(Exception):
    """A conditional write lost a race (e.g. the same card reviewed twice at once)."""


@functools.lru_cache(maxsize=1)
def get_dynamodb_resource():
    # Cached: building a boto3 resource is slow and was done on every call before.
    return boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "us-east-1"))


def _table(name: str):
    return get_dynamodb_resource().Table(name)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _query_all(table, **kwargs) -> list[dict]:
    """Run a query and follow LastEvaluatedKey so no page of results is dropped."""
    items = []
    while True:
        result = table.query(**kwargs)
        items.extend(result.get("Items", []))
        last_key = result.get("LastEvaluatedKey")
        if not last_key:
            return items
        kwargs["ExclusiveStartKey"] = last_key


# ---------------------------------------------------------------- decks


def create_deck(user_id: str, deck_name: str, status: str = STATUS_READY) -> str:
    deck_id = str(uuid.uuid4())
    _table(DECKS_TABLE).put_item(
        Item={
            "deck_id": deck_id,
            "user_id": user_id,
            "deck_name": deck_name,
            "created_at": _now(),
            "status": status,
            "card_count": 0,
        }
    )
    return deck_id


def get_deck(deck_id: str) -> dict | None:
    return _table(DECKS_TABLE).get_item(Key={"deck_id": deck_id}).get("Item")


def get_owned_deck(deck_id: str, user_id: str) -> dict | None:
    """The deck, only if it belongs to user_id. Callers answer 404 either way."""
    deck = get_deck(deck_id)
    if deck and deck.get("user_id") == user_id:
        return deck
    return None


def list_decks_for_user(user_id: str) -> list[dict]:
    return _query_all(
        _table(DECKS_TABLE),
        IndexName="user_id-index",
        KeyConditionExpression=Key("user_id").eq(user_id),
    )


def rename_deck(deck_id: str, deck_name: str) -> None:
    _table(DECKS_TABLE).update_item(
        Key={"deck_id": deck_id},
        UpdateExpression="SET deck_name = :n",
        ExpressionAttributeValues={":n": deck_name},
    )


def set_deck_status(deck_id: str, status: str, card_count: int | None = None, error: str | None = None) -> bool:
    """
    Update a deck's status. Returns False if the deck no longer exists (the
    user deleted it). Without the condition, update_item would quietly create
    a new, ownerless deck item.
    """
    names = {"#s": "status"}
    values: dict = {":s": status}
    sets = ["#s = :s"]
    if card_count is not None:
        sets.append("card_count = :c")
        values[":c"] = card_count
    if error is not None:
        sets.append("#e = :e")
        names["#e"] = "error"
        values[":e"] = error
    try:
        _table(DECKS_TABLE).update_item(
            Key={"deck_id": deck_id},
            UpdateExpression="SET " + ", ".join(sets),
            ConditionExpression="attribute_exists(deck_id)",
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
        )
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False
        raise


def claim_generation(deck_id: str) -> bool:
    """
    Atomically mark a "generating" deck as being worked on. Only the first
    caller gets True, so a duplicated async invoke can't run (and bill) the
    model call twice. A read-then-check would let two copies both pass.
    """
    try:
        _table(DECKS_TABLE).update_item(
            Key={"deck_id": deck_id},
            UpdateExpression="SET generation_started_at = :now",
            ConditionExpression="#s = :generating AND attribute_not_exists(generation_started_at)",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":now": _now(), ":generating": STATUS_GENERATING},
        )
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False
        raise


# The worker's Lambda timeout is 200 s, so a deck still "generating" after this
# long has a worker that died (timeout, crash) and will never finish.
GENERATION_STALE_AFTER = timedelta(minutes=10)
STALE_GENERATION_ERROR = "Generation took too long and was stopped. Please try again."


def deck_status(deck: dict) -> tuple[str, str | None]:
    """The (status, error) to show the user, treating abandoned generations as failed."""
    status = deck.get("status", STATUS_READY)
    if status == STATUS_GENERATING:
        try:
            started = datetime.fromisoformat(deck.get("created_at", ""))
        except ValueError:
            started = None
        if started and datetime.now(UTC) - started > GENERATION_STALE_AFTER:
            return STATUS_FAILED, STALE_GENERATION_ERROR
    return status, deck.get("error")


def delete_cards_for_deck(deck_id: str) -> None:
    with _table(CARDS_TABLE).batch_writer() as batch:
        for card in get_cards_for_deck(deck_id):
            batch.delete_item(Key={"card_id": card["card_id"]})


def delete_deck(deck_id: str) -> None:
    delete_cards_for_deck(deck_id)
    _table(DECKS_TABLE).delete_item(Key={"deck_id": deck_id})


def consume_generation_quota(user_id: str, limit: int, today: str) -> bool:
    """
    Count one generation against the user's daily limit. Returns False (and
    counts nothing) when the limit is already reached. The check and the
    increment are one conditional write, so concurrent requests can't overshoot.
    """
    expires_at = int((datetime.now(UTC) + timedelta(days=2)).timestamp())
    try:
        _table(DECKS_TABLE).update_item(
            Key={"deck_id": f"quota#{user_id}#{today}"},
            UpdateExpression="ADD #c :one SET expires_at = :exp",
            ConditionExpression="attribute_not_exists(#c) OR #c < :limit",
            ExpressionAttributeNames={"#c": "count"},
            ExpressionAttributeValues={":one": 1, ":limit": limit, ":exp": expires_at},
        )
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False
        raise


# ---------------------------------------------------------------- cards


def _new_card_item(deck_id: str, front: str, back: str) -> dict:
    return {
        "card_id": str(uuid.uuid4()),
        "deck_id": deck_id,
        "front": front,
        "back": back,
        "repetitions": 0,
        "interval_days": 0,
        "easiness_factor": Decimal("2.5"),  # DynamoDB rejects native floats
        "last_reviewed": None,
        "next_review": NEW_CARD_DUE,
    }


def add_card(deck_id: str, front: str, back: str) -> str:
    item = _new_card_item(deck_id, front, back)
    _table(CARDS_TABLE).put_item(Item=item)
    return item["card_id"]


def add_cards(deck_id: str, cards: list[dict]) -> int:
    """Write many cards in batches of 25 instead of one round trip per card."""
    with _table(CARDS_TABLE).batch_writer() as batch:
        for card in cards:
            batch.put_item(Item=_new_card_item(deck_id, card["front"], card["back"]))
    return len(cards)


def get_cards_for_deck(deck_id: str) -> list[dict]:
    return _query_all(
        _table(CARDS_TABLE),
        IndexName="deck_id-index",
        KeyConditionExpression=Key("deck_id").eq(deck_id),
    )


def get_card(card_id: str) -> dict | None:
    return _table(CARDS_TABLE).get_item(Key={"card_id": card_id}).get("Item")


def get_owned_card(card_id: str, user_id: str) -> dict | None:
    """The card, only if its deck belongs to user_id (card -> deck -> owner)."""
    card = get_card(card_id)
    if card and get_owned_deck(card["deck_id"], user_id):
        return card
    return None


def update_card_text(card_id: str, front: str, back: str) -> None:
    _table(CARDS_TABLE).update_item(
        Key={"card_id": card_id},
        # "back" is a DynamoDB reserved word, so attribute names go through placeholders.
        UpdateExpression="SET #front = :f, #back = :b",
        ExpressionAttributeNames={"#front": "front", "#back": "back"},
        ExpressionAttributeValues={":f": front, ":b": back},
    )


def delete_card(card_id: str) -> None:
    _table(CARDS_TABLE).delete_item(Key={"card_id": card_id})


def update_card_schedule(
    card_id: str,
    repetitions: int,
    interval_days: int,
    easiness_factor: float,
    last_reviewed: str,
    next_review: str,
    expected_repetitions: int | None = None,
    expected_next_review: str | None = None,
):
    """
    Save a card's new schedule. When the expected_* values are given, the write
    only succeeds if the card is still in that state, so two simultaneous
    reviews can't both apply SM-2 to the same starting point (raises ConflictError).
    """
    kwargs = {}
    if expected_repetitions is not None and expected_next_review is not None:
        kwargs["ConditionExpression"] = "repetitions = :er AND next_review = :en"
        extra = {":er": expected_repetitions, ":en": expected_next_review}
    else:
        extra = {}
    try:
        _table(CARDS_TABLE).update_item(
            Key={"card_id": card_id},
            UpdateExpression=(
                "SET repetitions = :r, interval_days = :i, easiness_factor = :e, last_reviewed = :l, next_review = :n"
            ),
            ExpressionAttributeValues={
                ":r": repetitions,
                ":i": interval_days,
                ":e": Decimal(str(easiness_factor)),  # DynamoDB rejects native floats
                ":l": last_reviewed,
                ":n": next_review,
                **extra,
            },
            **kwargs,
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise ConflictError("Card was modified concurrently") from None
        raise
