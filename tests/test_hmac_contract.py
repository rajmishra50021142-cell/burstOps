"""Dependency-free pytest for the HMAC contract shared by dummy-serverless and
(anything else that mirrors gateway.py's sign_request()).

Imports hmac_util by inserting dummy-serverless/ onto sys.path — does NOT
import app.py, which would pull in FastAPI. No network, no Docker; `now` is
injected for deterministic stale-timestamp tests.
"""
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "dummy-serverless"))
import hmac_util  # noqa: E402

VECTORS = [
    # (secret, timestamp, body, expected_hex)
    ("local-dev-secret-change-in-prod", "1700000000", b"",
     "7545c853772dd927b78111771008f1ace824d14fd36c02e7c00b301ac3ab933b"),
    ("local-dev-secret-change-in-prod", "1700000000", b'{"n":100}',
     "263942c72316a870e757782819c315e543e1653dd9481beae4d6b53abb525d75"),
    ("test-secret", "1700000000", b"",
     "0f5d899b28266feacd0515cc219efef93968c602c49ecf488c15da01dba0b4a3"),
    ("test-secret", "1700000000", b'{"n":100}',
     "0bd99a3457b14815fed94d47656212f1a92580d93f8806cf86e67f87642a022b"),
]

NOW = 1_700_000_000.0


# 1. compute_signature reproduces all four golden vectors exactly
@pytest.mark.parametrize("secret,ts,body,expected", VECTORS)
def test_golden_vectors(secret, ts, body, expected):
    assert hmac_util.compute_signature(secret, ts, body) == expected


def _valid(secret="test-secret", ts="1700000000", body=b"", key="k"):
    return dict(
        secret=secret,
        expected_function_key=key,
        provided_function_key=key,
        timestamp=ts,
        signature=hmac_util.compute_signature(secret, ts, body),
        body=body,
        now=NOW,
    )


# 2. a valid request passes (now pinned to the timestamp)
def test_valid_request_passes():
    hmac_util.verify_request(**_valid())


def _raises(kwargs, status):
    with pytest.raises(hmac_util.SignatureError) as ei:
        hmac_util.verify_request(**kwargs)
    assert ei.value.status_code == status


# 3. wrong function key -> 403
def test_wrong_function_key():
    kw = _valid(); kw["provided_function_key"] = "wrong"
    _raises(kw, 403)


# 4. missing function key -> 403
def test_missing_function_key():
    kw = _valid(); kw["provided_function_key"] = None
    _raises(kw, 403)


# 5. missing / non-integer timestamp -> 401
@pytest.mark.parametrize("ts", [None, "abc", "17.5", ""])
def test_invalid_timestamp(ts):
    kw = _valid(ts="1700000000"); kw["timestamp"] = ts
    _raises(kw, 401)


# 6. stale in both directions: now +/- 301 -> 401
@pytest.mark.parametrize("offset", [-301, 301])
def test_stale_timestamp_both_directions(offset):
    ts = str(int(NOW + offset))
    kw = _valid(ts=ts)
    _raises(kw, 401)


# 7. boundary: now - 299 passes (skew boundary is inclusive at 300s)
def test_skew_boundary_299_passes():
    ts = str(int(NOW - 299))
    hmac_util.verify_request(**_valid(ts=ts))


def test_skew_boundary_301_fails():
    ts = str(int(NOW - 301))
    _raises(_valid(ts=ts), 401)


# 8. tamper case: signature over a different body -> 401
def test_tampered_body():
    kw = _valid(ts="1700000000", body=b'{"n":100}')
    kw["body"] = b'{"n":999}'
    _raises(kw, 401)


# 9. empty-body GET-style request with correct signature passes
def test_empty_body_get():
    hmac_util.verify_request(**_valid(body=b""))


# 10. all-zeros signature of right length -> 401, raises only SignatureError
def test_all_zero_signature():
    kw = _valid()
    kw["signature"] = "0" * 64
    _raises(kw, 401)


# ---------------------------------------------------------------------------
# Phase 4: the azure-function/ copy must agree with dummy-serverless/'s copy.
# This is the test that catches the two copies drifting apart.
# ---------------------------------------------------------------------------
import importlib.util

import random as _random

_ROOT = Path(__file__).resolve().parent.parent


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ds_mod = _load("hmac_util_dummy_serverless", _ROOT / "dummy-serverless" / "hmac_util.py")
af_mod = _load("hmac_util_azure_function", _ROOT / "azure-function" / "hmac_util.py")


@pytest.mark.parametrize("secret,ts,body,expected", VECTORS)
def test_azure_function_copy_matches_golden_vectors(secret, ts, body, expected):
    assert af_mod.compute_signature(secret, ts, body) == expected


def test_both_copies_agree_on_randomized_triples():
    rng = _random.Random(20260901)
    for _ in range(25):
        secret = "".join(rng.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=12))
        ts = str(rng.randint(1_500_000_000, 2_000_000_000))
        body = bytes(rng.choices(range(256), k=rng.randint(0, 64)))
        assert ds_mod.compute_signature(secret, ts, body) == af_mod.compute_signature(
            secret, ts, body
        )


def test_both_copies_verify_request_signatures_match():
    # inspect.signature equivalence as the softer structural check
    import inspect

    assert str(inspect.signature(ds_mod.verify_request)) == str(
        inspect.signature(af_mod.verify_request)
    )
