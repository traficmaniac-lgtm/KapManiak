from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import requests

from config import DEFAULT_CONFIG


STABLE_BASES = {
    "USDT",
    "USDC",
    "BUSD",
    "TUSD",
    "DAI",
    "FDUSD",
    "USDP",
}


@dataclass
class UniverseManager:
    session: requests.Session | None = None

    def _get_session(self) -> requests.Session:
        if self.session is None:
            self.session = requests.Session()
        return self.session

    def fetch_universe(self) -> list[str]:
        session = self._get_session()
        response = session.get("https://api.binance.com/api/v3/ticker/24hr", timeout=10)
        response.raise_for_status()
        payload = response.json()
        assets = []
        for item in payload:
            symbol = item.get("symbol", "")
            if not symbol.endswith("USDT"):
                continue
            base = symbol.replace("USDT", "")
            if base in STABLE_BASES:
                continue
            try:
                quote_volume = float(item.get("quoteVolume", 0))
            except (TypeError, ValueError):
                continue
            if quote_volume < DEFAULT_CONFIG.min_quote_volume:
                continue
            assets.append((symbol, quote_volume))
        assets.sort(key=lambda entry: entry[1], reverse=True)
        return [symbol for symbol, _ in assets[: DEFAULT_CONFIG.universe_size]]

    def get_universe(self) -> list[str]:
        try:
            return self.fetch_universe()
        except requests.RequestException:
            return self.default_universe()

    @staticmethod
    def default_universe() -> list[str]:
        return [
            "BTCUSDT",
            "ETHUSDT",
            "BNBUSDT",
            "SOLUSDT",
            "XRPUSDT",
            "ADAUSDT",
            "DOGEUSDT",
            "AVAXUSDT",
            "LINKUSDT",
            "TRXUSDT",
        ]


def normalize_symbols(symbols: Iterable[str]) -> list[str]:
    return [symbol.upper() for symbol in symbols]
