from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, List, Optional, Tuple


@dataclass
class ReturnWindow:
    ret_15m: Optional[float]
    ret_1h: Optional[float]
    ret_4h: Optional[float]


@dataclass
class ScoreRow:
    asset: str
    score: Optional[float]
    ret_15m: Optional[float]
    ret_1h: Optional[float]
    ret_4h: Optional[float]


class PriceHistory:
    """Stores price history for a single asset."""

    def __init__(self, max_age_sec: int) -> None:
        self._max_age_sec = max_age_sec
        self._data: Deque[Tuple[float, float]] = deque()

    def add(self, timestamp: float, price: float) -> None:
        self._data.append((timestamp, price))
        self._trim(timestamp)

    def _trim(self, now: float) -> None:
        while self._data and now - self._data[0][0] > self._max_age_sec:
            self._data.popleft()

    def _price_at_or_before(self, timestamp: float) -> Optional[float]:
        if not self._data:
            return None
        for ts, price in reversed(self._data):
            if ts <= timestamp:
                return price
        return None

    def returns(self, now: float, ret_15m_sec: int, ret_1h_sec: int, ret_4h_sec: int) -> ReturnWindow:
        current = self._data[-1][1] if self._data else None
        if current is None:
            return ReturnWindow(None, None, None)

        def calc(delta: int) -> Optional[float]:
            past_price = self._price_at_or_before(now - delta)
            if past_price is None or past_price <= 0:
                return None
            return (current / past_price) - 1.0

        return ReturnWindow(
            ret_15m=calc(ret_15m_sec),
            ret_1h=calc(ret_1h_sec),
            ret_4h=calc(ret_4h_sec),
        )


class ScoringEngine:
    """Calculates momentum scores based on price history."""

    def __init__(
        self,
        assets: List[str],
        ret_15m_sec: int,
        ret_1h_sec: int,
        ret_4h_sec: int,
        weight_15m: float,
        weight_1h: float,
        weight_4h: float,
    ) -> None:
        self._assets = assets
        self._ret_15m_sec = ret_15m_sec
        self._ret_1h_sec = ret_1h_sec
        self._ret_4h_sec = ret_4h_sec
        self._weight_15m = weight_15m
        self._weight_1h = weight_1h
        self._weight_4h = weight_4h
        max_age = max(ret_15m_sec, ret_1h_sec, ret_4h_sec) + 300
        self._histories: Dict[str, PriceHistory] = {
            asset: PriceHistory(max_age_sec=max_age) for asset in assets
        }

    def update_assets(self, assets: List[str]) -> None:
        if set(assets) == set(self._assets):
            return
        self._assets = assets
        max_age = max(self._ret_15m_sec, self._ret_1h_sec, self._ret_4h_sec) + 300
        self._histories = {asset: PriceHistory(max_age_sec=max_age) for asset in assets}

    def update_prices(self, prices: Dict[str, float], now: float) -> None:
        for asset in self._assets:
            symbol = f"{asset}USDT"
            price = prices.get(symbol)
            if price is None:
                continue
            self._histories[asset].add(now, price)

    def scores(self, now: Optional[float] = None) -> List[ScoreRow]:
        if now is None:
            now = time.time()
        rows: List[ScoreRow] = []
        for asset in self._assets:
            history = self._histories.get(asset)
            if history is None:
                continue
            returns = history.returns(
                now,
                ret_15m_sec=self._ret_15m_sec,
                ret_1h_sec=self._ret_1h_sec,
                ret_4h_sec=self._ret_4h_sec,
            )
            score = None
            if returns.ret_15m is not None and returns.ret_1h is not None and returns.ret_4h is not None:
                score = (
                    self._weight_15m * returns.ret_15m
                    + self._weight_1h * returns.ret_1h
                    + self._weight_4h * returns.ret_4h
                )
            rows.append(
                ScoreRow(
                    asset=asset,
                    score=score,
                    ret_15m=returns.ret_15m,
                    ret_1h=returns.ret_1h,
                    ret_4h=returns.ret_4h,
                )
            )
        return rows
