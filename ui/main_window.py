from __future__ import annotations

import datetime as dt
from dataclasses import replace
from typing import List, Optional

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QDoubleSpinBox,
    QStatusBar,
    QTableView,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from config import AppConfig
from engine.decision_engine import DecisionEngine, DecisionSnapshot
from engine.logger import LogEmitter


class DataWorker(QThread):
    prices_ready = Signal(object)
    error = Signal(str)

    def __init__(self, decision_engine: DecisionEngine) -> None:
        super().__init__()
        self._decision_engine = decision_engine
        self._running = False
        self._paused = False

    def run(self) -> None:
        self._running = True
        while self._running:
            if self._paused:
                self.msleep(250)
                continue
            try:
                snapshot = self._decision_engine.fetch_prices()
                self.prices_ready.emit(snapshot)
            except Exception as exc:  # noqa: BLE001 - broad catch to keep thread alive
                self.error.emit(str(exc))
            interval_ms = self._decision_engine.config.update_interval_sec * 1000
            self.msleep(interval_ms)

    def stop(self) -> None:
        self._running = False

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False


class SettingsDialog(QDialog):
    def __init__(self, config: AppConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self._config = config

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.starting_balance = QDoubleSpinBox()
        self.starting_balance.setRange(100.0, 1_000_000.0)
        self.starting_balance.setValue(config.starting_balance)

        self.update_interval = QSpinBox()
        self.update_interval.setRange(5, 120)
        self.update_interval.setValue(config.update_interval_sec)

        self.edge_threshold = QDoubleSpinBox()
        self.edge_threshold.setDecimals(3)
        self.edge_threshold.setRange(0.1, 5.0)
        self.edge_threshold.setValue(config.edge_threshold_pct)

        self.confirm_n = QSpinBox()
        self.confirm_n.setRange(1, 10)
        self.confirm_n.setValue(config.confirm_n)

        self.min_hold = QSpinBox()
        self.min_hold.setRange(60, 7200)
        self.min_hold.setValue(config.min_hold_sec)

        self.cooldown = QSpinBox()
        self.cooldown.setRange(0, 1800)
        self.cooldown.setValue(config.cooldown_sec)

        self.max_switches = QSpinBox()
        self.max_switches.setRange(1, 50)
        self.max_switches.setValue(config.max_switches_per_day)

        self.fee_bps = QDoubleSpinBox()
        self.fee_bps.setDecimals(2)
        self.fee_bps.setRange(0, 50)
        self.fee_bps.setValue(config.fee_bps)

        self.slippage_bps = QDoubleSpinBox()
        self.slippage_bps.setDecimals(2)
        self.slippage_bps.setRange(0, 50)
        self.slippage_bps.setValue(config.slippage_bps)

        self.spread_bps = QDoubleSpinBox()
        self.spread_bps.setDecimals(2)
        self.spread_bps.setRange(0, 50)
        self.spread_bps.setValue(config.spread_bps_buffer)

        self.net_edge_gate = QComboBox()
        self.net_edge_gate.addItems(["ON", "OFF"])
        self.net_edge_gate.setCurrentIndex(0 if config.net_edge_gate_enabled else 1)

        self.net_edge_min = QDoubleSpinBox()
        self.net_edge_min.setDecimals(3)
        self.net_edge_min.setRange(0.1, 5.0)
        self.net_edge_min.setValue(config.net_edge_min_pct)

        self.universe_edit = QLineEdit(", ".join(config.universe))

        form.addRow("Starting balance (USDT)", self.starting_balance)
        form.addRow("Update interval (sec)", self.update_interval)
        form.addRow("Edge threshold (%)", self.edge_threshold)
        form.addRow("Confirm N", self.confirm_n)
        form.addRow("Min hold (sec)", self.min_hold)
        form.addRow("Cooldown (sec)", self.cooldown)
        form.addRow("Max switches/day", self.max_switches)
        form.addRow("Fee (bps)", self.fee_bps)
        form.addRow("Slippage (bps)", self.slippage_bps)
        form.addRow("Spread buffer (bps)", self.spread_bps)
        form.addRow("Net edge gate", self.net_edge_gate)
        form.addRow("Net edge min (%)", self.net_edge_min)
        form.addRow("Universe (comma-separated)", self.universe_edit)

        layout.addLayout(form)

        buttons = QHBoxLayout()
        save_btn = QPushButton("Save")
        cancel_btn = QPushButton("Cancel")
        save_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(save_btn)
        buttons.addWidget(cancel_btn)
        layout.addLayout(buttons)

    def updated_config(self) -> AppConfig:
        universe = [asset.strip().upper() for asset in self.universe_edit.text().split(",") if asset.strip()]
        return replace(
            self._config,
            starting_balance=self.starting_balance.value(),
            update_interval_sec=self.update_interval.value(),
            edge_threshold_pct=self.edge_threshold.value(),
            confirm_n=self.confirm_n.value(),
            min_hold_sec=self.min_hold.value(),
            cooldown_sec=self.cooldown.value(),
            max_switches_per_day=self.max_switches.value(),
            fee_bps=self.fee_bps.value(),
            slippage_bps=self.slippage_bps.value(),
            spread_bps_buffer=self.spread_bps.value(),
            net_edge_gate_enabled=self.net_edge_gate.currentText() == "ON",
            net_edge_min_pct=self.net_edge_min.value(),
            universe=universe,
        )


class MainWindow(QMainWindow):
    def __init__(
        self,
        config: AppConfig,
        decision_engine: DecisionEngine,
        log_emitter: LogEmitter,
    ) -> None:
        super().__init__()
        self.setWindowTitle("KapManiak v0.1 (PAPER)")
        self._config = config
        self._decision_engine = decision_engine
        self._log_emitter = log_emitter
        self._worker = DataWorker(decision_engine)
        self._worker.prices_ready.connect(self._on_prices)
        self._worker.error.connect(self._on_error)
        self._log_emitter.new_log.connect(self._append_log)

        self._last_snapshot = None
        self._log_lines: List[tuple[str, int]] = []
        self._max_log_lines = 500

        self._build_ui()

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override
        if self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(1000)
        event.accept()

    def _build_ui(self) -> None:
        central = QWidget()
        main_layout = QVBoxLayout(central)

        self.status_bar = QStatusBar()
        self.mode_label = QLabel("Mode: PAPER")
        self.conn_label = QLabel("Connection: DEGRADED")
        self.last_update_label = QLabel("Last update: --")
        self.asset_label = QLabel("Current asset: USDT")
        self.equity_label = QLabel("Equity: 0.00 USDT")
        self.state_label = QLabel("State: SAFE")

        for label in [
            self.mode_label,
            self.conn_label,
            self.last_update_label,
            self.asset_label,
            self.equity_label,
            self.state_label,
        ]:
            self.status_bar.addWidget(label)

        self.setStatusBar(self.status_bar)

        content_layout = QHBoxLayout()
        main_layout.addLayout(content_layout)

        self.table_model = QStandardItemModel(0, 11)
        self.table_model.setHorizontalHeaderLabels(
            [
                "Rank",
                "Asset",
                "Score",
                "ret_15m",
                "ret_1h",
                "ret_4h",
                "Edge vs Current (bps)",
                "Cost (bps)",
                "Net Edge (bps)",
                "Confirm",
                "Signal",
            ]
        )
        self.table_view = QTableView()
        self.table_view.setModel(self.table_model)
        self.table_view.horizontalHeader().setStretchLastSection(True)
        content_layout.addWidget(self.table_view, stretch=3)

        decision_card = QGroupBox("Decision Card")
        decision_layout = QVBoxLayout(decision_card)
        self.leader_label = QLabel("Leader: --")
        self.edge_label = QLabel("Edge: --")
        self.cost_label = QLabel("Cost: --")
        self.net_edge_label = QLabel("Net edge: --")
        self.confirm_label = QLabel("Confirm: --")
        self.next_action_label = QLabel("Next action: --")
        self.reason_label = QLabel("Reasons: --")

        for label in [
            self.leader_label,
            self.edge_label,
            self.cost_label,
            self.net_edge_label,
            self.confirm_label,
            self.next_action_label,
            self.reason_label,
        ]:
            decision_layout.addWidget(label)

        buttons_layout = QHBoxLayout()
        self.start_btn = QPushButton("Start")
        self.pause_btn = QPushButton("Pause")
        self.stop_btn = QPushButton("Stop")
        self.park_btn = QPushButton("Park to USDT")
        self.blacklist_btn = QPushButton("Blacklist leader")
        self.settings_btn = QPushButton("Settings")

        self.start_btn.clicked.connect(self._start)
        self.pause_btn.clicked.connect(self._pause)
        self.stop_btn.clicked.connect(self._stop)
        self.park_btn.clicked.connect(self._park)
        self.blacklist_btn.clicked.connect(self._blacklist_leader)
        self.settings_btn.clicked.connect(self._open_settings)

        for btn in [
            self.start_btn,
            self.pause_btn,
            self.stop_btn,
            self.park_btn,
            self.blacklist_btn,
            self.settings_btn,
        ]:
            buttons_layout.addWidget(btn)
        decision_layout.addLayout(buttons_layout)
        content_layout.addWidget(decision_card, stretch=1)

        log_box = QGroupBox("Logs")
        log_layout = QVBoxLayout(log_box)
        self.log_filter = QComboBox()
        self.log_filter.addItems(["ALL", "INFO", "WARNING", "ERROR"])
        self.log_filter.currentTextChanged.connect(self._refresh_logs)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_filter)
        log_layout.addWidget(self.log_text)
        main_layout.addWidget(log_box, stretch=1)

        self.setCentralWidget(central)

    def _start(self) -> None:
        if not self._worker.isRunning():
            self._worker.start()
        else:
            self._worker.resume()

    def _pause(self) -> None:
        self._worker.pause()

    def _stop(self) -> None:
        self._worker.stop()

    def _park(self) -> None:
        if self._last_snapshot is None:
            QMessageBox.warning(self, "No data", "No price snapshot available yet.")
            return
        self._decision_engine.park_to_usdt(self._last_snapshot.prices)

    def _blacklist_leader(self) -> None:
        leader_text = self.leader_label.text().replace("Leader: ", "").strip()
        if leader_text and leader_text != "--":
            self._decision_engine.blacklist_asset(leader_text)

    def _open_settings(self) -> None:
        dialog = SettingsDialog(self._config, self)
        if dialog.exec() == QDialog.Accepted:
            self._config = dialog.updated_config()
            self._decision_engine.update_config(self._config)

    def _on_prices(self, snapshot) -> None:
        self._last_snapshot = snapshot
        decision = self._decision_engine.process_prices(snapshot)
        self._update_ui(decision)

    def _on_error(self, message: str) -> None:
        self.conn_label.setText("Connection: DEGRADED")
        self._append_log(f"{dt.datetime.now():%Y-%m-%d %H:%M:%S} | ERROR | {message}", 40)

    def _update_ui(self, decision: DecisionSnapshot) -> None:
        self.mode_label.setText(f"Mode: {decision.mode}")
        self.conn_label.setText(f"Connection: {decision.connection}")
        self.last_update_label.setText(f"Last update: {dt.datetime.fromtimestamp(decision.last_update):%H:%M:%S}")
        self.asset_label.setText(f"Current asset: {decision.current_asset}")
        self.equity_label.setText(f"Equity: {decision.equity_usdt:,.2f} USDT")
        self.state_label.setText(f"State: {decision.state}")

        self.leader_label.setText(f"Leader: {decision.leader or '--'}")
        self.edge_label.setText(
            f"Edge: {decision.edge_pct * 100:.3f}%"
            if decision.edge_pct is not None
            else "Edge: --"
        )
        self.cost_label.setText(f"Cost: {decision.cost_bps:.2f} bps")
        self.net_edge_label.setText(
            f"Net edge: {decision.net_edge_pct * 100:.3f}%"
            if decision.net_edge_pct is not None
            else "Net edge: --"
        )
        self.confirm_label.setText(f"Confirm: {decision.confirm}")
        self.next_action_label.setText(f"Next action: {decision.next_action}")
        self.reason_label.setText(f"Reasons: {', '.join(decision.reason_codes) or '--'}")

        self._refresh_table(decision.leaderboard)

    def _refresh_table(self, rows) -> None:
        self.table_model.setRowCount(0)
        for row in rows:
            items = [
                QStandardItem(str(row.rank)),
                QStandardItem(row.asset),
                QStandardItem(self._fmt_pct(row.score)),
                QStandardItem(self._fmt_pct(row.ret_15m)),
                QStandardItem(self._fmt_pct(row.ret_1h)),
                QStandardItem(self._fmt_pct(row.ret_4h)),
                QStandardItem(self._fmt_bps(row.edge_bps)),
                QStandardItem(f"{row.cost_bps:.2f}"),
                QStandardItem(self._fmt_bps(row.net_edge_bps)),
                QStandardItem(row.confirm),
                QStandardItem(row.signal),
            ]
            for item in items:
                item.setTextAlignment(Qt.AlignCenter)
            self.table_model.appendRow(items)

    def _fmt_pct(self, value: Optional[float]) -> str:
        if value is None:
            return "--"
        return f"{value * 100:.3f}%"

    def _fmt_bps(self, value: Optional[float]) -> str:
        if value is None:
            return "--"
        return f"{value:.2f}"

    def _append_log(self, message: str, level: int) -> None:
        self._log_lines.append((message, level))
        self._log_lines = self._log_lines[-self._max_log_lines :]
        self._refresh_logs()

    def _refresh_logs(self) -> None:
        level_filter = self.log_filter.currentText()
        level_map = {"INFO": 20, "WARNING": 30, "ERROR": 40}
        lines = []
        for message, level in self._log_lines:
            if level_filter == "ALL" or level >= level_map.get(level_filter, 0):
                lines.append(message)
        self.log_text.setPlainText("\n".join(lines))
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())
