"""
generate_flashcards.py
-----------------------
Lambda handler: takes note text (already extracted from an uploaded PDF/
text file and stored in S3), asks Claude to generate flashcard Q&A pairs,
and stores them as a new deck in DynamoDB.

Expected event body (API Gateway proxy integration):
{
  "user_id": "...",
  "deck_name": "...",
  "notes_text": "..."
}
"""

import json
import os

from db import create_deck, add_card

CLAUDE_MODEL = "claude-sonnet-5"
MAX_CARDS = 30


def generate_flashcards_with_claude(notes_text: str) -> list[dict]:
    import anthropic

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    prompt = f"""Generate up to {MAX_CARDS} flashcards from the following study notes.
Each flashcard should test one discrete fact or concept — not vague or
overly broad questions. Return ONLY a JSON array, no other text, in this
exact format:

[{{"front": "question or prompt", "back": "answer"}}]

Notes:
{notes_text}
"""

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )

    raw_text = response.content[0].text.strip()
    # Strip markdown code fences if Claude wrapped the JSON in one
    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]

    cards = json.loads(raw_text)
    return cards


def handler(event, context):
    try:
        body = json.loads(event.get("body") or "{}")
        user_id = body.get("user_id")
        deck_name = body.get("deck_name")
        notes_text = body.get("notes_text")

        if not all([user_id, deck_name, notes_text]):
            return _response(400, {"error": "user_id, deck_name, and notes_text are required"})

        cards = generate_flashcards_with_claude(notes_text)
        if not cards:
            return _response(422, {"error": "No flashcards could be generated from these notes"})

        deck_id = create_deck(user_id, deck_name)
        card_ids = [add_card(deck_id, c["front"], c["back"]) for c in cards]

        return _response(200, {
            "deck_id": deck_id,
            "deck_name": deck_name,
            "card_count": len(card_ids),
        })

    except json.JSONDecodeError:
        return _response(502, {"error": "Claude did not return valid JSON"})
    except Exception as e:
        return _response(500, {"error": str(e)})


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }
