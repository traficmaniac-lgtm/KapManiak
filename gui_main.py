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
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from config import (
    DB_PATH,
    REPORT_DIR,
    DEFAULT_CONFIG,
    START_ASSET,
    START_EQUITY_USDT,
)
from data_provider import BinanceDataProvider
from decision_engine import DecisionEngine, DecisionState
from paper_portfolio import PaperPortfolio
from reporting import export_report
from score_engine import apply_costs, compute_scores
from storage_sqlite import SQLiteStorage, ensure_db_path
from universe import UniverseManager, normalize_symbols


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("KapManiak v0.1.3")

        self.current_asset = START_ASSET
        self.portfolio = PaperPortfolio.from_start(START_ASSET, START_EQUITY_USDT)

        self.data_provider = BinanceDataProvider()
        self.universe_manager = UniverseManager(session=self.data_provider.session)
        self.universe = normalize_symbols(self.universe_manager.get_universe())
        self.decision_engine = DecisionEngine(DecisionState(current_asset=self.current_asset))
        self.storage = SQLiteStorage(ensure_db_path(DB_PATH))
        self.storage.init_db()

        self._build_ui()
        self._update_paper_stats()
        self._setup_timer()

    def _build_ui(self) -> None:
        container = QWidget()
        main_layout = QVBoxLayout(container)

        header_layout = QGridLayout()
        self.mode_label = QLabel("Mode: PAPER")
        self.connection_label = QLabel("Connection: OFF")
        self.asset_label = QLabel("")
        self.equity_label = QLabel("")
        self._update_portfolio_labels()

        header_layout.addWidget(self.mode_label, 0, 0)
        header_layout.addWidget(self.connection_label, 0, 1)
        header_layout.addWidget(self.asset_label, 0, 2)
        header_layout.addWidget(self.equity_label, 0, 3)
        header_layout.addWidget(QLabel(f"DB: {DB_PATH}"), 1, 0)
        header_layout.addWidget(QLabel(f"Reports: {REPORT_DIR}"), 1, 1)

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

        prices_now = {
            symbol: float(payload["price_now"])
            for symbol, payload in price_snapshot.items()
            if payload.get("price_now") is not None
        }
        if not prices_now:
            self._log("WARN", "DATA_UPDATE", "No price data available for universe")
            return

        ts_ms = int(now.timestamp() * 1000)
        self.storage.insert_tick(ts_ms, prices_now, data_age_sec)

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
        self.storage.insert_decision(
            ts_ms=ts_ms,
            current_asset=self.current_asset,
            leader_asset=leader,
            decision=self._map_decision_state(decision.state),
            reasons=decision.block_reasons,
            edge_pct=decision.edge_pct,
            net_edge_pct=decision.net_edge_pct,
            cost_pct=decision.cost_pct,
            confirm_k=decision.confirm_k,
            confirm_n=decision.confirm_n,
        )
        self._log("INFO", "DATA_UPDATE", f"Updated {len(df)} assets")
        self._log("INFO", "SCORE_UPDATE", f"Leader {leader} score {leader_row['score']:.4f}")
        reasons = ",".join(decision.block_reasons) if decision.block_reasons else "NONE"
        self._log("INFO", "DECISION", f"{decision.state} | {reasons}")

        trade_details = None
        if decision.state == "READY_TO_SWITCH":
            try:
                trade_details = self.portfolio.simulate_switch_via_usdt(
                    leader,
                    prices_now,
                    DEFAULT_CONFIG.cost_bps,
                    now=now,
                )
            except KeyError as exc:
                self._log("WARN", "SWITCH_SIM", f"Missing price for {exc}")
            else:
                self.current_asset = self.portfolio.asset
                self.decision_engine.state.current_asset = self.current_asset
                self.decision_engine.state.last_switch_ts = now
                self.decision_engine.state.switches_today_count += 1
                self._log(
                    "INFO",
                    "SWITCH_SIM",
                    f"{trade_details['from_asset']} -> {trade_details['to_asset']}, "
                    f"equity {trade_details['v_before']:.2f} -> {trade_details['v_after']:.2f} USDT",
                )

        if trade_details and trade_details.get("status") == "SWITCHED":
            self.storage.insert_trade_sim(
                ts_ms=ts_ms,
                from_asset=str(trade_details["from_asset"]),
                to_asset=str(trade_details["to_asset"]),
                v_before_usdt=float(trade_details["v_before"]),
                v_after_usdt=float(trade_details["v_after"]),
                cost_paid_usdt=float(trade_details["cost_paid"]),
                px_used=None if trade_details["px_used"] is None else float(trade_details["px_used"]),
            )
            self._update_decision_card(decision)

        try:
            equity = self.portfolio.update_equity(prices_now)
        except KeyError as exc:
            self._log("WARN", "EQUITY_UPDATE", f"Missing price for {exc}")
            return

        self.storage.insert_equity_curve(
            ts_ms=ts_ms,
            equity_usdt=equity,
            asset=self.portfolio.asset,
            qty=self.portfolio.qty,
        )
        self._update_portfolio_labels()
        self._update_paper_stats()

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

    def _update_portfolio_labels(self) -> None:
        equity = self.portfolio.equity_usdt
        qty_precision = 2 if self.portfolio.asset == "USDT" else 6
        qty_text = f"{self.portfolio.qty:.{qty_precision}f}"
        self.asset_label.setText(
            f"Portfolio: {self.portfolio.asset} {qty_text} (≈ {equity:.2f} USDT)"
        )
        self.equity_label.setText(f"Equity: ${equity:.2f}")

    def _update_paper_stats(self) -> None:
        pnl_usdt = self.portfolio.equity_usdt - self.portfolio.start_equity_usdt
        pnl_pct = (
            pnl_usdt / self.portfolio.start_equity_usdt * 100
            if self.portfolio.start_equity_usdt
            else 0.0
        )
        switches_today = self.decision_engine.state.switches_today_count
        self.paper_switches_value.setText(f"{switches_today}/{self.portfolio.switches_count}")
        self.paper_costs_value.setText(f"{self.portfolio.total_cost_paid_usdt:.4f} USDT")
        self.paper_pnl_value.setText(f"{pnl_usdt:.2f} USDT ({pnl_pct:.2f}%)")

    @staticmethod
    def _map_decision_state(state: str) -> str:
        if state == "READY_TO_SWITCH":
            return "READY"
        if state == "SAFE_MODE":
            return "SAFE_MODE"
        return "HOLD"

    def _export_report(self) -> None:
        summary = export_report(DB_PATH, REPORT_DIR, self.portfolio.start_equity_usdt)
        self._log(
            "INFO",
            "REPORT_EXPORT",
            f"Exported report to {REPORT_DIR} (PnL {summary['pnl_usdt']:.2f} USDT)",
        )

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

        stats_title = QLabel("Paper Stats")
        stats_title.setStyleSheet("font-weight: bold;")
        card_layout.addWidget(stats_title)

        stats_grid = QGridLayout()
        self.paper_switches_value = QLabel("-")
        self.paper_costs_value = QLabel("-")
        self.paper_pnl_value = QLabel("-")

        stats_grid.addWidget(QLabel("Switches (today/total):"), 0, 0)
        stats_grid.addWidget(self.paper_switches_value, 0, 1)
        stats_grid.addWidget(QLabel("Total costs paid:"), 1, 0)
        stats_grid.addWidget(self.paper_costs_value, 1, 1)
        stats_grid.addWidget(QLabel("PnL:"), 2, 0)
        stats_grid.addWidget(self.paper_pnl_value, 2, 1)

        card_layout.addLayout(stats_grid)

        self.export_button = QPushButton("Export Report")
        self.export_button.clicked.connect(self._export_report)
        card_layout.addWidget(self.export_button)

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
        switches_today = self.decision_engine.state.switches_today_count
        self.switches_value.setText(f"{switches_today}/{DEFAULT_CONFIG.max_switches_day}")

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt naming
        self.storage.close()
        super().closeEvent(event)


def run_app() -> None:
    app = QApplication([])
    window = MainWindow()
    window.resize(1100, 700)
    window.show()
    app.exec()
