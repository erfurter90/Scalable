"""Service für Verwaltung historischer Bitcoin-Preise."""

import json
from datetime import datetime, UTC, timedelta
from pathlib import Path
from decimal import Decimal

from app.providers.coingecko_provider import CoinGeckoProvider

# Pfad zur JSON-Datei für historische Preise
DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"
BITCOIN_PRICES_FILE = DATA_DIR / "bitcoin_daily_prices.json"


def ensure_data_dir():
    """Stelle sicher, dass das Datenverzeichnis existiert."""
    DATA_DIR.mkdir(exist_ok=True)


def load_price_history() -> dict:
    """Lade die gespeicherten Bitcoin-Preise aus der JSON-Datei."""
    ensure_data_dir()

    if not BITCOIN_PRICES_FILE.exists():
        return {"prices": {}, "last_updated": None}

    try:
        with open(BITCOIN_PRICES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {"prices": {}, "last_updated": None}


def save_price_history(data: dict):
    """Speichere die Bitcoin-Preise in der JSON-Datei."""
    ensure_data_dir()
    with open(BITCOIN_PRICES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


def get_today_date_str() -> str:
    """Gib das heutige Datum im Format YYYY-MM-DD zurück."""
    return datetime.now(UTC).strftime("%Y-%m-%d")


async def update_price_history() -> dict:
    """
    Aktualisiere die Bitcoin-Preishistorie.
    - Lade die gespeicherten Preise
    - Prüfe, ob der heutige Tag bereits gespeichert ist
    - Wenn nicht, rufe den aktuellen Preis von CoinGecko ab und speichere ihn
    """
    history = load_price_history()
    today = get_today_date_str()

    # Prüfe, ob der heutige Tag bereits gespeichert ist
    if today in history.get("prices", {}):
        return history

    # Rufe den aktuellen Preis ab
    provider = CoinGeckoProvider()
    result = provider.fetch("btc_price_usd")

    if result.status == "ok" and result.value is not None:
        # Speichere den Preis
        if "prices" not in history:
            history["prices"] = {}

        history["prices"][today] = float(result.value)
        history["last_updated"] = datetime.now(UTC).isoformat()

        save_price_history(history)

    return history


def get_price_history() -> dict:
    """Gib alle gespeicherten Bitcoin-Preise mit Volume zurück."""
    history = load_price_history()

    # Konvertiere die Preise zu sortierten Liste
    prices_dict = history.get("prices", {})
    volumes_dict = history.get("volumes", {})

    prices_list = []
    for date_str, price in sorted(prices_dict.items()):
        prices_list.append({
            "date": date_str,
            "price": float(price) if isinstance(price, (int, float, Decimal)) else price,
            "volume": float(volumes_dict.get(date_str, 0))
        })

    return {
        "prices": prices_list,
        "last_updated": history.get("last_updated"),
        "total_days": len(prices_list)
    }


def get_prices_for_date_range(start_date: str, end_date: str) -> list:
    """
    Gib alle Bitcoin-Preise für einen Datumbereich zurück.
    Format: YYYY-MM-DD
    """
    history = load_price_history()
    prices = history.get("prices", {})
    volumes = history.get("volumes", {})

    result = []
    for date_str in sorted(prices.keys()):
        if start_date <= date_str <= end_date:
            result.append({
                "date": date_str,
                "price": float(prices[date_str]),
                "volume": float(volumes.get(date_str, 0))
            })

    return result
