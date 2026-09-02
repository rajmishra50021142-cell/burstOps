"""HMAC request verification — pure stdlib, zero third-party imports.

SOURCE OF TRUTH: dummy-serverless/hmac_util.py — this file is a verbatim
copy. The two copies MUST stay identical (tests/test_hmac_contract.py
asserts they agree on all golden vectors). Do not "fix" one without the
other.

The signing scheme mirrors gateway.py's sign_request() byte-for-byte:
    signature = HMAC_SHA256(secret, f"{timestamp}:".encode() + body).hexdigest()
sent as headers x-functions-key / x-gateway-timestamp / x-gateway-signature.
"""
import hashlib
import hmac
import time

DEFAULT_MAX_CLOCK_SKEW_SECONDS = 300


def compute_signature(secret: str, timestamp: str, body: bytes) -> str:
    """Reference implementation, mirrors gateway.py's sign_request()."""
    return hmac.new(
        secret.encode("utf-8"),
        f"{timestamp}:".encode("utf-8") + body,
        hashlib.sha256,
    ).hexdigest()


class SignatureError(Exception):
    """Carries .status_code (401/403) and .reason (short, safe to log)."""

    def __init__(self, status_code: int, reason: str) -> None:
        super().__init__(reason)
        self.status_code = status_code
        self.reason = reason


def verify_request(
    *,
    secret: str,
    expected_function_key: str,
    provided_function_key: str | None,
    timestamp: str | None,
    signature: str | None,
    body: bytes,
    max_skew_seconds: int = DEFAULT_MAX_CLOCK_SKEW_SECONDS,
    now: float | None = None,
) -> None:
    """Raise SignatureError on any failure; return None when the request is valid.

    Check order (matters — a wrong-key caller must learn nothing about
    signature validity): function key, then timestamp presence/parse, then
    skew, then signature. Both key and signature compared with
    hmac.compare_digest — timing-safe comparison is the entire point.
    """
    if now is None:
        now = time.time()

    # 1. function key — 403 on missing or mismatched
    if provided_function_key is None or not hmac.compare_digest(
        provided_function_key, expected_function_key
    ):
        raise SignatureError(403, "invalid function key")

    # 2. timestamp presence / integer parse — 401
    if timestamp is None:
        raise SignatureError(401, "invalid timestamp")
    try:
        ts_value = int(timestamp)
    except (TypeError, ValueError):
        raise SignatureError(401, "invalid timestamp") from None

    # 3. clock skew — 401 in both directions
    if abs(now - ts_value) > max_skew_seconds:
        raise SignatureError(401, "stale timestamp")

    # 4. signature — 401 on missing or mismatched
    if signature is None:
        raise SignatureError(401, "invalid signature")
    expected = compute_signature(secret, timestamp, body)
    if not hmac.compare_digest(signature, expected):
        raise SignatureError(401, "invalid signature")
