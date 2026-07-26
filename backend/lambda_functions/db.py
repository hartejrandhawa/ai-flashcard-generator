"""
db.py
-----
DynamoDB table access for decks and cards.

Table: Decks
  PK: deck_id (string)
  Attributes: user_id, deck_name, created_at

Table: Cards
  PK: card_id (string)
  Attributes: deck_id, front, back, repetitions, interval_days,
              easiness_factor, last_reviewed, next_review
  GSI: deck_id-index (to query all cards in a deck)
"""

import os
import uuid
from datetime import date
from decimal import Decimal

import boto3

DECKS_TABLE = os.environ.get("DECKS_TABLE", "Decks")
CARDS_TABLE = os.environ.get("CARDS_TABLE", "Cards")


def get_dynamodb_resource():
    return boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "us-east-1"))


def create_deck(user_id: str, deck_name: str) -> str:
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(DECKS_TABLE)
    deck_id = str(uuid.uuid4())
    table.put_item(
        Item={
            "deck_id": deck_id,
            "user_id": user_id,
            "deck_name": deck_name,
            "created_at": date.today().isoformat(),
        }
    )
    return deck_id


def list_decks_for_user(user_id: str) -> list[dict]:
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(DECKS_TABLE)
    response = table.query(
        IndexName="user_id-index",
        KeyConditionExpression=boto3.dynamodb.conditions.Key("user_id").eq(user_id),
    )
    return response.get("Items", [])


def add_card(deck_id: str, front: str, back: str) -> str:
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(CARDS_TABLE)
    card_id = str(uuid.uuid4())
    table.put_item(
        Item={
            "card_id": card_id,
            "deck_id": deck_id,
            "front": front,
            "back": back,
            "repetitions": 0,
            "interval_days": 0,
            "easiness_factor": Decimal("2.5"),  # DynamoDB rejects native floats
            "last_reviewed": None,
            "next_review": date.today().isoformat(),
        }
    )
    return card_id


def get_cards_for_deck(deck_id: str) -> list[dict]:
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(CARDS_TABLE)
    response = table.query(
        IndexName="deck_id-index",
        KeyConditionExpression=boto3.dynamodb.conditions.Key("deck_id").eq(deck_id),
    )
    return response.get("Items", [])


def get_card(card_id: str) -> dict | None:
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(CARDS_TABLE)
    response = table.get_item(Key={"card_id": card_id})
    return response.get("Item")


def update_card_schedule(card_id: str, repetitions: int, interval_days: int,
                          easiness_factor: float, last_reviewed: str, next_review: str):
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(CARDS_TABLE)
    table.update_item(
        Key={"card_id": card_id},
        UpdateExpression=(
            "SET repetitions = :r, interval_days = :i, easiness_factor = :e, "
            "last_reviewed = :l, next_review = :n"
        ),
        ExpressionAttributeValues={
            ":r": repetitions,
            ":i": interval_days,
            ":e": Decimal(str(easiness_factor)),  # DynamoDB rejects native floats
            ":l": last_reviewed,
            ":n": next_review,
        },
    )
