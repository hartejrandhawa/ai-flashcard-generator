# AI Flashcard Generator

Turn study notes into flashcards and review them on a spaced-repetition schedule.

1. Sign in, then upload a PDF / `.txt` file or paste your notes.
2. Claude writes up to 30 question/answer cards. Review, edit or delete them on the deck page.
3. Study the cards that are due. Rate each one Again / Hard / Good / Easy.
4. [SM-2](https://en.wikipedia.org/wiki/SuperMemo#Algorithm_SM-2) (the algorithm behind Anki) schedules the next review: cards you know come back less often, cards you struggle with come back sooner.
5. Export any deck as CSV (importable into Anki).

## Architecture

```
React (Vite) ──HTTPS + Cognito ID token──▶ API Gateway (Cognito authorizer)
     │                                          │
     │ sign-in (PKCE)                           ├─ POST   /decks              ─▶ generate_flashcards ──async──▶ generate_worker ─▶ Claude
     ▼                                          ├─ GET    /decks              ─▶ list_decks
 Cognito hosted page                            ├─ PATCH/DELETE /decks/{id}   ─▶ manage_deck
                                                ├─ GET    /decks/{id}/cards   ─▶ get_deck_cards
                                                ├─ GET    /decks/{id}/due     ─▶ get_due_cards
                                                ├─ PATCH/DELETE /cards/{id}   ─▶ manage_card
                                                └─ POST   /reviews            ─▶ submit_review
                                                          │
                                                   DynamoDB: Decks, Cards
```

- **Backend:** Python 3.12 Lambdas deployed with AWS SAM (`backend/`).
- **Frontend:** React + Vite (`frontend/`). PDF text is extracted in the browser with pdfjs, so the server only ever sees text.
- **Generation is asynchronous.** `POST /decks` validates the request, creates the deck with `status: "generating"` and returns `202`. A separate worker function calls Claude and marks the deck `ready` or `failed`. The frontend polls `GET /decks`. A model call can take longer than API Gateway's 29-second limit, so it can't run inside the request.
- **Identity** comes from the verified Cognito token (`sub` claim). The server never trusts a user id sent by the client, and other users' decks and cards return `404`.

### API

All routes require `Authorization: <Cognito ID token>`. Errors are `{"error": "message"}`.

| Method & path | Purpose |
|---|---|
| `POST /decks` | Body `{deck_name, notes_text}` (notes ≤ 50,000 chars). Returns `202 {deck_id, status}`. `429` once the daily limit is used. |
| `GET /decks?today=YYYY-MM-DD` | The user's decks with `status`, `error`, `card_count`, `due_count`. |
| `PATCH /decks/{id}` · `DELETE /decks/{id}` | Rename (`{deck_name}`) or delete a deck and its cards. |
| `GET /decks/{id}/cards` | The deck plus all its cards. |
| `GET /decks/{id}/due?today=` | Cards due for review. |
| `PATCH /cards/{id}` · `DELETE /cards/{id}` | Edit (`{front, back}`) or delete a card. |
| `POST /reviews` | Body `{card_id, quality 0-5, today?}`. `409` if the card was reviewed concurrently. |

`today` is the browser's local date, so "due today" follows the user's day rather than UTC.

### Security notes

- The Anthropic API key lives in an SSM SecureString and is readable only by the worker function. It is never in the template or in Lambda environment variables.
- Uploaded notes are untrusted. They are wrapped in `<notes>` tags, the system prompt says to treat them as data, and every card the model returns is validated, de-duplicated and length-capped before it is stored.
- Spend controls: input size cap, a per-user daily generation limit (`DailyGenerationLimit`, default 20), and API Gateway throttling.
- CORS defaults to `*` for development. Set `AllowedOrigin` to your real frontend origin in production.

## Deploying

Requirements: an AWS account, the [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html), and an [Anthropic API key](https://console.anthropic.com).

1. **Store the API key** (once; CloudFormation can't create SecureStrings):

   ```bash
   aws ssm put-parameter --name /flashcards/anthropic-api-key --type SecureString --value "sk-ant-..."
   ```

2. **Deploy the backend.** Pick a globally unique `CognitoDomainPrefix`:

   ```bash
   cd backend
   cp samconfig.toml.example samconfig.toml   # edit the values
   sam build
   sam deploy
   ```

   The outputs include `ApiUrl`, `CognitoDomain` and `UserPoolClientId`.

3. **Configure and run the frontend:**

   ```bash
   cd frontend
   cp .env.example .env     # paste the three stack outputs
   npm install
   npm run dev              # http://localhost:5173
   ```

   `FrontendUrls` (stack parameter) must contain the exact origin you serve the app from, with a trailing slash, for sign-in to redirect back correctly. When you host the built app elsewhere, redeploy with that URL added.

4. **Tearing down:** the tables have deletion protection. Redeploy with `TableDeletionProtection=false`, then `sam delete`.

## Development

```bash
cd backend
uv sync
uv run pytest             # moto mocks AWS; the Anthropic client is faked

cd frontend
npm install
npm run lint
npm run build
```

Notes:

- No real AWS or Anthropic calls are made by the tests, so a green run doesn't prove a deployment works. The first `sam deploy` plus one real generation is the end-to-end check.
- If this folder is synced by iCloud Drive, put the Python virtualenv outside it (`export UV_PROJECT_ENVIRONMENT=~/.cache/envs/flashcard-backend`). Thousands of small files in `.venv` can make imports crawl.
- The model is set in `backend/lambda_functions/llm.py` (`CLAUDE_MODEL`).

## Project layout

```
backend/
  template.yaml            SAM template: API, Cognito, tables, functions
  lambda_functions/        handlers + common.py (shared helpers), db.py, llm.py, sm2.py
  tests/                   pytest suite
frontend/
  src/auth.js              Cognito sign-in (PKCE)
  src/api/client.js        authenticated API client
  src/pages/               Home, Deck, Quiz
```
