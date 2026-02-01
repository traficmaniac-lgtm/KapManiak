from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CostModel:
    fee_bps: float
    slippage_bps: float
    spread_bps_buffer: float

    @property
    def per_trade_bps(self) -> float:
        return self.fee_bps + self.slippage_bps + self.spread_bps_buffer

    def switch_cost_bps(self) -> float:
        return 2 * self.per_trade_bps
