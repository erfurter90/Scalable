#!/usr/bin/env python3
"""
Importiere echte Bitcoin-Preise aus Excel-Datei.
Ersetze die Sample-Daten mit echten historischen Daten.
"""

import json
import sys
from datetime import datetime, UTC
from pathlib import Path

try:
    import openpyxl
except ImportError:
    print("[ERROR] openpyxl not installed. Install with: pip install openpyxl")
    sys.exit(1)

# Pfade
EXCEL_FILE = Path(r"C:\Users\Administrator\Downloads\Bitcoin_historische_Schlusskurse_USD (1).xlsx")
DATA_DIR = Path(__file__).parent.parent.parent / "data"
JSON_FILE = DATA_DIR / "bitcoin_daily_prices.json"


def load_prices_from_excel() -> dict:
    """Lese Bitcoin-Preise aus Excel-Datei."""
    if not EXCEL_FILE.exists():
        print(f"[ERROR] Excel-Datei nicht gefunden: {EXCEL_FILE}")
        sys.exit(1)

    print(f"Lese Excel-Datei: {EXCEL_FILE}")

    # Öffne Workbook
    wb = openpyxl.load_workbook(EXCEL_FILE)
    ws = wb.active

    prices = {}
    skipped = 0

    # Lese Daten (ignoriere Header-Zeile)
    for row_idx, row in enumerate(ws.iter_rows(values_only=True), 1):
        if row_idx == 1:  # Skip header
            print(f"Header: {row}")
            continue

        if not row or len(row) < 2:
            continue

        try:
            date_val = row[0]
            price_val = row[1]

            # Parse Datum
            if isinstance(date_val, str):
                date_str = date_val.strip()
            else:
                # Assume it's a datetime object
                date_str = date_val.strftime("%Y-%m-%d") if hasattr(date_val, 'strftime') else str(date_val)

            # Parse Preis
            price = float(price_val)

            # Validiere Datum-Format
            try:
                datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                skipped += 1
                continue

            prices[date_str] = round(price, 2)

        except (ValueError, TypeError, AttributeError) as e:
            skipped += 1
            continue

    print(f"[OK] Gelesen: {len(prices)} Preise, {skipped} übersprungen")
    return prices


def save_to_json(prices: dict):
    """Speichere Preise in JSON-Datei."""
    DATA_DIR.mkdir(exist_ok=True)

    data = {
        "prices": prices,
        "last_updated": datetime.now(UTC).isoformat(),
        "source": "Excel import from Bitcoin_historische_Schlusskurse_USD.xlsx",
        "note": "Echte historische Bitcoin-Schlusskurse. Wird täglich mit CoinGecko aktualisiert.",
        "total_days": len(prices)
    }

    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"[OK] Gespeichert: {JSON_FILE}")
    print(f"  Datenpunkte: {len(prices)}")
    print(f"  Zeitraum: {min(prices.keys())} bis {max(prices.keys())}")
    print(f"  Min: ${min(prices.values()):.2f}, Max: ${max(prices.values()):.2f}")


def main():
    print("=" * 60)
    print("Bitcoin Preis-Import aus Excel")
    print("=" * 60)

    prices = load_prices_from_excel()
    save_to_json(prices)

    print("=" * 60)
    print("[OK] Import abgeschlossen!")
    print("=" * 60)


if __name__ == "__main__":
    main()
