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
    def __init__(self, funpay_fee: float, usdt_withdraw_fee: float, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Настройки комиссий")
        self.setModal(True)

        self.funpay_fee_input = self._make_percent_field("Комиссия FunPay (%)")
        self.usdt_withdraw_fee_input = self._make_percent_field("Комиссия вывода USDT (%)")

        self.set_percent_value(self.funpay_fee_input, funpay_fee)
        self.set_percent_value(self.usdt_withdraw_fee_input, usdt_withdraw_fee)

        form_layout = QFormLayout()
        form_layout.setContentsMargins(16, 16, 16, 8)
        form_layout.setSpacing(10)
        form_layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form_layout.addRow("Комиссия FunPay (%)", self.funpay_fee_input)
        form_layout.addRow("Комиссия вывода USDT (%)", self.usdt_withdraw_fee_input)

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
