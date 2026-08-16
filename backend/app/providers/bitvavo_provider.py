"""Read-only client for the user's own Bitvavo account data (balances, trade/deposit/
withdrawal history). Never places, cancels, or modifies an order — only ever issues GET
requests. Like every other provider in this app, this never raises: network/auth/HTTP errors
come back as a BitvavoResult with status="error" so bitvavo_sync_service can report a clean
failure instead of crashing.

Signature scheme verified against Bitvavo's own documented example (docs.bitvavo.com) and the
official python-bitvavo-api SDK source: HMAC-SHA256 over
`timestamp + method + "/v2" + endpoint + querystring + jsonBody`, hex-encoded, using the API
secret. The private "my trades" endpoint is `GET /v2/trades?market=...` (a query parameter) —
not `GET /v2/{market}/trades`, which is the public recent-trades endpoint for a market and
returns other traders' activity, not the account's own.
"""

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Literal

import httpx

from app.core.config import get_settings

_HOST = "https://api.bitvavo.com"
_API_PREFIX = "/v2"
_ACCESS_WINDOW_MS = "10000"

BitvavoStatus = Literal["ok", "error"]


@dataclass
class BitvavoResult:
    status: BitvavoStatus
    data: list[dict] | dict | None
    error_message: str | None = None


def _build_postfix(params: dict[str, str] | None) -> str:
    """Mirrors the official SDK's `createPostfix`: plain `key=value` joins, not `urllib`'s
    encoder, since the exact string built here is also what gets signed — any reordering or
    escaping difference between what we sign and what we send would break the signature."""
    if not params:
        return ""
    return "?" + "&".join(f"{key}={value}" for key, value in params.items())


class BitvavoProvider:
    name = "bitvavo"

    def __init__(self, timeout_seconds: float = 15.0) -> None:
        self._timeout = timeout_seconds

    @property
    def is_configured(self) -> bool:
        settings = get_settings()
        return bool(settings.bitvavo_api_key and settings.bitvavo_api_secret)

    def _sign(self, timestamp: str, method: str, path: str, body_str: str, secret: str) -> str:
        message = f"{timestamp}{method}{path}{body_str}"
        return hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()

    def _get(self, endpoint: str, params: dict[str, str] | None = None) -> BitvavoResult:
        settings = get_settings()
        if not self.is_configured:
            return BitvavoResult(
                status="error", data=None, error_message="Bitvavo-API nicht konfiguriert (Key/Secret fehlen)."
            )

        postfix = _build_postfix(params)
        path = f"{_API_PREFIX}{endpoint}{postfix}"
        timestamp = str(int(time.time() * 1000))
        signature = self._sign(timestamp, "GET", path, "", settings.bitvavo_api_secret)
        headers = {
            "Bitvavo-Access-Key": settings.bitvavo_api_key,
            "Bitvavo-Access-Timestamp": timestamp,
            "Bitvavo-Access-Signature": signature,
            "Bitvavo-Access-Window": _ACCESS_WINDOW_MS,
        }

        try:
            response = httpx.get(f"{_HOST}{path}", headers=headers, timeout=self._timeout)
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            return BitvavoResult(status="error", data=None, error_message=str(exc))

        if isinstance(data, dict) and "error" in data:
            return BitvavoResult(status="error", data=None, error_message=str(data.get("error")))

        return BitvavoResult(status="ok", data=data)

    def get_balance(self, symbol: str | None = None) -> BitvavoResult:
        return self._get("/balance", {"symbol": symbol} if symbol else None)

    def get_trades(self, market: str, limit: int = 1000, trade_id_from: str | None = None) -> BitvavoResult:
        params = {"market": market, "limit": str(limit)}
        if trade_id_from:
            params["tradeIdFrom"] = trade_id_from
        return self._get("/trades", params)

    def get_deposit_history(self, symbol: str | None = None, limit: int = 1000) -> BitvavoResult:
        params = {"limit": str(limit)}
        if symbol:
            params["symbol"] = symbol
        return self._get("/depositHistory", params)

    def get_withdrawal_history(self, symbol: str | None = None, limit: int = 1000) -> BitvavoResult:
        params = {"limit": str(limit)}
        if symbol:
            params["symbol"] = symbol
        return self._get("/withdrawalHistory", params)


def sign_for_test(timestamp: str, method: str, path: str, body: dict | None, secret: str) -> str:
    """Exposed only so the unit test can verify against Bitvavo's own documented example,
    which signs a POST body — the real provider above only ever issues GET requests."""
    body_str = json.dumps(body, separators=(",", ":")) if body else ""
    return BitvavoProvider()._sign(timestamp, method, path, body_str, secret)  # noqa: SLF001
