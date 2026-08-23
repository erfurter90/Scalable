"""Read-only client for the user's own Bitget account data (balances, trade/deposit/
withdrawal history). Never places, cancels, or modifies an order — only ever issues GET
requests. Like every other provider in this app, this never raises: network/auth/HTTP errors
come back as a BitgetResult with status="error" so bitget_sync_service can report a clean
failure instead of crashing.

Signature scheme verified against the official Bitget Python SDK source
(BitgetLimited/v3-bitget-api-sdk, bitget/utils.py: sign()/pre_hash()/parse_params_to_str()) —
bitget.com's own API docs are a JS single-page app that couldn't be fetched directly. Unlike
Bitvavo: the signature is HMAC-SHA256 **base64**-encoded (not hex), requires a third secret
(a passphrase chosen when the API key was created, sent as its own header), and query
parameters are sorted alphabetically by key before being appended to both the signed string
and the request URL.
"""

import base64
import hashlib
import hmac
import time
from dataclasses import dataclass
from typing import Literal

import httpx

from app.core.config import get_settings

_HOST = "https://api.bitget.com"

BitgetStatus = Literal["ok", "error"]


@dataclass
class BitgetResult:
    status: BitgetStatus
    data: list[dict] | dict | None
    error_message: str | None = None


def _build_query(params: dict[str, str] | None) -> str:
    """Mirrors the official SDK's `parse_params_to_str`: params sorted by key, joined as
    `key=value&key2=value2` with no URL-encoding — the exact string that also gets signed, so
    it must match byte-for-byte what's sent on the wire."""
    if not params:
        return ""
    sorted_items = sorted(params.items(), key=lambda kv: kv[0])
    return "?" + "&".join(f"{key}={value}" for key, value in sorted_items)


class BitgetProvider:
    name = "bitget"

    def __init__(self, timeout_seconds: float = 15.0) -> None:
        self._timeout = timeout_seconds

    @property
    def is_configured(self) -> bool:
        settings = get_settings()
        return bool(settings.bitget_api_key and settings.bitget_api_secret and settings.bitget_api_passphrase)

    def _sign(self, timestamp: str, method: str, request_path: str, body: str, secret: str) -> str:
        message = f"{timestamp}{method.upper()}{request_path}{body}"
        digest = hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).digest()
        return base64.b64encode(digest).decode("utf-8")

    def _get(self, endpoint: str, params: dict[str, str] | None = None) -> BitgetResult:
        settings = get_settings()
        if not self.is_configured:
            return BitgetResult(
                status="error", data=None, error_message="Bitget-API nicht konfiguriert (Key/Secret/Passphrase fehlen)."
            )

        request_path = f"{endpoint}{_build_query(params)}"
        timestamp = str(int(time.time() * 1000))
        signature = self._sign(timestamp, "GET", request_path, "", settings.bitget_api_secret)
        headers = {
            "ACCESS-KEY": settings.bitget_api_key,
            "ACCESS-SIGN": signature,
            "ACCESS-TIMESTAMP": timestamp,
            "ACCESS-PASSPHRASE": settings.bitget_api_passphrase,
            "Content-Type": "application/json",
        }

        try:
            response = httpx.get(f"{_HOST}{request_path}", headers=headers, timeout=self._timeout)
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            return BitgetResult(status="error", data=None, error_message=str(exc))

        # Bitget's v2 API returns HTTP 200 even for business errors, signalled by `code` !=
        # "00000" — a failed/misconfigured key surfaces here, not as an HTTP error status.
        if isinstance(data, dict) and data.get("code") not in (None, "00000"):
            return BitgetResult(status="error", data=None, error_message=str(data.get("msg") or data.get("code")))

        return BitgetResult(status="ok", data=data.get("data") if isinstance(data, dict) else data)

    def get_balance(self, coin: str | None = None) -> BitgetResult:
        return self._get("/api/v2/spot/account/assets", {"coin": coin} if coin else None)

    def get_tax_spot_records(self, start_time_ms: int, end_time_ms: int, limit: int = 100) -> BitgetResult:
        """The account's full spot ledger (buys, sells, external deposits, internal transfers,
        fiat top-ups) for a time window — built for tax reporting, so unlike
        `/api/v2/spot/trade/fills` (confirmed during development to only cover roughly the
        last 90 days), this one reaches back through the account's entire history. Bitget
        caps each request to a 30-day window (`startTime`/`endTime` interval), so covering
        multiple years requires paging backward in <=29-day windows — see
        bitget_sync_service._fetch_all_spot_records."""
        return self._get(
            "/api/v2/tax/spot-record",
            {"startTime": str(start_time_ms), "endTime": str(end_time_ms), "limit": str(limit)},
        )


def sign_for_test(timestamp: str, method: str, request_path: str, body: str, secret: str) -> str:
    """Exposed only so the unit test can verify against an independently hand-computed
    reference value using the same algorithm as the official SDK."""
    return BitgetProvider()._sign(timestamp, method, request_path, body, secret)  # noqa: SLF001
