from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class Holdings:
    asset: str
    quantity: float
    cash_usdt: float


class PaperBroker:
    """Simulates paper holdings with single-asset allocation."""

    def __init__(self, starting_balance: float) -> None:
        self._holdings = Holdings(asset="USDT", quantity=0.0, cash_usdt=starting_balance)

    @property
    def current_asset(self) -> str:
        return self._holdings.asset

    @property
    def cash_usdt(self) -> float:
        return self._holdings.cash_usdt

    @property
    def quantity(self) -> float:
        return self._holdings.quantity

    def equity_usdt(self, prices: Dict[str, float]) -> float:
        if self._holdings.asset == "USDT":
            return self._holdings.cash_usdt
        symbol = f"{self._holdings.asset}USDT"
        price = prices.get(symbol)
        if price is None:
            return self._holdings.cash_usdt
        return self._holdings.quantity * price

    def park_usdt(self, prices: Dict[str, float], cost_bps: float) -> None:
        if self._holdings.asset == "USDT":
            return
        symbol = f"{self._holdings.asset}USDT"
        price = prices.get(symbol)
        if price is None:
            return
        gross_usdt = self._holdings.quantity * price
        net_usdt = gross_usdt * (1 - cost_bps / 10000)
        self._holdings = Holdings(asset="USDT", quantity=0.0, cash_usdt=net_usdt)

    def buy_asset(self, asset: str, prices: Dict[str, float], cost_bps: float) -> None:
        symbol = f"{asset}USDT"
        price = prices.get(symbol)
        if price is None:
            return
        if self._holdings.asset != "USDT":
            return
        net_cash = self._holdings.cash_usdt * (1 - cost_bps / 10000)
        quantity = net_cash / price if price > 0 else 0.0
        self._holdings = Holdings(asset=asset, quantity=quantity, cash_usdt=0.0)

    def switch_asset(self, to_asset: str, prices: Dict[str, float], cost_bps_per_trade: float) -> None:
        if self._holdings.asset == to_asset:
            return
        if self._holdings.asset != "USDT":
            self.park_usdt(prices, cost_bps_per_trade)
        self.buy_asset(to_asset, prices, cost_bps_per_trade)
