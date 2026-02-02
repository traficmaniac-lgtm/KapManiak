from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QWidget,
)


class ParamsPanel(QGroupBox):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("Параметры", parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.coin_per_1kkA = self._make_field("монет за 1кк")
        self.fp_buyer_rub_per_1kkA = self._make_field("₽ за 1кк (FP)")
        self.fee_fp = self._make_field("комиссия FP", suffix="")
        self.fee_withdraw = self._make_field("комиссия вывода", suffix="")
        self.coins_in = self._make_field("монет ввод")

        layout = QFormLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        layout.setFormAlignment(Qt.AlignTop)

        layout.addRow("Монет за 1кк адены", self.coin_per_1kkA)
        layout.addRow("FP ₽ для покупателя", self.fp_buyer_rub_per_1kkA)
        layout.addRow("Комиссия FunPay", self.fee_fp)
        layout.addRow("Комиссия вывода USDT", self.fee_withdraw)
        layout.addRow("Текущий ввод монет", self.coins_in)

    def _make_field(self, placeholder: str, suffix: str = "") -> QLineEdit:
        field = QLineEdit()
        field.setPlaceholderText(placeholder)
        field.setProperty("suffix", suffix)
        field.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        validator = QDoubleValidator(0.0, 1_000_000_000.0, 6, field)
        validator.setNotation(QDoubleValidator.StandardNotation)
        field.setValidator(validator)
        return field

    def bind(self, handler: Callable[[], None]) -> None:
        for widget in [
            self.coin_per_1kkA,
            self.fp_buyer_rub_per_1kkA,
            self.fee_fp,
            self.fee_withdraw,
            self.coins_in,
        ]:
            widget.textChanged.connect(handler)

    @staticmethod
    def _parse(value: str) -> Optional[float]:
        value = value.replace(",", ".").strip()
        if not value:
            return None
        try:
            return float(value)
        except ValueError:
            return None

    def values(self) -> dict:
        return {
            "coin_per_1kkA": self._parse(self.coin_per_1kkA.text()),
            "fp_buyer_rub_per_1kkA": self._parse(self.fp_buyer_rub_per_1kkA.text()),
            "fee_fp": self._parse(self.fee_fp.text()),
            "fee_withdraw": self._parse(self.fee_withdraw.text()),
            "coins_in": self._parse(self.coins_in.text()),
        }

    def set_values(self, values: dict) -> None:
        mapping = {
            self.coin_per_1kkA: values.get("coin_per_1kkA"),
            self.fp_buyer_rub_per_1kkA: values.get("fp_buyer_rub_per_1kkA"),
            self.fee_fp: values.get("fee_fp"),
            self.fee_withdraw: values.get("fee_withdraw"),
            self.coins_in: values.get("coins_in"),
        }
        for widget, value in mapping.items():
            widget.blockSignals(True)
            widget.setText("" if value is None else f"{value:.6g}")
            widget.blockSignals(False)
