"""Health endpoint tests — fast, no AWS calls."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "health"))
from handler import lambda_handler


class TestHealthHandler:
    def test_returns_200(self):
        result = lambda_handler({}, None)
        assert result["statusCode"] == 200

    def test_body_has_status_ok(self):
        body = json.loads(lambda_handler({}, None)["body"])
        assert body["status"] == "ok"

    def test_body_has_timestamp(self):
        body = json.loads(lambda_handler({}, None)["body"])
        assert "timestamp" in body
        assert "T" in body["timestamp"]  # ISO format

    def test_default_version(self):
        body = json.loads(lambda_handler({}, None)["body"])
        assert body["version"] == "1.0.0"

    def test_custom_version(self, monkeypatch):
        monkeypatch.setenv("APP_VERSION", "2.5.0")
        body = json.loads(lambda_handler({}, None)["body"])
        assert body["version"] == "2.5.0"

    def test_content_type_header(self):
        result = lambda_handler({}, None)
        assert result["headers"]["Content-Type"] == "application/json"
