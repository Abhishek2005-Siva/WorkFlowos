"""Webhook signature verification helpers."""
from __future__ import annotations

import hashlib
import hmac
import time


def verify_slack_signature(body: bytes, timestamp: str, signature: str, signing_secret: str) -> bool:
    """Prevents replay attacks (5 min window) and forged requests."""
    if not signing_secret:
        # No secret configured (mock/dev mode) — accept everything.
        return True

    try:
        if abs(time.time() - int(timestamp)) > 60 * 5:
            return False
    except (ValueError, TypeError):
        return False

    basestring = f"v0:{timestamp}:{body.decode('utf-8')}".encode()
    computed = "v0=" + hmac.new(signing_secret.encode(), basestring, hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, signature)


def verify_github_signature(body: bytes, signature_header: str, secret: str) -> bool:
    """GitHub sends `X-Hub-Signature-256: sha256=<hexdigest>`."""
    if not secret:
        return True
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    computed = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, signature_header)


def verify_discord_signature(body: bytes, signature: str, timestamp: str, public_key_hex: str) -> bool:
    """Discord signs Interactions payloads with Ed25519, not HMAC."""
    if not public_key_hex:
        return True
    try:
        from nacl.signing import VerifyKey

        verify_key = VerifyKey(bytes.fromhex(public_key_hex))
        verify_key.verify(f"{timestamp}".encode() + body, bytes.fromhex(signature))
        return True
    except Exception:
        return False
