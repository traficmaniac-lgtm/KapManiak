from __future__ import annotations

from dataclasses import replace
from typing import List, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import (
    QApplication,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.calc import Settings, calc_item, calc_quick, calc_rub_per_coin_buyer
from src.core.config import GoodsItem, load_config, load_goods, new_goods_item, save_config, save_goods
from src.services.rate_service import fetch_rate
from src.ui.settings_dialog import SettingsDialog

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
    min-height: 28px;
}
QPushButton {
    background-color: #2d6cdf;
    border: none;
    border-radius: 6px;
    padding: 6px 12px;
    color: #ffffff;
    min-height: 28px;
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
#HintLabel {
    color: #ffb5b5;
    font-size: 10.5pt;
}
"""


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("KapManiak — L2 Trade Helper")
        self.resize(1200, 720)

        self.config = load_config()
        self.goods: List[GoodsItem] = load_goods()

        self._build_ui()
        self._load_config_to_fields()
        self._refresh_quick_calc()
        self._refresh_goods_table()

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

        main_layout.addWidget(self._build_top_bar())

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)

        left_layout.addWidget(self._build_params_group())
        left_layout.addWidget(self._build_quick_group())
        left_layout.addStretch(1)

        splitter.addWidget(left_widget)
        splitter.addWidget(self._build_goods_group())
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        main_layout.addWidget(splitter)
        self.setCentralWidget(central)

    def _build_top_bar(self) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.rate_label = QLabel("Курс USDT: —")
        self.status_label = QLabel("OFFLINE")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("background-color: #6b2b2b; padding: 4px 10px; border-radius: 10px;")

        refresh_button = QPushButton("↻ Обновить")
        refresh_button.clicked.connect(self.update_rate)

        settings_button = QPushButton("⚙")
        settings_button.setFixedWidth(44)
        settings_button.clicked.connect(self.open_settings)

        layout.addWidget(self.rate_label)
        layout.addWidget(self.status_label)
        layout.addStretch(1)
        layout.addWidget(refresh_button)
        layout.addWidget(settings_button)
        return container

    def _build_params_group(self) -> QGroupBox:
        group = QGroupBox("Курс / Параметры")

        self.coin_to_adena_input = self._make_number_input("1 монета = X адены")
        self.rub_per_1kk_input = self._make_number_input("1кк адены = ₽")

        save_button = QPushButton("Сохранить")
        save_button.clicked.connect(self.save_params)

        form_layout = QFormLayout()
        form_layout.setContentsMargins(12, 12, 12, 12)
        form_layout.setSpacing(8)
        form_layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form_layout.addRow("1 монета = адены", self.coin_to_adena_input)
        form_layout.addRow("1кк адены = ₽ (FP)", self.rub_per_1kk_input)

        layout = QVBoxLayout(group)
        layout.addLayout(form_layout)
        layout.addWidget(save_button, alignment=Qt.AlignRight)

        self.coin_to_adena_input.editingFinished.connect(self.save_params)
        self.rub_per_1kk_input.editingFinished.connect(self.save_params)
        return group

    def _build_quick_group(self) -> QGroupBox:
        group = QGroupBox("Быстрый расчёт")
        self.coins_qty_input = self._make_number_input("Кол-во монет")
        self.coins_qty_input.textChanged.connect(self._refresh_quick_calc)

        self.fp_buyer_label = QLabel("—")
        self.fp_payout_label = QLabel("—")
        self.withdraw_fee_label = QLabel("—")
        self.withdraw_rub_label = QLabel("—")
        self.withdraw_usdt_label = QLabel("—")
        self.debug_button = QPushButton("ℹ")
        self.debug_button.setFixedWidth(36)
        self.debug_button.clicked.connect(self._show_debug_breakdown)

        form_layout = QFormLayout()
        form_layout.setContentsMargins(12, 12, 12, 12)
        form_layout.setSpacing(8)
        form_layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form_layout.addRow("Кол-во монет", self.coins_qty_input)
        form_layout.addRow("СБП ₽ покупателя", self.fp_buyer_label)
        form_layout.addRow("FP ₽ мне", self.fp_payout_label)
        form_layout.addRow("Комиссия вывода ₽", self.withdraw_fee_label)
        form_layout.addRow("Вывод ₽", self.withdraw_rub_label)
        form_layout.addRow("Вывод USDT", self.withdraw_usdt_label)

        layout = QVBoxLayout(group)
        info_layout = QHBoxLayout()
        info_layout.addStretch(1)
        info_layout.addWidget(self.debug_button)
        layout.addLayout(info_layout)
        layout.addLayout(form_layout)
        return group

    def _build_goods_group(self) -> QGroupBox:
        group = QGroupBox("Товары")

        self.item_name_input = QLineEdit()
        self.item_name_input.setPlaceholderText("Название товара (необязательно)")
        self.item_price_input = self._make_number_input("Цена в монетах")

        add_button = QPushButton("Добавить")
        add_button.clicked.connect(self.add_goods)

        remove_button = QPushButton("Удалить")
        remove_button.clicked.connect(self.remove_selected_goods)

        clear_button = QPushButton("Очистить")
        clear_button.clicked.connect(self.clear_goods)

        self.goods_hint = QLabel("")
        self.goods_hint.setObjectName("HintLabel")
        self.goods_hint.setWordWrap(True)

        form_layout = QFormLayout()
        form_layout.setContentsMargins(12, 12, 12, 0)
        form_layout.setSpacing(8)
        form_layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form_layout.addRow("Товар", self.item_name_input)
        form_layout.addRow("Цена (монеты)", self.item_price_input)

        buttons_layout = QHBoxLayout()
        buttons_layout.setContentsMargins(12, 8, 12, 12)
        buttons_layout.setSpacing(8)
        buttons_layout.addWidget(add_button)
        buttons_layout.addWidget(remove_button)
        buttons_layout.addWidget(clear_button)
        buttons_layout.addStretch(1)

        self.goods_table = QTableWidget(0, 6)
        self.goods_table.setHorizontalHeaderLabels(
            [
                "Name",
                "Price (coins)",
                "SBP buyer (₽)",
                "FP payout me (₽)",
                "Withdraw (USDT)",
                "Withdraw (₽)",
            ]
        )
        self.goods_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.goods_table.setSelectionMode(QTableWidget.SingleSelection)
        self.goods_table.verticalHeader().setVisible(False)
        self.goods_table.horizontalHeader().setStretchLastSection(True)

        layout = QVBoxLayout(group)
        layout.addLayout(form_layout)
        layout.addLayout(buttons_layout)
        layout.addWidget(self.goods_hint)
        layout.addWidget(self.goods_table)
        return group

    def _make_number_input(self, placeholder: str) -> QLineEdit:
        field = QLineEdit()
        field.setPlaceholderText(placeholder)
        field.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        validator = QDoubleValidator(0.0, 1_000_000_000.0, 6, field)
        validator.setNotation(QDoubleValidator.StandardNotation)
        field.setValidator(validator)
        return field

    def _load_config_to_fields(self) -> None:
        self.coin_to_adena_input.setText(_format_number(self.config.coin_to_adena))
        self.rub_per_1kk_input.setText(_format_number(self.config.rub_per_1kk_buyer))

    def save_params(self) -> None:
        coin_to_adena = _parse_positive_float(self.coin_to_adena_input.text())
        rub_per_1kk = _parse_positive_float(self.rub_per_1kk_input.text())
        self.config = replace(self.config, coin_to_adena=coin_to_adena, rub_per_1kk_buyer=rub_per_1kk)
        save_config(self.config)
        self._refresh_quick_calc()
        self._refresh_goods_table()

    def open_settings(self) -> None:
        dialog = SettingsDialog(
            self.config.funpay_fee,
            self.config.sbp_fee_effective,
            self.config.withdraw_fee_pct,
            self.config.withdraw_fee_min_rub,
            self.config.withdraw_rate_rub_per_usdt or self.config.rub_per_usdt,
            self,
        )
        if dialog.exec() == dialog.Accepted:
            funpay_fee = dialog.parse_percent(dialog.funpay_fee_input.text())
            sbp_fee_effective = dialog.parse_percent(dialog.sbp_fee_effective_input.text())
            withdraw_fee_pct = dialog.parse_percent(dialog.withdraw_fee_pct_input.text())
            withdraw_fee_min_rub = dialog.parse_number(dialog.withdraw_fee_min_rub_input.text())
            withdraw_rate_rub_per_usdt = dialog.parse_number(dialog.withdraw_rate_rub_per_usdt_input.text())
            self.config = replace(
                self.config,
                funpay_fee=funpay_fee if funpay_fee is not None else self.config.funpay_fee,
                sbp_fee_effective=(
                    sbp_fee_effective if sbp_fee_effective is not None else self.config.sbp_fee_effective
                ),
                withdraw_fee_pct=(
                    withdraw_fee_pct if withdraw_fee_pct is not None else self.config.withdraw_fee_pct
                ),
                withdraw_fee_min_rub=(
                    withdraw_fee_min_rub
                    if withdraw_fee_min_rub is not None
                    else self.config.withdraw_fee_min_rub
                ),
                withdraw_rate_rub_per_usdt=(
                    withdraw_rate_rub_per_usdt
                    if withdraw_rate_rub_per_usdt is not None
                    else self.config.withdraw_rate_rub_per_usdt
                ),
            )
            save_config(self.config)
            self._refresh_quick_calc()
            self._refresh_goods_table()

    def update_rate(self) -> None:
        self.status_label.setText("UPDATING")
        self.status_label.setStyleSheet("background-color: #3a3f48; padding: 4px 10px; border-radius: 10px;")
        QApplication.processEvents()
        result = fetch_rate()
        if result.rate is not None:
            updated_withdraw_rate = self.config.withdraw_rate_rub_per_usdt
            if updated_withdraw_rate is None or updated_withdraw_rate == self.config.rub_per_usdt:
                updated_withdraw_rate = result.rate
            self.config = replace(
                self.config,
                rub_per_usdt=result.rate,
                withdraw_rate_rub_per_usdt=updated_withdraw_rate,
            )
            save_config(self.config)
            self.status_label.setText("OK")
            self.status_label.setStyleSheet("background-color: #1f6f50; padding: 4px 10px; border-radius: 10px;")
        else:
            self.status_label.setText("OFFLINE")
            self.status_label.setStyleSheet("background-color: #6b2b2b; padding: 4px 10px; border-radius: 10px;")
        self.rate_label.setText(f"Курс USDT: {_format_rub(self.config.rub_per_usdt, suffix='')}")
        self._refresh_quick_calc()
        self._refresh_goods_table()

    def _refresh_quick_calc(self) -> None:
        settings = self._settings()
        coins_qty = _parse_positive_float(self.coins_qty_input.text())
        result = calc_quick(settings, coins_qty)
        self.fp_buyer_label.setText(_format_rub(result.sbp_price_rub_buyer))
        self.fp_payout_label.setText(_format_rub(result.fp_payout_rub_me))
        self.withdraw_fee_label.setText(_format_rub(result.withdraw_fee_rub))
        self.withdraw_rub_label.setText(_format_rub(result.withdraw_rub))
        self.withdraw_usdt_label.setText(_format_usdt(result.withdraw_usdt))

    def add_goods(self) -> None:
        price_coins = _parse_positive_float(self.item_price_input.text())
        if price_coins is None:
            self.goods_hint.setText("Введите цену товара в монетах.")
            return
        if calc_rub_per_coin_buyer(self._settings()) is None:
            self.goods_hint.setText("Заполните курс монеты к адене и ₽ за 1кк.")
            return
        item = new_goods_item(self.item_name_input.text(), price_coins)
        self.goods.append(item)
        save_goods(self.goods)
        self.item_name_input.clear()
        self.item_price_input.clear()
        self.goods_hint.setText("")
        self._refresh_goods_table()

    def remove_selected_goods(self) -> None:
        selection = self.goods_table.selectionModel().selectedRows()
        if not selection:
            return
        index = selection[0].row()
        if 0 <= index < len(self.goods):
            self.goods.pop(index)
            save_goods(self.goods)
            self._refresh_goods_table()

    def clear_goods(self) -> None:
        if not self.goods:
            return
        self.goods = []
        save_goods(self.goods)
        self._refresh_goods_table()

    def _refresh_goods_table(self) -> None:
        self.goods_table.setRowCount(len(self.goods))
        settings = self._settings()
        for row_index, item in enumerate(self.goods):
            calc = calc_item(settings, item.price_coins)
            values = [
                item.name,
                _format_coins(item.price_coins),
                _format_rub(calc.sbp_price_rub_buyer),
                _format_rub(calc.fp_payout_rub_me),
                _format_usdt(calc.withdraw_usdt),
                _format_rub(calc.withdraw_rub),
            ]
            for col, text in enumerate(values):
                cell = QTableWidgetItem(text)
                if col > 0:
                    cell.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.goods_table.setItem(row_index, col, cell)
        self.goods_table.resizeRowsToContents()

    def _settings(self) -> Settings:
        return Settings(
            coin_to_adena=self.config.coin_to_adena,
            rub_per_1kk_buyer=self.config.rub_per_1kk_buyer,
            funpay_fee=self.config.funpay_fee,
            sbp_fee_effective=self.config.sbp_fee_effective,
            withdraw_fee_pct=self.config.withdraw_fee_pct,
            withdraw_fee_min_rub=self.config.withdraw_fee_min_rub,
            withdraw_rate_rub_per_usdt=self.config.withdraw_rate_rub_per_usdt,
            rub_per_usdt=self.config.rub_per_usdt,
        )

    def _show_debug_breakdown(self) -> None:
        settings = self._settings()
        coins_qty = _parse_positive_float(self.coins_qty_input.text())
        rub_per_coin = calc_rub_per_coin_buyer(settings)
        sbp_raw = coins_qty * rub_per_coin if coins_qty is not None and rub_per_coin is not None else None
        result = calc_quick(settings, coins_qty)
        lines = [
            f"coins_qty: {_format_number(coins_qty) or '—'}",
            f"rub_per_coin: {_format_number(rub_per_coin) or '—'}",
            f"sbp_raw: {_format_rub(sbp_raw)}",
            f"me_rub: {_format_rub(result.fp_payout_rub_me)}",
            f"sbp_price_rub: {_format_rub(result.sbp_price_rub_buyer)}",
            f"amount_rub: {_format_rub(result.fp_payout_rub_me)}",
            f"fee_rub: {_format_rub(result.withdraw_fee_rub)}",
            f"net_rub: {_format_rub(result.withdraw_rub)}",
            f"withdraw_rate_rub_per_usdt: {_format_rub(settings.withdraw_rate_rub_per_usdt, suffix='')}",
            f"withdraw_usdt: {_format_usdt(result.withdraw_usdt)}",
            f"sbp_fee_effective: {_format_number(settings.sbp_fee_effective) or '—'}",
            f"withdraw_fee_pct: {_format_number(settings.withdraw_fee_pct) or '—'}",
            f"withdraw_fee_min_rub: {_format_number(settings.withdraw_fee_min_rub) or '—'}",
        ]
        QMessageBox.information(self, "Debug breakdown", "\n".join(lines))


def _parse_positive_float(text: str) -> Optional[float]:
    normalized = text.replace(",", ".").strip()
    if not normalized:
        return None
    try:
        value = float(normalized)
    except ValueError:
        return None
    return value if value > 0 else None


def _format_number(value: Optional[float]) -> str:
    if value is None:
        return ""
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _format_coins(value: Optional[float]) -> str:
    if value is None:
        return "—"
    formatted = f"{value:,.6f}"
    whole, _, frac = formatted.partition(".")
    frac = frac.rstrip("0")
    if len(frac) < 2:
        frac = frac.ljust(2, "0")
    return f"{whole}.{frac}".replace(",", " ")


def _format_rub(value: Optional[float], suffix: str = " ₽") -> str:
    if value is None:
        return "—"
    return f"{value:,.2f}{suffix}".replace(",", " ")


def _format_usdt(value: Optional[float]) -> str:
    if value is None:
        return "—"
    return f"{value:,.4f} USDT".replace(",", " ")
