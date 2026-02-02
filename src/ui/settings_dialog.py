from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QVBoxLayout,
)


class SettingsDialog(QDialog):
    def __init__(
        self,
        funpay_fee: float,
        sbp_fee_effective: float,
        k_card_ru: float,
        k_sbp_qr: float,
        withdraw_fee_pct: float,
        withdraw_fee_min_rub: float,
        withdraw_rate_rub_per_usdt: Optional[float],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Настройки")
        self.setModal(True)

        self.funpay_fee_input = self._make_percent_field("Комиссия FunPay (%)")
        self.sbp_fee_effective_input = self._make_percent_field("Эффективная комиссия СБП (%)")
        self.k_card_ru_input = self._make_number_field("Коэф. карта RU")
        self.k_sbp_qr_input = self._make_number_field("Коэф. СБП QR")
        self.withdraw_fee_pct_input = self._make_percent_field("Комиссия вывода (%)")
        self.withdraw_fee_min_rub_input = self._make_number_field("Мин. комиссия вывода (₽)")
        self.withdraw_rate_rub_per_usdt_input = self._make_number_field("Курс вывода (FP)")

        self.set_percent_value(self.funpay_fee_input, funpay_fee)
        self.set_percent_value(self.sbp_fee_effective_input, sbp_fee_effective)
        self.set_number_value(self.k_card_ru_input, k_card_ru)
        self.set_number_value(self.k_sbp_qr_input, k_sbp_qr)
        self.set_percent_value(self.withdraw_fee_pct_input, withdraw_fee_pct)
        self.set_number_value(self.withdraw_fee_min_rub_input, withdraw_fee_min_rub)
        self.set_number_value(self.withdraw_rate_rub_per_usdt_input, withdraw_rate_rub_per_usdt)

        form_layout = QFormLayout()
        form_layout.setContentsMargins(16, 16, 16, 8)
        form_layout.setSpacing(10)
        form_layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form_layout.addRow("Комиссия FunPay (%)", self.funpay_fee_input)
        form_layout.addRow("Эффективная комиссия СБП (%)", self.sbp_fee_effective_input)
        form_layout.addRow("Коэф. карта RU", self.k_card_ru_input)
        form_layout.addRow("Коэф. СБП QR", self.k_sbp_qr_input)
        form_layout.addRow("Комиссия вывода (%)", self.withdraw_fee_pct_input)
        form_layout.addRow("Мин. комиссия вывода (₽)", self.withdraw_fee_min_rub_input)
        form_layout.addRow("Курс вывода (FP)", self.withdraw_rate_rub_per_usdt_input)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form_layout)
        layout.addWidget(buttons)

    def _make_percent_field(self, placeholder: str) -> QLineEdit:
        field = QLineEdit()
        field.setPlaceholderText(placeholder)
        field.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        validator = QDoubleValidator(0.0, 100.0, 2, field)
        validator.setNotation(QDoubleValidator.StandardNotation)
        field.setValidator(validator)
        return field

    def _make_number_field(self, placeholder: str) -> QLineEdit:
        field = QLineEdit()
        field.setPlaceholderText(placeholder)
        field.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        validator = QDoubleValidator(0.0, 1_000_000_000.0, 6, field)
        validator.setNotation(QDoubleValidator.StandardNotation)
        field.setValidator(validator)
        return field

    @staticmethod
    def set_percent_value(field: QLineEdit, value: float) -> None:
        field.setText(f"{value * 100:.2f}")

    @staticmethod
    def parse_percent(text: str) -> Optional[float]:
        normalized = text.replace(",", ".").strip()
        if not normalized:
            return None
        try:
            value = float(normalized)
        except ValueError:
            return None
        return value / 100

    @staticmethod
    def set_number_value(field: QLineEdit, value: Optional[float]) -> None:
        if value is None:
            field.setText("")
        else:
            field.setText(f"{value:.6f}".rstrip("0").rstrip("."))

    @staticmethod
    def parse_number(text: str) -> Optional[float]:
        normalized = text.replace(",", ".").strip()
        if not normalized:
            return None
        try:
            value = float(normalized)
        except ValueError:
            return None
        return value
