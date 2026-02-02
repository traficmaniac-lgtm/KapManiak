from __future__ import annotations

import csv
from dataclasses import asdict
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QHeaderView,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.calc import ItemResult, Params, calc_item_forward, calc_item_inverse, calc_summary
from src.services.rate_service import fetch_rate
from src.services.storage import Storage, hydrate_goods, serialize_goods
from src.widgets.goods_panel import GoodsPanel
from src.widgets.metric_card import MetricCard
from src.widgets.params_panel import ParamsPanel

APP_QSS = """
* {
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 12.5pt;
}
QMainWindow {
    background-color: #111418;
    color: #e6e6e6;
}
QGroupBox {
    border: 1px solid #262b33;
    border-radius: 10px;
    margin-top: 12px;
    padding: 10px;
    background-color: #161a20;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
    color: #cfd6df;
}
QLineEdit, QComboBox {
    background-color: #0f1216;
    border: 1px solid #303744;
    border-radius: 6px;
    padding: 6px 8px;
    color: #e6e6e6;
    min-height: 26px;
}
QPushButton {
    background-color: #2d6cdf;
    border: none;
    border-radius: 6px;
    padding: 6px 12px;
    color: #ffffff;
}
QPushButton:hover { background-color: #3a7bff; }
QPushButton:disabled { background-color: #3a3f48; color: #9aa3ad; }
QTableWidget {
    background-color: #141821;
    border: 1px solid #262b33;
    gridline-color: #262b33;
    color: #e6e6e6;
}
QHeaderView::section {
    background-color: #1b2028;
    padding: 6px;
    border: 1px solid #262b33;
    color: #cfd6df;
}
#MetricValue {
    font-size: 18pt;
    font-weight: 600;
    color: #ffffff;
}
#MetricTitle {
    font-size: 10.5pt;
    color: #9aa3ad;
}
#HintLabel {
    color: #ffb5b5;
    font-size: 10.5pt;
}
#StatusBadge {
    padding: 4px 10px;
    border-radius: 10px;
    background-color: #26303c;
}
"""


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("KapManiak — L2 Trade Helper")
        self.resize(1200, 760)

        self.storage = Storage()
        self.params = self.storage.load_params()
        self.goods_rows: List[dict] = hydrate_goods(self.storage.load_goods())

        self._build_ui()
        self._load_params_to_ui()
        self._refresh_metrics()
        self._populate_table()
        self._update_add_hint("")

        self.rate_timer = QTimer(self)
        self.rate_timer.setInterval(10 * 60 * 1000)
        self.rate_timer.timeout.connect(self.update_rate)
        self.rate_timer.start()

        self.update_rate()

    def _build_ui(self) -> None:
        central = QWidget()
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        top_bar = self._build_top_bar()
        main_layout.addWidget(top_bar)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)

        self.params_panel = ParamsPanel()
        self.params_panel.bind(self._on_params_changed)

        self.metrics_widget = self._build_metrics()
        self.goods_panel = GoodsPanel()
        self.goods_panel.mode_combo.currentIndexChanged.connect(self.goods_panel.set_mode_label)
        self.goods_panel.set_mode_label()
        self.goods_panel.bind_add(self.add_goods)
        self.goods_panel.bind_remove(self.remove_selected)
        self.goods_panel.bind_clear(self.clear_goods)
        self.goods_panel.bind_export(self.export_csv)

        left_layout.addWidget(self.params_panel)
        left_layout.addWidget(self.metrics_widget)
        left_layout.addWidget(self.goods_panel)
        left_layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setWidget(left_container)

        self.table = self._build_table()

        splitter.addWidget(scroll)
        splitter.addWidget(self.table)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        main_layout.addWidget(splitter)
        self.setCentralWidget(central)

    def _build_top_bar(self) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self.rate_label = QLabel("Курс USDT: —")
        self.rate_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.status_badge = QLabel("OFFLINE")
        self.status_badge.setObjectName("StatusBadge")
        self.status_badge.setAlignment(Qt.AlignCenter)

        refresh = QPushButton("↻ Обновить")
        refresh.clicked.connect(self.update_rate)

        layout.addWidget(self.rate_label)
        layout.addWidget(self.status_badge)
        layout.addStretch(1)
        layout.addWidget(refresh)
        return container

    def _build_metrics(self) -> QWidget:
        container = QWidget()
        grid = QGridLayout(container)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(12)

        self.metric_cards = {
            "donate_rub": MetricCard("Стоимость доната"),
            "adena_kk": MetricCard("Получено адены (кк)"),
            "sum_fp_buyer_rub": MetricCard("FP ₽ покупателя"),
            "sum_fp_you_rub": MetricCard("FP ₽ мне"),
            "sum_fp_you_usdt": MetricCard("USDT на вывод"),
            "profit_rub": MetricCard("Профит ₽"),
            "profit_usdt": MetricCard("Профит USDT"),
        }

        positions = [
            (0, 0, "donate_rub"),
            (0, 1, "adena_kk"),
            (1, 0, "sum_fp_buyer_rub"),
            (1, 1, "sum_fp_you_rub"),
            (2, 0, "sum_fp_you_usdt"),
            (2, 1, "profit_rub"),
            (3, 0, "profit_usdt"),
        ]

        for row, col, key in positions:
            grid.addWidget(self.metric_cards[key], row, col)

        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        return container

    def _build_table(self) -> QTableWidget:
        headers = [
            "Товар",
            "Монеты",
            "Донат ₽",
            "Адена (кк)",
            "FP ₽ (покуп.)",
            "FP ₽ (мне)",
            "USDT (вывод)",
            "Профит ₽",
            "Профит USDT",
        ]
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.SingleSelection)
        table.horizontalHeader().setStretchLastSection(False)
        table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setHorizontalScrollMode(QTableWidget.ScrollPerPixel)

        column_widths = [240, 110, 110, 110, 120, 110, 120, 110, 120]
        for index, width in enumerate(column_widths):
            table.setColumnWidth(index, width)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        return table

    def _load_params_to_ui(self) -> None:
        self.params_panel.set_values(asdict(self.params))

    def _on_params_changed(self) -> None:
        values = self.params_panel.values()
        fee_fp = values.get("fee_fp")
        fee_withdraw = values.get("fee_withdraw")
        self.params = Params(
            coin_per_1kkA=values.get("coin_per_1kkA"),
            fp_buyer_rub_per_1kkA=values.get("fp_buyer_rub_per_1kkA"),
            fee_fp=fee_fp if fee_fp is not None else 0.15,
            fee_withdraw=fee_withdraw if fee_withdraw is not None else 0.21,
            coins_in=values.get("coins_in"),
            rub_per_usdt=self.params.rub_per_usdt,
        )
        self.storage.save_params(self.params)
        self._refresh_metrics()
        self._recalc_goods()

    def _refresh_metrics(self) -> None:
        result = calc_summary(self.params)
        self.metric_cards["donate_rub"].set_value(_fmt_rub(result.donate_rub))
        self.metric_cards["adena_kk"].set_value(_fmt_number(result.adena_kk))
        self.metric_cards["sum_fp_buyer_rub"].set_value(_fmt_rub(result.sum_fp_buyer_rub))
        self.metric_cards["sum_fp_you_rub"].set_value(_fmt_rub(result.sum_fp_you_rub))
        self.metric_cards["sum_fp_you_usdt"].set_value(_fmt_usdt(result.sum_fp_you_usdt))
        self.metric_cards["profit_rub"].set_value(_fmt_rub(result.profit_rub))
        self.metric_cards["profit_usdt"].set_value(_fmt_usdt(result.profit_usdt))

    def _recalc_goods(self) -> None:
        updated: List[dict] = []
        for row in self.goods_rows:
            mode = row.get("mode", 0)
            value = row.get("value")
            if value is None:
                continue
            calc = self._calc_goods(mode, value)
            if calc is None:
                continue
            updated.append({"name": row.get("name", "Без названия"), "mode": mode, "value": value, "calc": calc})
        self.goods_rows = updated
        self._populate_table()
        self._persist_goods()

    def _calc_goods(self, mode: int, value: float) -> Optional[ItemResult]:
        if mode == 0:
            return calc_item_forward(self.params, value)
        return calc_item_inverse(self.params, value)

    def add_goods(self) -> None:
        payload = self.goods_panel.payload()
        if payload["value"] is None:
            self._update_add_hint("Введите значение товара.")
            return
        if self.params.coin_per_1kkA is None or self.params.fp_buyer_rub_per_1kkA is None:
            self._update_add_hint("Заполните параметры: монет за 1кк и FP ₽.")
            return
        if self.params.rub_per_usdt is None:
            self._update_add_hint("Нет курса USDT. Обновите курс.")
            return

        calc = self._calc_goods(payload["mode"], payload["value"])
        if calc is None:
            self._update_add_hint("Недостаточно данных для расчёта.")
            return

        self.goods_rows.append({"name": payload["name"], "mode": payload["mode"], "value": payload["value"], "calc": calc})
        self._populate_table()
        self._persist_goods()
        self._update_add_hint("")

    def remove_selected(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        row_index = rows[0].row()
        if 0 <= row_index < len(self.goods_rows):
            del self.goods_rows[row_index]
            self._populate_table()
            self._persist_goods()

    def clear_goods(self) -> None:
        if not self.goods_rows:
            return
        reply = QMessageBox.question(self, "Очистить", "Удалить все товары?")
        if reply == QMessageBox.StandardButton.Yes:
            self.goods_rows = []
            self._populate_table()
            self._persist_goods()

    def export_csv(self) -> None:
        if not self.goods_rows:
            self._update_add_hint("Нет данных для экспорта.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Экспорт CSV", str(Path.cwd() / "goods.csv"), "CSV (*.csv)")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle, delimiter=";")
            writer.writerow(self.table.horizontalHeaderItem(i).text() for i in range(self.table.columnCount()))
            for row in self.goods_rows:
                calc: ItemResult = row["calc"]
                writer.writerow(
                    [
                        row["name"],
                        _fmt_number(calc.item_coins),
                        _fmt_rub(calc.item_cost_rub),
                        _fmt_number(calc.item_adena_kk),
                        _fmt_rub(calc.item_fp_buyer_rub),
                        _fmt_rub(calc.item_fp_you_rub),
                        _fmt_usdt(calc.item_usdt_net),
                        _fmt_rub(calc.profit_rub),
                        _fmt_usdt(calc.profit_usdt),
                    ]
                )
        self._update_add_hint("Экспорт выполнен.")

    def _populate_table(self) -> None:
        self.table.setRowCount(len(self.goods_rows))
        for row_index, row in enumerate(self.goods_rows):
            calc: ItemResult = row["calc"]
            values = [
                row["name"],
                _fmt_number(calc.item_coins),
                _fmt_rub(calc.item_cost_rub),
                _fmt_number(calc.item_adena_kk),
                _fmt_rub(calc.item_fp_buyer_rub),
                _fmt_rub(calc.item_fp_you_rub),
                _fmt_usdt(calc.item_usdt_net),
                _fmt_rub(calc.profit_rub),
                _fmt_usdt(calc.profit_usdt),
            ]
            for col, text in enumerate(values):
                item = QTableWidgetItem(text)
                if col > 0:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(row_index, col, item)
        self.table.resizeRowsToContents()

    def _persist_goods(self) -> None:
        payload = serialize_goods(self.goods_rows)
        self.storage.save_goods(payload)

    def _update_add_hint(self, text: str) -> None:
        self.goods_panel.set_hint(text)

    def update_rate(self) -> None:
        self.status_badge.setText("UPDATING")
        self.status_badge.setStyleSheet("background-color: #3a3f48;")
        QApplication.processEvents()
        result = fetch_rate()
        if result.rate is not None:
            self.params.rub_per_usdt = result.rate
            self.storage.save_rate(result.rate, result.timestamp)
            self.status_badge.setText("OK")
            self.status_badge.setStyleSheet("background-color: #1f6f50;")
        else:
            self.status_badge.setText("OFFLINE")
            self.status_badge.setStyleSheet("background-color: #6b2b2b;")
            cached = self.storage.load_params().rub_per_usdt
            if cached:
                self.params.rub_per_usdt = cached
        self.rate_label.setText(f"Курс USDT: {_fmt_number(self.params.rub_per_usdt)} ₽")
        self._refresh_metrics()
        self._recalc_goods()


def _fmt_number(value: Optional[float]) -> str:
    if value is None:
        return "—"
    return f"{value:,.2f}".replace(",", " ")


def _fmt_rub(value: Optional[float]) -> str:
    if value is None:
        return "—"
    return f"{value:,.2f} ₽".replace(",", " ")


def _fmt_usdt(value: Optional[float]) -> str:
    if value is None:
        return "—"
    return f"{value:,.4f} USDT".replace(",", " ")
