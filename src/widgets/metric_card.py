from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget
from PySide6.QtCore import Qt


class MetricCard(QWidget):
    def __init__(self, title: str, value: str = "—", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.title_label = QLabel(title)
        self.value_label = QLabel(value)

        self.title_label.setObjectName("MetricTitle")
        self.value_label.setObjectName("MetricValue")
        self.value_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)
        layout.addWidget(self.value_label)
        layout.addWidget(self.title_label)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)
