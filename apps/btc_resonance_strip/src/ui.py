from __future__ import annotations

import os
import time
from datetime import datetime

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QFont, QImage, QPainter
from PySide6.QtWidgets import QMainWindow, QWidget

from features import FeatureState
from renderer import ColumnRenderer
from ws_client import BinanceWSClient


class CanvasWidget(QWidget):
    def __init__(self, state: FeatureState, renderer: ColumnRenderer) -> None:
        super().__init__()
        self.state = state
        self.renderer = renderer
        self.mode = "STACKED"
        self.paused = False
        self.image = QImage(800, 400, QImage.Format_RGB32)
        self.image.fill(Qt.black)
        self.setMinimumSize(640, 360)

        self.timer = QTimer(self)
        self.timer.setInterval(33)
        self.timer.timeout.connect(self.on_tick)
        self.timer.start()

    def toggle_mode(self) -> None:
        self.mode = "BANDS" if self.mode == "STACKED" else "STACKED"

    def clear(self) -> None:
        self.image.fill(Qt.black)

    def save_screenshot(self) -> str:
        out_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "out")
        os.makedirs(out_dir, exist_ok=True)
        filename = datetime.now().strftime("resonance_%Y%m%d_%H%M%S.png")
        path = os.path.join(out_dir, filename)
        self.image.save(path)
        return path

    def resizeEvent(self, event) -> None:
        new_image = QImage(self.width(), self.height(), QImage.Format_RGB32)
        new_image.fill(Qt.black)
        painter = QPainter(new_image)
        try:
            painter.drawImage(0, 0, self.image)
        finally:
            painter.end()
        self.image = new_image
        super().resizeEvent(event)

    def on_tick(self) -> None:
        if not self.paused:
            self.shift_left()
            snapshot = self.state.snapshot()
            painter = QPainter(self.image)
            try:
                self.renderer.draw_column(painter, self.image.width() - 1, self.image.height(), snapshot, self.mode)
            finally:
                painter.end()
        self.update()

    def shift_left(self) -> None:
        if self.image.width() <= 1:
            return
        painter = QPainter(self.image)
        try:
            painter.drawImage(0, 0, self.image, 1, 0, self.image.width() - 1, self.image.height())
            painter.fillRect(self.image.width() - 1, 0, 1, self.image.height(), Qt.black)
        finally:
            painter.end()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        try:
            painter.drawImage(0, 0, self.image)
            self.draw_hud(painter)
        finally:
            painter.end()

    def draw_hud(self, painter: QPainter) -> None:
        snapshot = self.state.snapshot()
        painter.setPen(Qt.white)
        painter.setFont(QFont("Consolas", 9))
        status = "OK" if snapshot.ws_ok else "WAIT"
        hud = (
            f"WS={status} age_ms={snapshot.age_ms} mid={snapshot.mid:.2f} "
            f"tps={snapshot.tps:.1f} volps={snapshot.volps:.3f} "
            f"spread_bps={snapshot.spread_bps:.2f} imbalance={snapshot.imbalance:.2f} "
            f"micro_vol={snapshot.micro_vol:.6f}"
        )
        painter.drawText(10, self.height() - 10, hud)


class ResonanceWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.state = FeatureState()
        self.renderer = ColumnRenderer()
        self.canvas = CanvasWidget(self.state, self.renderer)
        self.setCentralWidget(self.canvas)
        self.ws_client = BinanceWSClient(self.state)
        self.ws_client.start()
        self.update_title()
        self.resize(1200, 600)

        self._title_timer = QTimer(self)
        self._title_timer.setInterval(500)
        self._title_timer.timeout.connect(self.update_title)
        self._title_timer.start()

    def update_title(self) -> None:
        self.setWindowTitle(f"BTC Infinite Resonance Strip - {self.canvas.mode}")

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Space:
            self.canvas.paused = not self.canvas.paused
        elif event.key() == Qt.Key_C:
            self.canvas.clear()
        elif event.key() == Qt.Key_F:
            self.canvas.toggle_mode()
            self.update_title()
        elif event.key() == Qt.Key_S:
            self.canvas.save_screenshot()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event) -> None:
        self.ws_client.stop()
        self.ws_client.join(timeout=2.0)
        super().closeEvent(event)
