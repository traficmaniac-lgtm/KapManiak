from __future__ import annotations

from datetime import datetime

import pandas as pd
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from config import DEFAULT_CONFIG
from data_provider import BinanceDataProvider
from decision_engine import DecisionEngine, DecisionState
from score_engine import apply_costs, compute_scores
from universe import UniverseManager, normalize_symbols


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("KapManiak v0.1.2")

        self.current_asset = "USDT"
        self.equity = 100.0

        self.data_provider = BinanceDataProvider()
        self.universe_manager = UniverseManager(session=self.data_provider.session)
        self.universe = normalize_symbols(self.universe_manager.get_universe())
        self.decision_engine = DecisionEngine(DecisionState(current_asset=self.current_asset))

        self._build_ui()
        self._setup_timer()

    def _build_ui(self) -> None:
        container = QWidget()
        main_layout = QVBoxLayout(container)

        header_layout = QGridLayout()
        self.mode_label = QLabel("Mode: PAPER")
        self.connection_label = QLabel("Connection: OFF")
        self.asset_label = QLabel(f"Current Asset: {self.current_asset}")
        self.equity_label = QLabel(f"Equity: ${self.equity:.2f}")

        header_layout.addWidget(self.mode_label, 0, 0)
        header_layout.addWidget(self.connection_label, 0, 1)
        header_layout.addWidget(self.asset_label, 0, 2)
        header_layout.addWidget(self.equity_label, 0, 3)

        main_layout.addLayout(header_layout)

        self.table = QTableWidget(0, 11)
        self.table.setHorizontalHeaderLabels(
            [
                "Asset",
                "Score",
                "ret_15m",
                "ret_1h",
                "ret_4h",
                "Edge vs Current",
                "Cost",
                "Net Edge",
                "Net Edge (bps)",
                "Confirm",
                "Signal",
            ]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        body_layout = QHBoxLayout()
        body_layout.addWidget(self.table)
        body_layout.addLayout(self._build_decision_card())
        main_layout.addLayout(body_layout)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMinimumHeight(160)
        main_layout.addWidget(self.log_view)

        self.setCentralWidget(container)

    def _setup_timer(self) -> None:
        self.timer = QTimer(self)
        self.timer.setInterval(DEFAULT_CONFIG.sample_interval_sec * 1000)
        self.timer.timeout.connect(self.refresh)
        self.timer.start()
        self.refresh()

    def refresh(self) -> None:
        now = datetime.utcnow()
        price_snapshot = self.data_provider.update(self.universe)
        data_age_sec = self.data_provider.age_sec(now)
        self.connection_label.setText(
            f"Connection: {'OK' if self.data_provider.last_connection_ok else 'OFF'}"
        )
        if not price_snapshot:
            self._log("INFO", "DATA_UPDATE", "No data available from provider")
            return

        df = compute_scores(price_snapshot)
        df = apply_costs(df, self.current_asset)
        if df.empty:
            self._log("WARN", "SCORE_UPDATE", "No valid scores computed")
            return
        self._log_missing_history(df)
        leader = self._find_leader(df)
        leader_row = df.loc[df["asset"] == leader].iloc[0]
        decision = self.decision_engine.evaluate(
            leader_asset=leader,
            edge_pct=float(leader_row["edge"]),
            net_edge_pct=float(leader_row["net_edge"]),
            cost_pct=float(leader_row["cost"]),
            data_age_sec=data_age_sec,
            now=now,
            current_asset=self.current_asset,
        )

        self._update_table(df, leader, decision)
        self._update_decision_card(decision)
        self._log("INFO", "DATA_UPDATE", f"Updated {len(df)} assets")
        self._log("INFO", "SCORE_UPDATE", f"Leader {leader} score {leader_row['score']:.4f}")
        reasons = ",".join(decision.block_reasons) if decision.block_reasons else "NONE"
        self._log("INFO", "DECISION", f"{decision.state} | {reasons}")

    def _find_leader(self, df: pd.DataFrame) -> str:
        if df.empty:
            return self.current_asset
        valid = df[df["score"].notna()]
        if valid.empty:
            if self.current_asset in df["asset"].values:
                return self.current_asset
            return str(df.iloc[0]["asset"])
        return str(valid.iloc[0]["asset"])

    def _update_table(self, df: pd.DataFrame, leader: str, decision: object) -> None:
        self.table.setRowCount(len(df))
        for row_idx, row in df.iterrows():
            asset = str(row["asset"])
            score = row["score"]
            ret_15m = row["ret_15m"]
            ret_1h = row["ret_1h"]
            ret_4h = row["ret_4h"]
            history_ok = bool(row["history_ok"])
            edge = float(row["edge"])
            cost = float(row["cost"])
            net_edge = float(row["net_edge"])
            net_edge_bps = net_edge * 10_000

            if decision.state == "SAFE_MODE":
                signal = "STALE" if asset == leader else ""
            elif not history_ok:
                signal = "STALE"
            elif asset == leader:
                signal = "OK" if decision.state == "READY_TO_SWITCH" else "BLOCKED"
            else:
                signal = ""

            confirm_text = ""
            if asset == leader:
                confirm_text = f"{decision.confirm_k}/{decision.confirm_n}"

            values = [
                asset,
                f"{score * 100:.2f}%" if pd.notna(score) else "n/a",
                f"{ret_15m * 100:.2f}%" if pd.notna(ret_15m) else "n/a",
                f"{ret_1h * 100:.2f}%" if pd.notna(ret_1h) else "n/a",
                f"{ret_4h * 100:.2f}%" if pd.notna(ret_4h) else "n/a",
                f"{edge * 100:.2f}%",
                f"{cost * 100:.2f}%",
                f"{net_edge * 100:.2f}%",
                f"{net_edge_bps:.1f}",
                confirm_text,
                signal,
            ]

            for col_idx, value in enumerate(values):
                item = QTableWidgetItem(value)
                if not history_ok:
                    item.setToolTip("NOT_ENOUGH_HISTORY")
                if col_idx > 0:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(row_idx, col_idx, item)

    def _log(self, level: str, code: str, message: str) -> None:
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        self.log_view.append(f"{timestamp} | {level} | {code} | {message}")

    def _log_missing_history(self, df: pd.DataFrame) -> None:
        missing = df.loc[~df["history_ok"], "asset"].tolist()
        if missing:
            assets = ", ".join(missing)
            self._log("WARN", "NOT_ENOUGH_HISTORY", f"Missing history for: {assets}")

    def _build_decision_card(self) -> QVBoxLayout:
        card_layout = QVBoxLayout()
        title = QLabel("Decision Card")
        title.setStyleSheet("font-weight: bold;")
        card_layout.addWidget(title)

        grid = QGridLayout()
        self.leader_value = QLabel("-")
        self.current_value = QLabel("-")
        self.edge_value = QLabel("-")
        self.confirm_value = QLabel("-")
        self.action_value = QLabel("-")
        self.reasons_value = QLabel("-")
        self.timers_value = QLabel("-")
        self.switches_value = QLabel("-")

        self.reasons_value.setWordWrap(True)

        grid.addWidget(QLabel("Leader:"), 0, 0)
        grid.addWidget(self.leader_value, 0, 1)
        grid.addWidget(QLabel("Current:"), 1, 0)
        grid.addWidget(self.current_value, 1, 1)
        grid.addWidget(QLabel("Edge / Cost / Net:"), 2, 0)
        grid.addWidget(self.edge_value, 2, 1)
        grid.addWidget(QLabel("Confirm:"), 3, 0)
        grid.addWidget(self.confirm_value, 3, 1)
        grid.addWidget(QLabel("Next action:"), 4, 0)
        grid.addWidget(self.action_value, 4, 1)
        grid.addWidget(QLabel("Reasons:"), 5, 0)
        grid.addWidget(self.reasons_value, 5, 1)
        grid.addWidget(QLabel("Timers:"), 6, 0)
        grid.addWidget(self.timers_value, 6, 1)
        grid.addWidget(QLabel("Switches today:"), 7, 0)
        grid.addWidget(self.switches_value, 7, 1)

        card_layout.addLayout(grid)
        card_layout.addStretch()
        return card_layout

    def _update_decision_card(self, decision: object) -> None:
        edge_bps = decision.edge_pct * 10_000
        cost_bps = decision.cost_pct * 10_000
        net_bps = decision.net_edge_pct * 10_000
        edge_text = (
            f"{decision.edge_pct * 100:.2f}% ({edge_bps:.1f} bps) / "
            f"{decision.cost_pct * 100:.2f}% ({cost_bps:.1f} bps) / "
            f"{decision.net_edge_pct * 100:.2f}% ({net_bps:.1f} bps)"
        )
        reasons = ", ".join(decision.block_reasons) if decision.block_reasons else "-"
        data_age = "n/a" if decision.data_age_sec is None else f"{decision.data_age_sec:.0f}s"
        timers_text = (
            f"data_age={data_age}, "
            f"min_hold_left={decision.min_hold_left_sec:.0f}s, "
            f"cooldown_left={decision.cooldown_left_sec:.0f}s"
        )

        self.leader_value.setText(decision.leader_asset)
        self.current_value.setText(self.current_asset)
        self.edge_value.setText(edge_text)
        self.confirm_value.setText(f"{decision.confirm_k}/{decision.confirm_n}")
        self.action_value.setText(decision.state)
        self.reasons_value.setText(reasons)
        self.timers_value.setText(timers_text)
        self.switches_value.setText(f"{decision.switches_today_count}/{DEFAULT_CONFIG.max_switches_day}")


def run_app() -> None:
    app = QApplication([])
    window = MainWindow()
    window.resize(1100, 700)
    window.show()
    app.exec()
