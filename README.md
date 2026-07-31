# AI Flashcard Generator

Upload your notes, get flashcards generated automatically, and review them
on a spaced-repetition schedule (the same SM-2 algorithm behind Anki) —
built to close a real gap: nothing else in the portfolio is actually
deployed and running on AWS, only claimed via an internship.

## What it does

1. Upload a PDF or paste notes directly
2. Claude generates flashcards (question/answer pairs) from the content
3. Review due cards in a quiz view; rate your recall (Again/Hard/Good/Easy)
4. The SM-2 algorithm schedules each card's next review based on how well
   you remembered it — cards you know well show up less often, cards you
   struggle with come back sooner

## What's been tested vs. what needs your own setup

This was built in a sandbox with no AWS access and no Anthropic API key,
so testing split into two categories:

**Fully tested (25 pytest tests, using `moto` to mock AWS locally):**
- SM-2 algorithm — verified interval growth (1 → 6 → 15 → 38 → 95 → 238
  days with consistent good recall), correct reset to 1 day on a
  forgotten card, and the easiness-factor floor at 1.3
- Deck/card creation, due-card queries, and review submission — full
  DynamoDB read/write flow tested end-to-end, including all four Lambda
  handlers with API-Gateway-shaped events
- Input validation (rejects invalid quality scores, missing fields)
- `generate_flashcards.py`'s handler logic and Claude-response parsing
  (markdown code-fence stripping), with the Anthropic client mocked
- Two real bugs caught and fixed during testing:
  - DynamoDB's boto3 API rejects native Python floats — the easiness
    factor field needed converting to `Decimal`, which would have
    crashed on the very first write in a real deployment
  - `list_decks.py` and `get_due_cards.py` read `queryStringParameters`
    / `pathParameters` with `event.get(key, {})` — but real API Gateway
    proxy events set these to `null`, not omit them, when empty. `.get()`
    on `None` threw an `AttributeError`, which the handler's broad
    exception handler turned into a misleading 500 instead of the
    intended 400.

Run them yourself: `cd backend && pip install -r requirements-dev.txt && pytest`

**Not testable here, needs your own setup:**
- The actual Claude API call in `generate_flashcards.py` — needs your own
  `ANTHROPIC_API_KEY`
- Real Lambda/API Gateway/DynamoDB/S3 deployment — this sandbox has no AWS
  access at all

## Stack

Python (AWS Lambda handlers), DynamoDB, S3, API Gateway, Claude API, React (Vite)

## Deploying for real

Requires the [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html)
and an AWS account.

```bash
cd backend
sam build
sam deploy --guided
```

You'll be prompted for your Anthropic API key during deploy (stored securely,
not in the code). SAM will output your API Gateway URL when done — put that
in the frontend's `.env`:

```bash
cd frontend
echo "VITE_API_BASE=https://your-api-url-here" > .env
npm install
npm run dev
```

## Testing the backend locally without deploying

The Lambda functions can be tested directly without AWS using `moto`
(mocks AWS services in-process):

```bash
pip install moto boto3 --break-system-packages
python3 -m pytest tests/  # if you add pytest tests, or run functions directly like:
```

See `backend/lambda_functions/sm2.py` for the algorithm itself — it has no
AWS dependency at all and can be tested completely standalone.
