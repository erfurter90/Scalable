"""Crypto Fear & Greed Index from alternative.me's free, keyless public API."""

from datetime import UTC, datetime
from decimal import Decimal

import httpx

from app.providers.base import ProviderResult

_ENDPOINT = "https://api.alternative.me/fng/"
_METRIC = "fear_greed_index"


class AlternativeMeFearGreedProvider:
    name = "alternative_me"

    def __init__(self, timeout_seconds: float = 10.0) -> None:
        self._timeout = timeout_seconds

    def supported_metrics(self) -> list[str]:
        return [_METRIC]

    def fetch(self, metric: str) -> ProviderResult:
        if metric != _METRIC:
            return ProviderResult(
                metric=metric,
                value=None,
                raw=None,
                unit=None,
                status="unavailable",
                source=self.name,
                source_endpoint=_ENDPOINT,
                as_of=None,
                error_message="metric not supported by AlternativeMeFearGreedProvider",
            )

        try:
            response = httpx.get(_ENDPOINT, params={"limit": 1}, timeout=self._timeout)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            return ProviderResult(
                metric=metric,
                value=None,
                raw=None,
                unit=None,
                status="error",
                source=self.name,
                source_endpoint=_ENDPOINT,
                as_of=None,
                error_message=str(exc),
            )

        entries = payload.get("data") or []
        if not entries:
            return ProviderResult(
                metric=metric,
                value=None,
                raw=payload,
                unit="index_0_100",
                status="unavailable",
                source=self.name,
                source_endpoint=_ENDPOINT,
                as_of=None,
                error_message="alternative.me returned no data entries",
            )

        entry = entries[0]
        try:
            value = Decimal(str(entry["value"]))
            as_of = datetime.fromtimestamp(int(entry["timestamp"]), tz=UTC)
        except (KeyError, ValueError, TypeError) as exc:
            return ProviderResult(
                metric=metric,
                value=None,
                raw=payload,
                unit="index_0_100",
                status="error",
                source=self.name,
                source_endpoint=_ENDPOINT,
                as_of=None,
                error_message=f"unexpected response shape: {exc}",
            )

        return ProviderResult(
            metric=metric,
            value=value,
            raw=payload,
            unit="index_0_100",
            status="ok",
            source=self.name,
            source_endpoint=_ENDPOINT,
            as_of=as_of,
        )
