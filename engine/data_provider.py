from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Dict, List

import requests


@dataclass
class PriceSnapshot:
    prices: Dict[str, float]
    fetched_at: float


class BinanceDataProvider:
    """Fetches spot prices from Binance public REST API."""

    def __init__(self, logger) -> None:
        self._logger = logger
        self._session = requests.Session()

    def fetch_prices(self, symbols: List[str]) -> PriceSnapshot:
        endpoint = "https://api.binance.com/api/v3/ticker/price"
        payload = {"symbols": json.dumps(symbols, separators=(",", ":"))}
        response = self._session.get(endpoint, params=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        prices = {item["symbol"]: float(item["price"]) for item in data}
        fetched_at = time.time()
        return PriceSnapshot(prices=prices, fetched_at=fetched_at)
