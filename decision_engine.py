from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from config import DEFAULT_CONFIG


@dataclass
class DecisionState:
    current_asset: str = "USDT"
    last_switch_ts: datetime | None = None
    switches_today_count: int = 0
    switches_today_date: str = ""
    leader_streak_asset: str | None = None
    leader_streak_count: int = 0
    last_decision_ts: datetime | None = None
    data_age_sec: float | None = None


@dataclass
class DecisionOutput:
    state: str
    leader_asset: str
    edge_pct: float
    net_edge_pct: float
    cost_pct: float
    confirm_k: int
    confirm_n: int
    block_reasons: list[str] = field(default_factory=list)
    min_hold_left_sec: float = 0.0
    cooldown_left_sec: float = 0.0
    data_age_sec: float | None = None
    switches_today_count: int = 0


class DecisionEngine:
    def __init__(self, state: DecisionState | None = None) -> None:
        self.state = state or DecisionState()

    def evaluate(
        self,
        leader_asset: str,
        edge_pct: float,
        net_edge_pct: float,
        cost_pct: float,
        data_age_sec: float | None,
        now: datetime | None = None,
        current_asset: str | None = None,
    ) -> DecisionOutput:
        now = now or datetime.utcnow()
        self.state.last_decision_ts = now
        if current_asset is not None:
            self.state.current_asset = current_asset
        self.state.data_age_sec = data_age_sec
        self._update_daily_switches(now)
        self._update_leader_streak(leader_asset)

        min_hold_left_sec = self._remaining_hold_sec(now, DEFAULT_CONFIG.min_hold_sec)
        cooldown_left_sec = self._remaining_hold_sec(now, DEFAULT_CONFIG.cooldown_sec)

        if data_age_sec is None or data_age_sec > DEFAULT_CONFIG.data_stale_sec:
            return DecisionOutput(
                state="SAFE_MODE",
                leader_asset=leader_asset,
                edge_pct=edge_pct,
                net_edge_pct=net_edge_pct,
                cost_pct=cost_pct,
                confirm_k=self.state.leader_streak_count,
                confirm_n=DEFAULT_CONFIG.confirm_n,
                block_reasons=["DATA_STALE"],
                min_hold_left_sec=min_hold_left_sec,
                cooldown_left_sec=cooldown_left_sec,
                data_age_sec=data_age_sec,
                switches_today_count=self.state.switches_today_count,
            )

        if self.state.switches_today_count >= DEFAULT_CONFIG.max_switches_day:
            return self._blocked_output(
                leader_asset,
                edge_pct,
                net_edge_pct,
                cost_pct,
                "MAX_SWITCHES_DAY",
                min_hold_left_sec,
                cooldown_left_sec,
                data_age_sec,
            )

        if self._should_hold(min_hold_left_sec):
            return self._blocked_output(
                leader_asset,
                edge_pct,
                net_edge_pct,
                cost_pct,
                "MIN_HOLD",
                min_hold_left_sec,
                cooldown_left_sec,
                data_age_sec,
            )

        if self._should_hold(cooldown_left_sec):
            return self._blocked_output(
                leader_asset,
                edge_pct,
                net_edge_pct,
                cost_pct,
                "COOLDOWN",
                min_hold_left_sec,
                cooldown_left_sec,
                data_age_sec,
            )

        if leader_asset == self.state.current_asset:
            return DecisionOutput(
                state="HOLD",
                leader_asset=leader_asset,
                edge_pct=edge_pct,
                net_edge_pct=net_edge_pct,
                cost_pct=cost_pct,
                confirm_k=self.state.leader_streak_count,
                confirm_n=DEFAULT_CONFIG.confirm_n,
                block_reasons=["LEADER_IS_CURRENT"],
                min_hold_left_sec=min_hold_left_sec,
                cooldown_left_sec=cooldown_left_sec,
                data_age_sec=data_age_sec,
                switches_today_count=self.state.switches_today_count,
            )

        if edge_pct < DEFAULT_CONFIG.edge_threshold:
            return self._blocked_output(
                leader_asset,
                edge_pct,
                net_edge_pct,
                cost_pct,
                "EDGE_TOO_SMALL",
                min_hold_left_sec,
                cooldown_left_sec,
                data_age_sec,
            )

        if net_edge_pct < DEFAULT_CONFIG.net_edge_min:
            return self._blocked_output(
                leader_asset,
                edge_pct,
                net_edge_pct,
                cost_pct,
                "NET_EDGE_TOO_SMALL",
                min_hold_left_sec,
                cooldown_left_sec,
                data_age_sec,
            )

        if self.state.leader_streak_count < DEFAULT_CONFIG.confirm_n:
            return self._blocked_output(
                leader_asset,
                edge_pct,
                net_edge_pct,
                cost_pct,
                "CONFIRMING",
                min_hold_left_sec,
                cooldown_left_sec,
                data_age_sec,
            )

        return DecisionOutput(
            state="READY_TO_SWITCH",
            leader_asset=leader_asset,
            edge_pct=edge_pct,
            net_edge_pct=net_edge_pct,
            cost_pct=cost_pct,
            confirm_k=self.state.leader_streak_count,
            confirm_n=DEFAULT_CONFIG.confirm_n,
            block_reasons=["READY_OK"],
            min_hold_left_sec=min_hold_left_sec,
            cooldown_left_sec=cooldown_left_sec,
            data_age_sec=data_age_sec,
            switches_today_count=self.state.switches_today_count,
        )

    def _blocked_output(
        self,
        leader_asset: str,
        edge_pct: float,
        net_edge_pct: float,
        cost_pct: float,
        reason: str,
        min_hold_left_sec: float,
        cooldown_left_sec: float,
        data_age_sec: float | None,
    ) -> DecisionOutput:
        return DecisionOutput(
            state="SWITCH_BLOCKED",
            leader_asset=leader_asset,
            edge_pct=edge_pct,
            net_edge_pct=net_edge_pct,
            cost_pct=cost_pct,
            confirm_k=self.state.leader_streak_count,
            confirm_n=DEFAULT_CONFIG.confirm_n,
            block_reasons=[reason],
            min_hold_left_sec=min_hold_left_sec,
            cooldown_left_sec=cooldown_left_sec,
            data_age_sec=data_age_sec,
            switches_today_count=self.state.switches_today_count,
        )

    def _update_leader_streak(self, leader_asset: str) -> None:
        if leader_asset == self.state.leader_streak_asset:
            self.state.leader_streak_count += 1
        else:
            self.state.leader_streak_asset = leader_asset
            self.state.leader_streak_count = 1

    def _update_daily_switches(self, now: datetime) -> None:
        today = now.date().isoformat()
        if self.state.switches_today_date != today:
            self.state.switches_today_date = today
            self.state.switches_today_count = 0

    def _remaining_hold_sec(self, now: datetime, hold_sec: int) -> float:
        if self.state.last_switch_ts is None:
            return 0.0
        elapsed = (now - self.state.last_switch_ts).total_seconds()
        return max(0.0, hold_sec - elapsed)

    @staticmethod
    def _should_hold(remaining_sec: float) -> bool:
        return remaining_sec > 0
