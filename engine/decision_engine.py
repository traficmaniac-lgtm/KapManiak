from __future__ import annotations

import datetime as dt
import logging
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

from config import AppConfig
from engine.cost_model import CostModel
from engine.data_provider import BinanceDataProvider, PriceSnapshot
from engine.paper_broker import PaperBroker
from engine.scoring import ScoreRow, ScoringEngine
from engine.storage import Storage


@dataclass
class LeaderboardRow:
    rank: int
    asset: str
    score: Optional[float]
    ret_15m: Optional[float]
    ret_1h: Optional[float]
    ret_4h: Optional[float]
    edge_bps: Optional[float]
    cost_bps: float
    net_edge_bps: Optional[float]
    confirm: str
    signal: str


@dataclass
class DecisionSnapshot:
    mode: str
    connection: str
    last_update: float
    current_asset: str
    equity_usdt: float
    state: str
    leader: Optional[str]
    edge_pct: Optional[float]
    cost_bps: float
    net_edge_pct: Optional[float]
    confirm: str
    next_action: str
    reason_codes: List[str]
    leaderboard: List[LeaderboardRow]


class DecisionEngine:
    """Evaluates scores, applies decision logic, and updates paper holdings."""

    def __init__(
        self,
        config: AppConfig,
        data_provider: BinanceDataProvider,
        storage: Storage,
        logger: logging.Logger,
    ) -> None:
        self._config = config
        self._data_provider = data_provider
        self._storage = storage
        self._logger = logger
        self._scoring = ScoringEngine(
            assets=config.universe,
            ret_15m_sec=config.ret_15m_sec,
            ret_1h_sec=config.ret_1h_sec,
            ret_4h_sec=config.ret_4h_sec,
            weight_15m=config.weight_15m,
            weight_1h=config.weight_1h,
            weight_4h=config.weight_4h,
        )
        self._cost_model = CostModel(
            fee_bps=config.fee_bps,
            slippage_bps=config.slippage_bps,
            spread_bps_buffer=config.spread_bps_buffer,
        )
        self._broker = PaperBroker(config.starting_balance)
        self._last_update: Optional[float] = None
        self._last_switch_time: Optional[float] = None
        self._last_leader: Optional[str] = None
        self._confirm_count: int = 0
        self._cooldown_until: Optional[float] = None
        self._switch_count_day: int = 0
        self._switch_count_date: Optional[dt.date] = None
        self._blacklist: set[str] = set()

    @property
    def config(self) -> AppConfig:
        return self._config

    def update_config(self, config: AppConfig) -> None:
        self._config = config
        self._cost_model = CostModel(
            fee_bps=config.fee_bps,
            slippage_bps=config.slippage_bps,
            spread_bps_buffer=config.spread_bps_buffer,
        )
        self._scoring = ScoringEngine(
            assets=config.universe,
            ret_15m_sec=config.ret_15m_sec,
            ret_1h_sec=config.ret_1h_sec,
            ret_4h_sec=config.ret_4h_sec,
            weight_15m=config.weight_15m,
            weight_1h=config.weight_1h,
            weight_4h=config.weight_4h,
        )
        self._logger.info("Settings updated. Universe size=%s", len(config.universe))

    def blacklist_asset(self, asset: Optional[str]) -> None:
        if asset:
            self._blacklist.add(asset)
            self._logger.info("Blacklisted leader %s", asset)

    def fetch_prices(self) -> PriceSnapshot:
        return self._data_provider.fetch_prices(self._config.symbols)

    def process_prices(self, snapshot: PriceSnapshot) -> DecisionSnapshot:
        now = snapshot.fetched_at
        stale = self._data_stale(now)
        self._last_update = now
        self._scoring.update_assets(self._config.universe)
        self._scoring.update_prices(snapshot.prices, now)

        scores = self._scoring.scores(now)
        available = [row for row in scores if row.score is not None and row.asset not in self._blacklist]
        available.sort(key=lambda row: row.score or -999, reverse=True)

        leader_row = available[0] if available else None
        leader_asset = leader_row.asset if leader_row else None

        self._update_confirmation(leader_asset)
        current_asset = self._broker.current_asset
        current_row = next((row for row in scores if row.asset == current_asset), None)
        current_score = current_row.score if current_row else None

        edge_pct = None
        if leader_row and leader_row.score is not None:
            base = current_score or 0.0
            edge_pct = leader_row.score - base

        cost_bps = self._cost_model.switch_cost_bps()
        net_edge_pct = None
        if edge_pct is not None:
            net_edge_pct = edge_pct - (cost_bps / 10000)

        reason_codes: List[str] = []
        state = "HOLD"
        next_action = "HOLD"

        connection = "OK"
        if stale:
            connection = "DEGRADED"
            reason_codes.append("DATA_STALE")
            state = "SAFE"
        elif not leader_row:
            reason_codes.append("ERROR")
            state = "SAFE"
        else:
            self._reset_daily_switch_count(now)
            if not self._can_switch(now):
                if self._min_hold_active(now):
                    reason_codes.append("HOLD_MIN_HOLD")
                if self._cooldown_active(now):
                    reason_codes.append("HOLD_COOLDOWN")
                if self._switch_limit_reached():
                    reason_codes.append("HOLD_MAX_SWITCHES")
            elif edge_pct is not None and edge_pct < self._config.edge_threshold_pct / 100:
                reason_codes.append("HOLD_EDGE_TOO_SMALL")
            elif self._config.net_edge_gate_enabled and (net_edge_pct or 0) < self._config.net_edge_min_pct / 100:
                reason_codes.append("HOLD_NET_EDGE_TOO_SMALL")
            elif self._confirm_count < self._config.confirm_n:
                reason_codes.append("HOLD_CONFIRMING")
            elif leader_asset == current_asset:
                reason_codes.append("HOLD_CONFIRMING")
            else:
                state = "READY"
                next_action = "SWITCH"

        if next_action == "SWITCH" and leader_asset:
            self._execute_switch(leader_asset, snapshot.prices, edge_pct, net_edge_pct)
            reason_codes = ["SWITCH"]
            state = "SWITCHING"

        equity = self._broker.equity_usdt(snapshot.prices)
        self._storage.append_equity(now, self._broker.current_asset, equity)

        leaderboard = self._build_leaderboard(scores, current_score)
        if next_action != "SWITCH":
            self._logger.info(
                "DECISION HOLD=%s leader=%s edge=%.4f net_edge=%.4f",
                ",".join(reason_codes) if reason_codes else "HOLD",
                leader_asset,
                edge_pct or 0.0,
                net_edge_pct or 0.0,
            )

        return DecisionSnapshot(
            mode="PAPER",
            connection=connection,
            last_update=now,
            current_asset=self._broker.current_asset,
            equity_usdt=equity,
            state=state,
            leader=leader_asset,
            edge_pct=edge_pct,
            cost_bps=cost_bps,
            net_edge_pct=net_edge_pct,
            confirm=f"{self._confirm_count}/{self._config.confirm_n}",
            next_action=next_action,
            reason_codes=reason_codes,
            leaderboard=leaderboard,
        )

    def _build_leaderboard(self, scores: List[ScoreRow], current_score: Optional[float]) -> List[LeaderboardRow]:
        cost_bps = self._cost_model.switch_cost_bps()
        sorted_scores = sorted(scores, key=lambda row: row.score or -999, reverse=True)
        rows: List[LeaderboardRow] = []
        for idx, row in enumerate(sorted_scores, start=1):
            edge_bps = None
            net_edge_bps = None
            if row.score is not None:
                base = current_score or 0.0
                edge = row.score - base
                edge_bps = edge * 10000
                net_edge_bps = edge_bps - cost_bps
            rows.append(
                LeaderboardRow(
                    rank=idx,
                    asset=row.asset,
                    score=row.score,
                    ret_15m=row.ret_15m,
                    ret_1h=row.ret_1h,
                    ret_4h=row.ret_4h,
                    edge_bps=edge_bps,
                    cost_bps=cost_bps,
                    net_edge_bps=net_edge_bps,
                    confirm=f"{self._confirm_count}/{self._config.confirm_n}"
                    if row.asset == self._last_leader
                    else "0/0",
                    signal="LEADER" if row.asset == self._last_leader else "",
                )
            )
        return rows

    def _data_stale(self, now: float) -> bool:
        if self._last_update is None:
            return False
        return (now - self._last_update) > self._config.data_stale_sec

    def _update_confirmation(self, leader: Optional[str]) -> None:
        if leader and leader == self._last_leader:
            self._confirm_count += 1
        else:
            self._confirm_count = 1 if leader else 0
            self._last_leader = leader

    def _reset_daily_switch_count(self, now: float) -> None:
        today = dt.datetime.fromtimestamp(now).date()
        if self._switch_count_date != today:
            self._switch_count_date = today
            self._switch_count_day = 0

    def _switch_limit_reached(self) -> bool:
        return self._switch_count_day >= self._config.max_switches_per_day

    def _min_hold_active(self, now: float) -> bool:
        if self._last_switch_time is None:
            return False
        return (now - self._last_switch_time) < self._config.min_hold_sec

    def _cooldown_active(self, now: float) -> bool:
        if self._cooldown_until is None:
            return False
        return now < self._cooldown_until

    def _can_switch(self, now: float) -> bool:
        return not (self._min_hold_active(now) or self._cooldown_active(now) or self._switch_limit_reached())

    def _execute_switch(
        self,
        leader_asset: str,
        prices: Dict[str, float],
        edge_pct: Optional[float],
        net_edge_pct: Optional[float],
    ) -> None:
        previous = self._broker.current_asset
        self._broker.switch_asset(leader_asset, prices, self._cost_model.per_trade_bps)
        self._last_switch_time = time.time()
        self._cooldown_until = self._last_switch_time + self._config.cooldown_sec
        self._switch_count_day += 1
        equity = self._broker.equity_usdt(prices)
        self._storage.append_switch(
            timestamp=self._last_switch_time,
            from_asset=previous,
            to_asset=leader_asset,
            reason="SWITCH",
            equity_usdt=equity,
            edge_pct=edge_pct,
            net_edge_pct=net_edge_pct,
        )
        self._logger.info(
            "DECISION SWITCH %s->%s edge=%.4f net_edge=%.4f equity=%.2f",
            previous,
            leader_asset,
            edge_pct or 0.0,
            net_edge_pct or 0.0,
            equity,
        )

    def park_to_usdt(self, prices: Dict[str, float]) -> None:
        self._broker.park_usdt(prices, self._cost_model.per_trade_bps)
        self._logger.info("Parked to USDT")

    def current_equity(self, prices: Dict[str, float]) -> float:
        return self._broker.equity_usdt(prices)

    def log_startup_history(self) -> None:
        equities = self._storage.load_equity()
        switches = self._storage.load_switches()
        if equities:
            latest = equities[0]
            self._logger.info(
                "Loaded equity history rows=%s latest_asset=%s latest_equity=%.2f",
                len(equities),
                latest[1],
                latest[2],
            )
        if switches:
            latest_switch = switches[0]
            self._logger.info(
                "Loaded switch history rows=%s latest_switch=%s->%s",
                len(switches),
                latest_switch.from_asset,
                latest_switch.to_asset,
            )
