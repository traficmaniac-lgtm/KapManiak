import os
import time
from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter

from .features import FeatureSnapshot


@dataclass
class HUDState:
    status: str = "DISCONNECTED"
    snapshot: Optional[FeatureSnapshot] = None
    paused: bool = False


class Renderer:
    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.image = QImage(width, height, QImage.Format_ARGB32)
        self.image.fill(QColor(6, 8, 16))
        self.hud = HUDState()

    def resize(self, width: int, height: int) -> None:
        if width <= 0 or height <= 0:
            return
        self.width = width
        self.height = height
        self.image = QImage(width, height, QImage.Format_ARGB32)
        self.image.fill(QColor(6, 8, 16))

    def clear(self) -> None:
        self.image.fill(QColor(6, 8, 16))

    def update_hud(self, status: str, snapshot: Optional[FeatureSnapshot], paused: bool) -> None:
        self.hud.status = status
        self.hud.snapshot = snapshot
        self.hud.paused = paused

    def render_frame(self, column: Optional[QImage], shift: bool = True) -> None:
        painter = QPainter(self.image)
        try:
            painter.setRenderHint(QPainter.Antialiasing, False)
            if shift and self.width > 1:
                painter.drawImage(
                    QRect(0, 0, self.width - 1, self.height),
                    self.image,
                    QRect(1, 0, self.width - 1, self.height),
                )
            if shift and column is not None:
                painter.fillRect(QRect(self.width - 1, 0, 1, self.height), QColor(0, 0, 0, 0))
                painter.drawImage(self.width - 1, 0, column)
                painter.fillRect(0, 0, self.width, self.height, QColor(0, 0, 0, 18))
            self._draw_hud(painter)
        finally:
            painter.end()

    def save_png(self, output_dir: str) -> str:
        os.makedirs(output_dir, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        path = os.path.join(output_dir, f"schumann_{timestamp}.png")
        self.image.save(path)
        return path

    def _draw_hud(self, painter: QPainter) -> None:
        painter.setPen(QColor(200, 220, 255, 210))
        painter.setFont(QFont("Consolas", 9))
        lines = [f"WS: {self.hud.status}"]
        if self.hud.snapshot:
            snap = self.hud.snapshot
            lines.append(f"mid: {snap.mid:.2f}")
            lines.append(f"tps: {snap.tps:.1f}")
            lines.append(f"spread: {snap.spread_bps:.2f} bps")
            lines.append(f"imb: {snap.imbalance:+.3f}")
            lines.append(f"micro: {snap.micro_vol:.5f}")
        if self.hud.paused:
            lines.append("PAUSED")
        for idx, line in enumerate(lines):
            painter.drawText(8, 18 + idx * 14, line)
