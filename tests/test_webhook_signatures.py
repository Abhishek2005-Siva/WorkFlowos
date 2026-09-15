import hashlib
import hmac

from nacl.signing import SigningKey

from backend.utils.webhooks import verify_discord_signature, verify_github_signature


def test_github_signature_accepts_valid_hmac():
    secret = "topsecret"
    body = b'{"action": "opened"}'
    computed = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    assert verify_github_signature(body, computed, secret) is True


def test_github_signature_rejects_tampered_body():
    secret = "topsecret"
    computed = "sha256=" + hmac.new(secret.encode(), b'{"action": "opened"}', hashlib.sha256).hexdigest()

    assert verify_github_signature(b'{"action": "closed"}', computed, secret) is False


def test_github_signature_no_secret_configured_accepts_anything():
    assert verify_github_signature(b"anything", "", "") is True


def test_discord_signature_accepts_valid_ed25519():
    signing_key = SigningKey.generate()
    public_key_hex = signing_key.verify_key.encode().hex()
    timestamp = "1234567890"
    body = b'{"type": 1}'
    signature = signing_key.sign(timestamp.encode() + body).signature.hex()

    assert verify_discord_signature(body, signature, timestamp, public_key_hex) is True


def test_discord_signature_rejects_wrong_key():
    signing_key = SigningKey.generate()
    other_key = SigningKey.generate()
    public_key_hex = other_key.verify_key.encode().hex()
    timestamp = "1234567890"
    body = b'{"type": 1}'
    signature = signing_key.sign(timestamp.encode() + body).signature.hex()

    assert verify_discord_signature(body, signature, timestamp, public_key_hex) is False
