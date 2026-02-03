from __future__ import annotations

from dataclasses import dataclass
from typing import List

from PySide6.QtCore import QRect
from PySide6.QtGui import QColor, QLinearGradient, QPainter

from features import FeatureSnapshot


@dataclass
class RenderParam:
    key: str
    hue: int
    weight: float


class ColumnRenderer:
    def __init__(self) -> None:
        self.params: List[RenderParam] = [
            RenderParam("tps", 210, 0.18),
            RenderParam("volps", 140, 0.18),
            RenderParam("spread_bps", 30, 0.15),
            RenderParam("imbalance", 300, 0.15),
            RenderParam("micro_vol", 20, 0.18),
            RenderParam("spectral_energy", 260, 0.16),
        ]

    def draw_column(self, painter: QPainter, x: int, height: int, snapshot: FeatureSnapshot, mode: str) -> None:
        if mode == "BANDS":
            self._draw_bands(painter, x, height, snapshot)
        else:
            self._draw_stacked(painter, x, height, snapshot)

    def _draw_stacked(self, painter: QPainter, x: int, height: int, snapshot: FeatureSnapshot) -> None:
        y_bottom = height
        for param in self.params:
            norm = snapshot.norms.get(param.key, 0.0)
            seg_height = int(height * param.weight * norm)
            if seg_height <= 0:
                continue
            y_bottom -= seg_height
            rect = QRect(x, y_bottom, 1, seg_height)
            gradient = QLinearGradient(rect.left(), rect.top(), rect.left(), rect.bottom())
            base = QColor.fromHsv(param.hue, 200, 120)
            bright = QColor.fromHsv(param.hue, 255, 255)
            gradient.setColorAt(0.0, bright)
            gradient.setColorAt(1.0, base)
            painter.fillRect(rect, gradient)

        marker_color = QColor(0, 220, 0) if snapshot.direction >= 0 else QColor(220, 0, 0)
        painter.setPen(marker_color)
        painter.drawPoint(x, 0)

    def _draw_bands(self, painter: QPainter, x: int, height: int, snapshot: FeatureSnapshot) -> None:
        band_height = max(1, height // len(self.params))
        for idx, param in enumerate(self.params):
            norm = snapshot.norms.get(param.key, 0.0)
            y_top = idx * band_height
            rect = QRect(x, y_top, 1, band_height)
            base = QColor.fromHsv(param.hue, 160, int(60 + 140 * norm))
            bright = QColor.fromHsv(param.hue, 255, int(120 + 135 * norm))
            gradient = QLinearGradient(rect.left(), rect.top(), rect.left(), rect.bottom())
            gradient.setColorAt(0.0, bright)
            gradient.setColorAt(1.0, base)
            painter.fillRect(rect, gradient)

        marker_color = QColor(0, 220, 0) if snapshot.direction >= 0 else QColor(220, 0, 0)
        painter.setPen(marker_color)
        painter.drawPoint(x, 0)
