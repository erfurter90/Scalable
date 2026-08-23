"""Read-only client for the user's own Coinbase (Advanced Trade) account data (balances,
fill/trade history). Never places, cancels, or modifies an order — only ever issues GET
requests. Like every other provider in this app, this never raises: network/auth/HTTP errors
come back as a CoinbaseResult with status="error" so coinbase_sync_service can report a clean
failure instead of crashing.

Auth scheme verified against the official Python SDK source
(coinbase/coinbase-advanced-py, coinbase/jwt_generator.py) — unlike Bitvavo/Bitget's HMAC
shared-secret schemes, Coinbase signs each request with a short-lived JWT built from an
asymmetric key pair (ES256 for EC keys, EdDSA for Ed25519 keys — CDP lets you pick either when
creating the key): claims `sub`/`iss`/`nbf`/`exp`/`uri`, header `kid`/`nonce`.
"""

import base64
import binascii
import secrets
import time
from dataclasses import dataclass
from typing import Literal

import httpx
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519

from app.core.config import get_settings

_HOST = "api.coinbase.com"
_BASE_URL = f"https://{_HOST}"
_API_PREFIX = "/api/v3/brokerage"
_JWT_TTL_SECONDS = 120
# Newer CDP "Secret API Keys" hand out a raw Ed25519 keypair instead of a PEM block: a
# base64 string that decodes to 64 bytes (32-byte seed + 32-byte public key).
_ED25519_RAW_KEYPAIR_LENGTH = 64

CoinbaseStatus = Literal["ok", "error"]


@dataclass
class CoinbaseResult:
    status: CoinbaseStatus
    data: dict | list | None
    error_message: str | None = None


def _load_private_key(key_env_value: str):
    stripped = key_env_value.strip()
    if stripped.startswith("-----BEGIN"):
        # .env values can't contain real newlines, so the PEM block is stored with literal
        # "\n" escapes and unescaped here.
        pem = key_env_value.replace("\\n", "\n").encode("utf-8")
        return serialization.load_pem_private_key(pem, password=None)

    try:
        raw = base64.b64decode(stripped, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Private Key ist weder ein PEM-Block noch ein gültiger Base64-String.") from exc
    if len(raw) != _ED25519_RAW_KEYPAIR_LENGTH:
        raise ValueError(f"Unerwartete Länge für rohen Ed25519-Key: {len(raw)} Bytes (erwartet: 64).")
    return ed25519.Ed25519PrivateKey.from_private_bytes(raw[:32])


def _algorithm_for(private_key) -> str:
    if isinstance(private_key, ed25519.Ed25519PrivateKey):
        return "EdDSA"
    if isinstance(private_key, ec.EllipticCurvePrivateKey):
        return "ES256"
    raise ValueError(f"Unsupported Coinbase private key type: {type(private_key).__name__}")


class CoinbaseProvider:
    name = "coinbase"

    def __init__(self, timeout_seconds: float = 15.0) -> None:
        self._timeout = timeout_seconds

    @property
    def is_configured(self) -> bool:
        settings = get_settings()
        return bool(settings.coinbase_api_key_name and settings.coinbase_api_private_key)

    def _build_jwt(self, method: str, path: str) -> str:
        settings = get_settings()
        private_key = _load_private_key(settings.coinbase_api_private_key)
        key_name = settings.coinbase_api_key_name
        now = int(time.time())
        claims = {
            "sub": key_name,
            "iss": "cdp",
            "nbf": now,
            "exp": now + _JWT_TTL_SECONDS,
            "uri": f"{method} {_HOST}{path}",
        }
        return jwt.encode(
            claims,
            private_key,
            algorithm=_algorithm_for(private_key),
            headers={"kid": key_name, "nonce": secrets.token_hex()},
        )

    def _get(self, path: str, params: dict[str, str] | None = None) -> CoinbaseResult:
        if not self.is_configured:
            return CoinbaseResult(
                status="error", data=None, error_message="Coinbase-API nicht konfiguriert (Key-Name/Private-Key fehlen)."
            )

        try:
            token = self._build_jwt("GET", path)
        except (ValueError, TypeError) as exc:
            return CoinbaseResult(status="error", data=None, error_message=f"Private Key ungültig: {exc}")

        headers = {"Authorization": f"Bearer {token}"}
        try:
            response = httpx.get(f"{_BASE_URL}{path}", headers=headers, params=params, timeout=self._timeout)
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            return CoinbaseResult(status="error", data=None, error_message=str(exc))

        return CoinbaseResult(status="ok", data=data)

    def get_accounts(self, cursor: str | None = None) -> CoinbaseResult:
        params = {"limit": "250"}
        if cursor:
            params["cursor"] = cursor
        return self._get(f"{_API_PREFIX}/accounts", params)

    def get_fills(self, cursor: str | None = None, product_ids: list[str] | None = None) -> CoinbaseResult:
        params: dict[str, str] = {"limit": "100"}
        if cursor:
            params["cursor"] = cursor
        if product_ids:
            params["product_ids"] = ",".join(product_ids)
        return self._get(f"{_API_PREFIX}/orders/historical/fills", params)


def sign_for_test(method: str, path: str, key_name: str, pem: str) -> str:
    """Exposed only so the unit test can build a JWT with a locally generated test key pair
    and verify it by decoding with the matching public key — Coinbase publishes no fixed test
    vector the way Bitvavo's docs did."""
    private_key = _load_private_key(pem)
    now = int(time.time())
    claims = {
        "sub": key_name,
        "iss": "cdp",
        "nbf": now,
        "exp": now + _JWT_TTL_SECONDS,
        "uri": f"{method} {_HOST}{path}",
    }
    return jwt.encode(
        claims, private_key, algorithm=_algorithm_for(private_key), headers={"kid": key_name, "nonce": secrets.token_hex()}
    )
