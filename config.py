from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class AppConfig:
    """Configuration for KapManiak v0.1 (PAPER mode only)."""

    starting_balance: float = 10000.0
    update_interval_sec: int = 10
    universe: List[str] = field(
        default_factory=lambda: [
            "BTC",
            "ETH",
            "BNB",
            "SOL",
            "XRP",
            "ADA",
            "DOGE",
            "TRX",
            "MATIC",
            "DOT",
            "LTC",
            "AVAX",
            "LINK",
            "BCH",
            "XLM",
            "ATOM",
            "ETC",
            "FIL",
            "APT",
            "NEAR",
        ]
    )
    edge_threshold_pct: float = 0.5
    confirm_n: int = 3
    min_hold_sec: int = 900
    cooldown_sec: int = 120
    max_switches_per_day: int = 12
    data_stale_sec: int = 30
    ret_15m_sec: int = 15 * 60
    ret_1h_sec: int = 60 * 60
    ret_4h_sec: int = 4 * 60 * 60
    weight_15m: float = 0.5
    weight_1h: float = 0.3
    weight_4h: float = 0.2
    fee_bps: float = 7.5
    slippage_bps: float = 5.0
    spread_bps_buffer: float = 2.0
    net_edge_gate_enabled: bool = True
    net_edge_min_pct: float = 0.25

    @property
    def symbols(self) -> List[str]:
        return [f"{asset}USDT" for asset in self.universe]
