"""
common.py
---------
Helpers shared by every Lambda handler: the JSON/CORS response builder,
request parsing, the authenticated user lookup, and a decorator that turns
exceptions into proper HTTP responses.

Why one module: CORS headers, error shapes and logging used to be copy-pasted
into each handler, so a change had to be made four times.
"""

import functools
import json
import logging
import os
from datetime import date, datetime, timedelta, timezone

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Card field limits, shared by AI generation and manual editing.
MAX_FRONT_CHARS = 500
MAX_BACK_CHARS = 1500


class ApiError(Exception):
    """Raise anywhere in a handler to return a clean HTTP error to the client."""

    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": os.environ.get("ALLOWED_ORIGIN", "*"),
        },
        "body": json.dumps(body),
    }


def parse_body(event: dict) -> dict:
    """Parse the JSON request body; anything that isn't a JSON object is a 400."""
    raw = event.get("body") or "{}"
    try:
        body = json.loads(raw)
    except (TypeError, ValueError):
        raise ApiError(400, "Request body must be valid JSON")
    if not isinstance(body, dict):
        raise ApiError(400, "Request body must be a JSON object")
    return body


def get_user_id(event: dict) -> str:
    """
    The authenticated user's id (Cognito `sub`), as set by the API Gateway
    authorizer. We never trust a user id sent by the client.
    """
    claims = ((event.get("requestContext") or {}).get("authorizer") or {}).get(
        "claims"
    ) or {}
    sub = claims.get("sub")
    if not sub:
        raise ApiError(401, "Not authenticated")
    return sub


def path_param(event: dict, name: str) -> str:
    value = (event.get("pathParameters") or {}).get(name)
    if not value:
        raise ApiError(400, f"{name} is required")
    return value


def utc_today() -> date:
    return datetime.now(timezone.utc).date()


def parse_today(raw: str | None) -> date:
    """
    The client's local date (YYYY-MM-DD), so "due today" follows the user's
    day instead of UTC. Anything more than a day away from UTC today is
    impossible for a real timezone, so it is rejected.
    """
    if not raw:
        return utc_today()
    try:
        value = date.fromisoformat(raw)
    except (TypeError, ValueError):
        raise ApiError(400, "today must be a date formatted YYYY-MM-DD")
    if abs(value - utc_today()) > timedelta(days=1):
        raise ApiError(400, "today is out of range")
    return value


def query_param(event: dict, name: str) -> str | None:
    return (event.get("queryStringParameters") or {}).get(name)


def api_handler(fn):
    """Map ApiError to its status code and everything else to a generic 500."""

    @functools.wraps(fn)
    def wrapper(event, context):
        try:
            return fn(event, context)
        except ApiError as e:
            return response(e.status_code, {"error": e.message})
        except Exception:
            # Log the details server-side; never leak internals to the client.
            logger.exception("Unhandled error in %s", fn.__name__)
            return response(500, {"error": "Internal server error"})

    return wrapper
