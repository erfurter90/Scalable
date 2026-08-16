"""USD/EUR exchange rate, used to convert a purchase price entered in USD into the app's EUR
base currency for average acquisition cost tracking. Frankfurter is free, keyless, and
sourced from ECB reference rates — no API key management needed for this narrow use case."""

from datetime import UTC, datetime
from decimal import Decimal

import httpx

from app.providers.base import ProviderResult

_ENDPOINT = "https://api.frankfurter.dev/v1/latest"
_METRIC = "fx_usd_eur"


class FrankfurterFxProvider:
    name = "frankfurter"

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
                error_message="metric not supported by FrankfurterFxProvider",
            )

        try:
            response = httpx.get(
                _ENDPOINT, params={"from": "USD", "to": "EUR"}, timeout=self._timeout, follow_redirects=True
            )
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            return ProviderResult(
                metric=metric,
                value=None,
                raw=None,
                unit="EUR",
                status="error",
                source=self.name,
                source_endpoint=_ENDPOINT,
                as_of=None,
                error_message=str(exc),
            )

        rate = data.get("rates", {}).get("EUR")
        if rate is None:
            return ProviderResult(
                metric=metric,
                value=None,
                raw=data,
                unit="EUR",
                status="unavailable",
                source=self.name,
                source_endpoint=_ENDPOINT,
                as_of=None,
                error_message="Frankfurter response missing an EUR rate",
            )

        return ProviderResult(
            metric=metric,
            value=Decimal(str(rate)),
            raw=data,
            unit="EUR",
            status="ok",
            source=self.name,
            source_endpoint=_ENDPOINT,
            as_of=datetime.now(UTC),
        )
