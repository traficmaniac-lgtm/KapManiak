from dataclasses import dataclass


@dataclass(frozen=True)
class AppConfig:
    sample_interval_sec: int = 10
    universe_size: int = 10
    min_quote_volume: float = 5_000_000.0
    confirm_n: int = 3
    min_hold_sec: int = 15 * 60
    cooldown_sec: int = 120
    edge_threshold_pct: float = 0.5
    net_edge_min_pct: float = 0.25
    max_switches_day: int = 12
    data_stale_sec: int = 30
    safe_mode_action: str = "STOP"
    fee_bps: float = 7.5
    slippage_bps: float = 5.0
    spread_bps: float = 2.0

    @property
    def sample_interval(self) -> int:
        return self.sample_interval_sec

    @property
    def edge_threshold(self) -> float:
        return self.edge_threshold_pct / 100

    @property
    def net_edge_min(self) -> float:
        return self.net_edge_min_pct / 100

    @property
    def cost_bps(self) -> float:
        return 2 * (self.fee_bps + self.slippage_bps + self.spread_bps)

    @property
    def cost_pct(self) -> float:
        return self.cost_bps / 10_000


DEFAULT_CONFIG = AppConfig()
