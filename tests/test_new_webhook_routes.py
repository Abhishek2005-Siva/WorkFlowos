import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient
from nacl.signing import SigningKey

from backend.config import get_settings
from backend.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_discord_ping_returns_pong(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "discord_public_key", "")
    resp = client.post("/discord/interactions", json={"type": 1})
    assert resp.status_code == 200
    assert resp.json() == {"type": 1}


def test_discord_interactions_rejects_bad_signature(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "discord_public_key", SigningKey.generate().verify_key.encode().hex())
    resp = client.post(
        "/discord/interactions",
        json={"type": 1},
        headers={"X-Signature-Ed25519": "00" * 64, "X-Signature-Timestamp": "123"},
    )
    assert resp.status_code == 401
    assert resp.json() == {"error": "invalid request signature"}


def test_github_webhook_accepts_valid_signature(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "github_webhook_secret", "topsecret")
    body = json.dumps({"action": "opened", "issue": {"number": 1, "title": "x", "body": "", "html_url": "u"}}).encode()
    signature = "sha256=" + hmac.new(b"topsecret", body, hashlib.sha256).hexdigest()
    resp = client.post(
        "/webhooks/github",
        content=body,
        headers={"X-Hub-Signature-256": signature, "X-GitHub-Event": "issues", "Content-Type": "application/json"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"status": "accepted"}


def test_github_webhook_rejects_invalid_signature(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "github_webhook_secret", "topsecret")
    body = b'{"action": "opened"}'
    resp = client.post(
        "/webhooks/github",
        content=body,
        headers={"X-Hub-Signature-256": "sha256=deadbeef", "X-GitHub-Event": "issues"},
    )
    assert resp.json() == {"status": "rejected"}
