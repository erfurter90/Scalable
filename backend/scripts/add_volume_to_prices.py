#!/usr/bin/env python3
"""
Füge Volume-Daten zu den Bitcoin-Preisen hinzu.
Volume wird basierend auf Preisbewegungen generiert.
"""

import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent.parent / "data"
JSON_FILE = DATA_DIR / "bitcoin_daily_prices.json"

def generate_volume_from_prices(prices_dict):
    """
    Generiere Volume basierend auf Preisbewegungen.
    - Höhere Preisbewegungen = höheres Volume
    - Durchschnittliches Volume: 50000 BTC (simuliert)
    """

    dates = sorted(prices_dict.keys())
    volumes = {}

    for i, date in enumerate(dates):
        current_price = prices_dict[date]

        if i == 0:
            # Erster Tag: Basis-Volume
            base_volume = 5000
        else:
            # Volume basierend auf Preisbewegung
            prev_price = prices_dict[dates[i-1]]
            price_change_percent = abs((current_price - prev_price) / prev_price) * 100 if prev_price > 0 else 0

            # Je höher die Preisbewegung, desto höher das Volume
            # Base = 10000, mit bis zu 100000 BTC für extreme Moves
            base_volume = 10000 + (price_change_percent * 500)
            base_volume = min(base_volume, 100000)  # Cap at 100k

        # Füge etwas Randomness hinzu (simuliert echte Variabilität)
        # Für deterministisch: verwende einen einfachen Hash basierend auf Datum
        date_hash = sum(ord(c) for c in date) % 1000 / 1000
        volume_multiplier = 0.8 + (date_hash * 0.4)  # 0.8 - 1.2

        volumes[date] = round(base_volume * volume_multiplier, 0)

    return volumes

def main():
    print("Lese Bitcoin-Preise...")

    with open(JSON_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    prices = data.get('prices', {})
    print(f"Gefunden: {len(prices)} Preiseinträge")

    print("Generiere Volume-Daten basierend auf Preisbewegungen...")
    volumes = generate_volume_from_prices(prices)

    # Füge Volume zu den Daten hinzu
    data['volumes'] = volumes

    # Speichere die neuen Daten
    print(f"Speichere aktualisierte Daten in {JSON_FILE}...")
    with open(JSON_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

    print("[OK] Fertig!")
    print(f"   Preiseinträge: {len(prices)}")
    print(f"   Volume-Einträge: {len(volumes)}")
    print(f"   Durchschnittliches Volume: {sum(volumes.values()) / len(volumes):.0f} BTC")
    print(f"   Min Volume: {min(volumes.values()):.0f} BTC")
    print(f"   Max Volume: {max(volumes.values()):.0f} BTC")

if __name__ == "__main__":
    main()
