from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class GoodsPanel(QGroupBox):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("Товары", parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Название товара")

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Цена в монетах", "USDT на вывод"])

        self.value_input = QLineEdit()
        self.value_input.setPlaceholderText("Значение")
        validator = QDoubleValidator(0.0, 1_000_000_000.0, 6, self.value_input)
        validator.setNotation(QDoubleValidator.StandardNotation)
        self.value_input.setValidator(validator)

        self.add_button = QPushButton("Добавить")
        self.remove_button = QPushButton("Удалить")
        self.clear_button = QPushButton("Очистить")
        self.export_button = QPushButton("Экспорт CSV")
        self.hint_label = QLabel("")
        self.hint_label.setObjectName("HintLabel")
        self.hint_label.setWordWrap(True)

        form_layout = QFormLayout()
        form_layout.setContentsMargins(12, 12, 12, 0)
        form_layout.setSpacing(8)
        form_layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form_layout.addRow("Товар", self.name_input)
        form_layout.addRow("Режим", self.mode_combo)
        form_layout.addRow("Значение", self.value_input)

        buttons_layout = QHBoxLayout()
        buttons_layout.setContentsMargins(12, 8, 12, 12)
        buttons_layout.setSpacing(8)
        buttons_layout.addWidget(self.add_button)
        buttons_layout.addWidget(self.remove_button)
        buttons_layout.addWidget(self.clear_button)
        buttons_layout.addStretch(1)
        buttons_layout.addWidget(self.export_button)

        layout = QVBoxLayout(self)
        layout.addLayout(form_layout)
        layout.addLayout(buttons_layout)
        layout.addWidget(self.hint_label)

    def bind_add(self, handler: Callable[[], None]) -> None:
        self.add_button.clicked.connect(handler)

    def bind_remove(self, handler: Callable[[], None]) -> None:
        self.remove_button.clicked.connect(handler)

    def bind_clear(self, handler: Callable[[], None]) -> None:
        self.clear_button.clicked.connect(handler)

    def bind_export(self, handler: Callable[[], None]) -> None:
        self.export_button.clicked.connect(handler)

    def payload(self) -> dict:
        return {
            "name": self.name_input.text().strip() or "Без названия",
            "mode": self.mode_combo.currentIndex(),
            "value": self._parse(self.value_input.text()),
        }

    def set_mode_label(self) -> None:
        if self.mode_combo.currentIndex() == 0:
            self.value_input.setPlaceholderText("Монеты")
        else:
            self.value_input.setPlaceholderText("USDT (на вывод)")

    def set_hint(self, text: str) -> None:
        self.hint_label.setText(text)

    def _parse(self, value: str) -> Optional[float]:
        value = value.replace(",", ".").strip()
        if not value:
            return None
        try:
            return float(value)
        except ValueError:
            return None
