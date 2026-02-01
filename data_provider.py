from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Deque

import requests


@dataclass
class PriceHistory:
    maxlen: int = 3600
    points: Deque[tuple[datetime, float]] = field(default_factory=deque)

    def append(self, timestamp: datetime, price: float) -> None:
        self.points.append((timestamp, price))
        while len(self.points) > self.maxlen:
            self.points.popleft()

    def price_at(self, target_time: datetime) -> float | None:
        for ts, price in reversed(self.points):
            if ts <= target_time:
                return price
        if self.points:
            return self.points[0][1]
        return None


@dataclass
class BinanceDataProvider:
    session: requests.Session | None = None
    history: dict[str, PriceHistory] = field(default_factory=dict)
    last_connection_ok: bool = True

    def _get_session(self) -> requests.Session:
        if self.session is None:
            self.session = requests.Session()
        return self.session

    def fetch_prices(self, symbols: list[str]) -> dict[str, float]:
        session = self._get_session()
        response = session.get("https://api.binance.com/api/v3/ticker/price", timeout=10)
        response.raise_for_status()
        payload = response.json()
        prices: dict[str, float] = {}
        for item in payload:
            symbol = item.get("symbol")
            if symbol in symbols:
                try:
                    prices[symbol] = float(item.get("price", 0))
                except (TypeError, ValueError):
                    continue
        return prices

    def update(self, symbols: list[str]) -> dict[str, dict[str, float]]:
        now = datetime.utcnow()
        try:
            prices = self.fetch_prices(symbols)
            self.last_connection_ok = True
        except requests.RequestException:
            self.last_connection_ok = False
            return {}

        snapshot: dict[str, dict[str, float]] = {}
        for symbol, price in prices.items():
            history = self.history.setdefault(symbol, PriceHistory())
            history.append(now, price)
            snapshot[symbol] = {
                "price_now": price,
                "price_15m_ago": self._price_delta(history, now, timedelta(minutes=15), price),
                "price_1h_ago": self._price_delta(history, now, timedelta(hours=1), price),
                "price_4h_ago": self._price_delta(history, now, timedelta(hours=4), price),
            }
        return snapshot

    @staticmethod
    def _price_delta(
        history: PriceHistory,
        now: datetime,
        delta: timedelta,
        fallback: float,
    ) -> float:
        target = now - delta
        price = history.price_at(target)
        return price if price is not None else fallback
