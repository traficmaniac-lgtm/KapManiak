from dataclasses import dataclass


@dataclass(frozen=True)
class AppConfig:
    sample_interval: int = 10
    universe_size: int = 10
    min_quote_volume: float = 5_000_000.0
    edge_threshold: float = 0.005
    net_edge_min: float = 0.0025
    fee_bps: float = 7.5
    slippage_bps: float = 5.0
    spread_bps: float = 2.0

    @property
    def cost_bps(self) -> float:
        return 2 * (self.fee_bps + self.slippage_bps + self.spread_bps)

    @property
    def cost_pct(self) -> float:
        return self.cost_bps / 10_000


DEFAULT_CONFIG = AppConfig()
