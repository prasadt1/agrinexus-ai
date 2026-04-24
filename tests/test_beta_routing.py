import json
import os
import importlib


def test_webhook_routes_beta_phone_to_beta_queue(monkeypatch):
    os.environ["QUEUE_URL"] = "https://sqs.local/live"
    os.environ["QUEUE_URL_BETA"] = "https://sqs.local/beta"
    os.environ["TABLE_NAME"] = "tbl"
    os.environ["VERIFY_SIGNATURE"] = "false"
    os.environ["BETA_PHONES"] = "1555123000000"

    from src.webhook import handler as webhook
    importlib.reload(webhook)

    sent = []

    class _FakeSqs:
        def send_message(self, **kwargs):
            sent.append(kwargs)
            return {"MessageId": "m1"}

    class _FakeTable:
        def query(self, **_kwargs):
            return {"Count": 0}

        def put_item(self, **_kwargs):
            return {"ResponseMetadata": {"HTTPStatusCode": 200}}

        def get_item(self, **_kwargs):
            return {}

    monkeypatch.setattr(webhook, "sqs", _FakeSqs())
    monkeypatch.setattr(webhook, "table", _FakeTable())
    monkeypatch.setattr(webhook, "check_rate_limit", lambda *_args, **_kwargs: True)

    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "id": "wamid.1",
                                    "from": "1555123000000",
                                    "type": "text",
                                    "text": {"body": "hi"},
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }
    event = {"httpMethod": "POST", "path": "/webhook", "headers": {}, "body": json.dumps(payload)}
    resp = webhook.lambda_handler(event, None)
    assert resp["statusCode"] == 200
    assert sent
    assert sent[0]["QueueUrl"] == "https://sqs.local/beta"

