import json
import os

import boto3
import pytest
from moto import mock_aws

os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("DECKS_TABLE", "Decks")
os.environ.setdefault("CARDS_TABLE", "Cards")


@pytest.fixture
def make_event():
    """
    Build an API Gateway proxy event as it looks after the Cognito authorizer:
    the user id lives in requestContext.authorizer.claims.sub.
    Pass user_id=None to simulate an unauthenticated request.
    """

    def _make(
        user_id="user-1", body=None, raw_body=None, path=None, query=None, method="GET"
    ):
        authorizer = {"claims": {"sub": user_id}} if user_id else None
        return {
            "httpMethod": method,
            "requestContext": {"authorizer": authorizer},
            "pathParameters": path,
            "queryStringParameters": query,
            "body": raw_body
            if raw_body is not None
            else (json.dumps(body) if body is not None else None),
        }

    return _make


@pytest.fixture(autouse=True)
def _reset_caches():
    # The boto3 resource is cached for speed; tests each get a fresh mock_aws.
    import db

    db.get_dynamodb_resource.cache_clear()
    yield
    db.get_dynamodb_resource.cache_clear()


@pytest.fixture
def dynamodb_tables():
    with mock_aws():
        client = boto3.client("dynamodb", region_name="us-east-1")
        client.create_table(
            TableName="Decks",
            AttributeDefinitions=[
                {"AttributeName": "deck_id", "AttributeType": "S"},
                {"AttributeName": "user_id", "AttributeType": "S"},
            ],
            KeySchema=[{"AttributeName": "deck_id", "KeyType": "HASH"}],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "user_id-index",
                    "KeySchema": [{"AttributeName": "user_id", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        client.create_table(
            TableName="Cards",
            AttributeDefinitions=[
                {"AttributeName": "card_id", "AttributeType": "S"},
                {"AttributeName": "deck_id", "AttributeType": "S"},
            ],
            KeySchema=[{"AttributeName": "card_id", "KeyType": "HASH"}],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "deck_id-index",
                    "KeySchema": [{"AttributeName": "deck_id", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        yield
