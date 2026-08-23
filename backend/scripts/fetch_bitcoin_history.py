#!/usr/bin/env python3
"""
Skript zum Abrufen historischer Bitcoin-Preise von CoinGecko
und Speichern in JSON-Datei.
"""

import json
import sys
import urllib.request
import urllib.error
from datetime import datetime, UTC
from pathlib import Path

# Pfad zur JSON-Datei
DATA_DIR = Path(__file__).parent.parent.parent / "data"
BITCOIN_PRICES_FILE = DATA_DIR / "bitcoin_daily_prices.json"


def ensure_data_dir():
    """Stelle sicher, dass das Datenverzeichnis existiert."""
    DATA_DIR.mkdir(exist_ok=True)


def fetch_historical_prices(start_date: str = "2022-06-01") -> dict:
    """
    Rufe historische Bitcoin-Preise von CoinGecko ab.

    Args:
        start_date: Startdatum im Format YYYY-MM-DD

    Returns:
        Dictionary mit Preisen und Metadaten
    """
    print(f"Fetching Bitcoin price history from CoinGecko starting {start_date}...")

    # CoinGecko API Endpoint für historische Daten
    url = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"

    params = {
        "vs_currency": "usd",
        "days": "1400",  # ~4 Jahre ab Juni 2022
        "interval": "daily",
    }

    try:
        # Baue URL mit Parametern
        from urllib.parse import urlencode
        query_string = urlencode(params)
        full_url = f"{url}?{query_string}"

        # Abrufen mit User-Agent Header
        request = urllib.request.Request(
            full_url,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode('utf-8'))

        prices_dict = {}
        prices_data = data.get("prices", [])

        # Konvertiere Timestamp in YYYY-MM-DD Format
        for timestamp_ms, price in prices_data:
            date = datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC)
            date_str = date.strftime("%Y-%m-%d")

            # Nur ab start_date speichern
            if date_str >= start_date:
                prices_dict[date_str] = round(float(price), 2)

        print(f"[OK] Fetched {len(prices_dict)} daily prices")
        return {
            "prices": prices_dict,
            "last_updated": datetime.now(UTC).isoformat(),
            "source": "CoinGecko API",
            "note": f"Data from {start_date} onwards",
        }

    except (urllib.error.HTTPError, urllib.error.URLError) as e:
        print(f"[ERROR] Error fetching data: {e}")
        return None


def merge_with_existing(new_data: dict) -> dict:
    """
    Merge neue Daten mit existierenden Daten.
    Neue Daten überschreiben ältere Daten für dieselben Tage.
    """
    ensure_data_dir()

    # Lade existierende Daten
    if BITCOIN_PRICES_FILE.exists():
        try:
            with open(BITCOIN_PRICES_FILE, "r", encoding="utf-8") as f:
                existing = json.load(f)
                existing_prices = existing.get("prices", {})
        except (json.JSONDecodeError, IOError):
            existing_prices = {}
    else:
        existing_prices = {}

    # Merge: Neue Daten überschreiben existierende
    merged_prices = {**existing_prices, **new_data["prices"]}

    return {
        "prices": merged_prices,
        "last_updated": new_data["last_updated"],
        "source": new_data["source"],
        "total_days": len(merged_prices),
    }


def save_prices(data: dict):
    """Speichere Preise in JSON-Datei."""
    ensure_data_dir()

    with open(BITCOIN_PRICES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"[OK] Saved {len(data['prices'])} prices to {BITCOIN_PRICES_FILE}")
    print(f"  Date range: {min(data['prices'].keys())} to {max(data['prices'].keys())}")
    print(f"  Last updated: {data['last_updated']}")


def main():
    """Hauptfunktion."""
    print("=" * 60)
    print("Bitcoin Price History Fetcher")
    print("=" * 60)

    # Abrufen
    new_data = fetch_historical_prices(start_date="2022-06-01")

    if not new_data:
        print("[ERROR] Failed to fetch data")
        sys.exit(1)

    # Merge
    merged = merge_with_existing(new_data)

    # Speichern
    save_prices(merged)

    print("=" * 60)
    print("[OK] Done!")
    print("=" * 60)


if __name__ == "__main__":
    main()
