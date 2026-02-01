from __future__ import annotations

from datetime import datetime

import pandas as pd
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QGridLayout,
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
from decision_engine import decide
from score_engine import apply_costs, compute_scores
from universe import UniverseManager, normalize_symbols


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("KapManiak v0.1.1")

        self.current_asset = "USDT"
        self.equity = 100.0

        self.data_provider = BinanceDataProvider()
        self.universe_manager = UniverseManager(session=self.data_provider.session)
        self.universe = normalize_symbols(self.universe_manager.get_universe())

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

        self.table = QTableWidget(0, 9)
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
                "Signal",
            ]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        main_layout.addWidget(self.table)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMinimumHeight(160)
        main_layout.addWidget(self.log_view)

        self.setCentralWidget(container)

    def _setup_timer(self) -> None:
        self.timer = QTimer(self)
        self.timer.setInterval(DEFAULT_CONFIG.sample_interval * 1000)
        self.timer.timeout.connect(self.refresh)
        self.timer.start()
        self.refresh()

    def refresh(self) -> None:
        price_snapshot = self.data_provider.update(self.universe)
        self.connection_label.setText(
            f"Connection: {'OK' if self.data_provider.last_connection_ok else 'OFF'}"
        )
        if not price_snapshot:
            self._log("INFO", "DATA_UPDATE", "No data available from provider")
            return

        df = compute_scores(price_snapshot)
        df = apply_costs(df, self.current_asset)
        leader = self._find_leader(df)
        leader_row = df.loc[df["asset"] == leader].iloc[0]
        decision = decide(leader, self.current_asset, leader_row["edge"], leader_row["net_edge"])

        self._update_table(df)
        self._log("INFO", "DATA_UPDATE", f"Updated {len(df)} assets")
        self._log("INFO", "SCORE_UPDATE", f"Leader {leader} score {leader_row['score']:.4f}")
        if decision.state == "READY_TO_SWITCH":
            self._log("INFO", "DECISION_READY", "Switch conditions met")
        else:
            reasons = ",".join(decision.reason_codes) if decision.reason_codes else "HOLD"
            self._log("INFO", "DECISION_HOLD", reasons)

    def _find_leader(self, df: pd.DataFrame) -> str:
        if df.empty:
            return self.current_asset
        return str(df.iloc[0]["asset"])

    def _update_table(self, df: pd.DataFrame) -> None:
        self.table.setRowCount(len(df))
        for row_idx, row in df.iterrows():
            asset = str(row["asset"])
            score = float(row["score"])
            ret_15m = float(row["ret_15m"])
            ret_1h = float(row["ret_1h"])
            ret_4h = float(row["ret_4h"])
            edge = float(row["edge"])
            cost = float(row["cost"])
            net_edge = float(row["net_edge"])

            signal = "OK" if edge >= DEFAULT_CONFIG.edge_threshold and net_edge >= DEFAULT_CONFIG.net_edge_min else "TOO_SMALL"

            values = [
                asset,
                f"{score * 100:.2f}%",
                f"{ret_15m * 100:.2f}%",
                f"{ret_1h * 100:.2f}%",
                f"{ret_4h * 100:.2f}%",
                f"{edge * 100:.2f}%",
                f"{cost * 100:.2f}%",
                f"{net_edge * 100:.2f}%",
                signal,
            ]

            for col_idx, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col_idx > 0:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(row_idx, col_idx, item)

    def _log(self, level: str, code: str, message: str) -> None:
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        self.log_view.append(f"{timestamp} | {level} | {code} | {message}")


def run_app() -> None:
    app = QApplication([])
    window = MainWindow()
    window.resize(1100, 700)
    window.show()
    app.exec()
