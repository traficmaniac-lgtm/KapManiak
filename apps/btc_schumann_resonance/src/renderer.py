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
    ws_connected: bool = False
    last_msg_age_ms: float = -1.0
    book_count: float = 0.0
    trade_count: float = 0.0
    depth_count: float = 0.0
    drive: float = 0.0
    field_mode: bool = True
    fade_alpha: int = 10
    palette_shift: float = 0.0


class Renderer:
    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.canvas = QImage(width, height, QImage.Format_ARGB32)
        self.canvas.fill(QColor(6, 8, 16))
        self.hud = HUDState()
        self.fade_alpha = 10

    def resize(self, width: int, height: int) -> None:
        if width <= 0 or height <= 0:
            return
        old_canvas = self.canvas
        self.width = width
        self.height = height
        new_canvas = QImage(width, height, QImage.Format_ARGB32)
        new_canvas.fill(QColor(6, 8, 16))
        painter = QPainter(new_canvas)
        try:
            painter.setRenderHint(QPainter.Antialiasing, False)
            src_width = min(old_canvas.width(), new_canvas.width())
            src_height = min(old_canvas.height(), new_canvas.height())
            painter.drawImage(QRect(0, 0, src_width, src_height), old_canvas, QRect(0, 0, src_width, src_height))
        finally:
            painter.end()
        self.canvas = new_canvas

    def clear(self) -> None:
        self.canvas.fill(QColor(6, 8, 16))

    def update_hud(
        self,
        status: str,
        snapshot: Optional[FeatureSnapshot],
        paused: bool,
        diagnostics: Optional[dict] = None,
        render_state: Optional[dict] = None,
    ) -> None:
        self.hud.status = status
        self.hud.snapshot = snapshot
        self.hud.paused = paused
        if diagnostics:
            self.hud.ws_connected = diagnostics.get("ws_connected", False)
            self.hud.last_msg_age_ms = diagnostics.get("last_msg_age_ms", -1.0)
            self.hud.book_count = diagnostics.get("book_count", 0.0)
            self.hud.trade_count = diagnostics.get("trade_count", 0.0)
            self.hud.depth_count = diagnostics.get("depth_count", 0.0)
        if render_state:
            self.hud.drive = render_state.get("drive", 0.0)
            self.hud.field_mode = render_state.get("field_mode", True)
            self.hud.fade_alpha = render_state.get("fade_alpha", self.fade_alpha)
            self.hud.palette_shift = render_state.get("palette_shift", 0.0)

    def render_frame(self, column: Optional[QImage], shift: bool = True) -> None:
        if shift:
            self.shift_left_1px()
        draw_column = column if column is not None else self._build_test_column(self.canvas.height())
        if draw_column is None:
            return
        painter = QPainter(self.canvas)
        try:
            painter.setRenderHint(QPainter.Antialiasing, False)
            painter.drawImage(self.canvas.width() - 1, 0, draw_column)
        finally:
            painter.end()

    def shift_left_1px(self) -> None:
        w = self.canvas.width()
        h = self.canvas.height()
        if w <= 1 or h <= 0:
            return
        painter = QPainter(self.canvas)
        try:
            painter.setRenderHint(QPainter.Antialiasing, False)
            painter.setCompositionMode(QPainter.CompositionMode_Source)
            painter.drawImage(QRect(0, 0, w - 1, h), self.canvas, QRect(1, 0, w - 1, h))
            painter.fillRect(w - 1, 0, 1, h, QColor(0, 0, 0))
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            painter.fillRect(0, 0, w, h, QColor(0, 0, 0, self.fade_alpha))
        finally:
            painter.end()

    def save_png(self, output_dir: str) -> str:
        os.makedirs(output_dir, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        path = os.path.join(output_dir, f"schumann_{timestamp}.png")
        self.canvas.save(path)
        return path

    def draw_hud(self, painter: QPainter) -> None:
        painter.setRenderHint(QPainter.Antialiasing, False)
        painter.setPen(QColor(200, 220, 255, 220))
        painter.setFont(QFont("Consolas", 9))
        mode = "FIELD" if self.hud.field_mode else "LEGACY"
        lines = [f"WS: {self.hud.status}", f"Mode={mode} Drive={self.hud.drive:.2f}"]
        if self.hud.snapshot:
            snap = self.hud.snapshot
            lines.append(f"tps={snap.tps:.1f} vol={snap.volume_per_s:.2f}")
            lines.append(f"spread={snap.spread_bps:.2f} imb={snap.imbalance:+.3f}")
            lines.append(f"micro={snap.micro_vol:.5f} spec={snap.spectral_energy:.3f}")
        lines.append(f"fade={self.hud.fade_alpha} hue={self.hud.palette_shift:+.2f}")
        if self.hud.paused:
            lines.append("PAUSED")
        lines = lines[:6]
        hud_width = 250
        hud_height = 14 + len(lines) * 13
        painter.fillRect(8, 8, hud_width, hud_height, QColor(0, 0, 0, 160))
        for idx, line in enumerate(lines):
            painter.drawText(12, 18 + idx * 13, line)

    @staticmethod
    def _build_test_column(height: int) -> Optional[QImage]:
        if height <= 0:
            return None
        column = QImage(1, height, QImage.Format_ARGB32)
        column.fill(QColor(0, 0, 0))
        painter = QPainter(column)
        try:
            painter.setRenderHint(QPainter.Antialiasing, False)
            for y in range(height):
                hue = 0.55 + (y / max(1, height)) * 0.25
                color = QColor.fromHsvF(hue % 1.0, 0.6, 0.9, 0.9)
                painter.setPen(color)
                painter.drawPoint(0, y)
        finally:
            painter.end()
        return column
