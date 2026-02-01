from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class PaperPortfolio:
    asset: str
    qty: float
    start_equity_usdt: float
    equity_usdt: float = 0.0
    total_cost_paid_usdt: float = 0.0
    switches_count: int = 0
    last_switch_ts: datetime | None = None

    @classmethod
    def from_start(cls, asset: str, start_equity_usdt: float) -> "PaperPortfolio":
        qty = start_equity_usdt if asset == "USDT" else 0.0
        return cls(asset=asset, qty=qty, start_equity_usdt=start_equity_usdt, equity_usdt=start_equity_usdt)

    def value_in_usdt(self, prices_now: dict[str, float]) -> float:
        if self.asset == "USDT":
            return self.qty
        price = self._price_for_asset(self.asset, prices_now)
        return self.qty * price

    def simulate_switch_via_usdt(
        self,
        target_asset: str,
        prices_now: dict[str, float],
        cost_bps: float,
        now: datetime | None = None,
    ) -> dict[str, float | str | bool | None]:
        if self.asset == target_asset:
            return {
                "status": "NOOP",
                "from_asset": self.asset,
                "to_asset": target_asset,
                "v_before": None,
                "v_after": None,
                "cost_paid": 0.0,
                "px_used": None,
            }

        now = now or datetime.utcnow()
        from_asset = self.asset
        v_before = self.value_in_usdt(prices_now)
        cost_pct = cost_bps / 10_000
        v_after = v_before * (1 - cost_pct) * (1 - cost_pct)

        px_used = None
        if target_asset == "USDT":
            self.qty = v_after
            self.asset = "USDT"
            if from_asset != "USDT":
                px_used = self._price_for_asset(from_asset, prices_now)
        else:
            px_used = self._price_for_asset(target_asset, prices_now)
            self.qty = v_after / px_used
            self.asset = target_asset

        cost_paid = v_before - v_after
        self.total_cost_paid_usdt += cost_paid
        self.switches_count += 1
        self.last_switch_ts = now
        self.equity_usdt = v_after

        return {
            "status": "SWITCHED",
            "from_asset": from_asset,
            "to_asset": target_asset,
            "v_before": v_before,
            "v_after": v_after,
            "cost_paid": cost_paid,
            "px_used": px_used,
        }

    def update_equity(self, prices_now: dict[str, float]) -> float:
        self.equity_usdt = self.value_in_usdt(prices_now)
        return self.equity_usdt

    @staticmethod
    def _price_for_asset(asset: str, prices_now: dict[str, float]) -> float:
        if asset == "USDT":
            return 1.0
        if asset not in prices_now:
            raise KeyError(f"Missing price for {asset}")
        return prices_now[asset]
