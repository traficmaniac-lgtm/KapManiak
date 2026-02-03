import os
import time
from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QMainWindow, QWidget

from .features import FeatureLayer, FeatureSnapshot
from .renderer import Renderer
from .resonance_field import FieldConfig, ResonanceField
from .ws_client import WSClient, WSDataStore


@dataclass
class RuntimeState:
    paused: bool = False
    field_mode: bool = True
    fade_alpha: int = 10
    palette_shift: float = 0.0


class ResonanceWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setFocusPolicy(Qt.StrongFocus)
        self.store = WSDataStore()
        self.ws_client = WSClient(self.store)
        self.ws_client.start()

        self.feature_layer = FeatureLayer()
        self.field = ResonanceField()
        self.config = FieldConfig(field_mode=True)
        self.state = RuntimeState()
        self.snapshot: Optional[FeatureSnapshot] = None
        self.latest_column = None

        self.renderer = Renderer(self.width() or 1200, self.height() or 700)

        self.feature_timer = QTimer(self)
        self.feature_timer.timeout.connect(self._update_features)
        self.feature_timer.start(33)

        self.render_timer = QTimer(self)
        self.render_timer.timeout.connect(self._render_frame)
        self.render_timer.start(33)

    def closeEvent(self, event) -> None:
        self.ws_client.stop()
        super().closeEvent(event)

    def resizeEvent(self, event) -> None:
        size = event.size()
        self.renderer.resize(size.width(), size.height())
        super().resizeEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.Antialiasing, False)
            painter.drawImage(0, 0, self.renderer.canvas)
            self.renderer.draw_hud(painter)
        finally:
            painter.end()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Space:
            self.state.paused = not self.state.paused
        elif event.key() == Qt.Key_C:
            self.renderer.clear()
        elif event.key() == Qt.Key_F:
            self.state.field_mode = not self.state.field_mode
            self.config.field_mode = self.state.field_mode
        elif event.key() in (Qt.Key_Plus, Qt.Key_Equal):
            self.state.fade_alpha = min(24, self.state.fade_alpha + 2)
            self.renderer.fade_alpha = self.state.fade_alpha
        elif event.key() in (Qt.Key_Minus, Qt.Key_Underscore):
            self.state.fade_alpha = max(4, self.state.fade_alpha - 2)
            self.renderer.fade_alpha = self.state.fade_alpha
        elif event.key() == Qt.Key_BracketLeft:
            self.state.palette_shift -= 0.02
            self.config.palette_shift = self.state.palette_shift
        elif event.key() == Qt.Key_BracketRight:
            self.state.palette_shift += 0.02
            self.config.palette_shift = self.state.palette_shift
        elif event.key() == Qt.Key_S:
            output_dir = os.path.join(os.path.dirname(__file__), "..", "out")
            self.renderer.save_png(os.path.abspath(output_dir))
        else:
            super().keyPressEvent(event)

    def _update_features(self) -> None:
        snapshot = self.feature_layer.process(self.store)
        if snapshot is None:
            return
        self.snapshot = snapshot
        self.config.field_mode = self.state.field_mode
        self.config.palette_shift = self.state.palette_shift
        self.latest_column = self.field.build_column(self.renderer.canvas.height(), snapshot, self.config)

    def _render_frame(self) -> None:
        diagnostics = self.store.get_diagnostics()
        status = diagnostics.get("status", "DISCONNECTED")
        self.renderer.update_hud(
            status,
            self.snapshot,
            self.state.paused,
            diagnostics,
            {
                "drive": self.field.last_drive,
                "field_mode": self.state.field_mode,
                "fade_alpha": self.state.fade_alpha,
                "palette_shift": self.state.palette_shift,
            },
        )
        if self.state.paused:
            self.renderer.render_frame(None, shift=False)
            self.update()
            return
        self.renderer.render_frame(self.latest_column, shift=True)
        self.update()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("BTC Schumann Resonance — LIVE")
        self.widget = ResonanceWidget()
        self.setCentralWidget(self.widget)
        self.resize(1200, 700)
