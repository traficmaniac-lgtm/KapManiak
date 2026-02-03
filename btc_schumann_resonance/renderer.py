from __future__ import annotations

import time
from PySide6 import QtCore, QtGui, QtWidgets

from .palette import energy_color, corona_color


class ResonanceRenderer(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAutoFillBackground(False)
        self._image = QtGui.QImage(900, 540, QtGui.QImage.Format.Format_RGB32)
        self._image.fill(QtGui.QColor("black"))
        self._last_frame = time.monotonic()
        self._fps = 0.0
        self._frame_count = 0
        self._last_fps_update = self._last_frame
        self._overlay_rect = QtCore.QRect(12, 12, 240, 92)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        size = event.size()
        if size.width() > 0 and size.height() > 0:
            self._image = QtGui.QImage(size, QtGui.QImage.Format.Format_RGB32)
            self._image.fill(QtGui.QColor("black"))
        super().resizeEvent(event)

    def tick(self, profile: list[float], gain: float, avg_energy: float, spectrum: list[float], mode: str, coherence: float) -> None:
        self._fade_buffer()
        self._scroll_buffer()
        self._draw_column(profile, gain, mode, coherence)
        self._draw_corona(spectrum, mode)
        self._update_fps()
        self.update()

    def _fade_buffer(self) -> None:
        painter = QtGui.QPainter(self._image)
        painter.setCompositionMode(QtGui.QPainter.CompositionMode.CompositionMode_SourceOver)
        painter.fillRect(self._image.rect(), QtGui.QColor(0, 0, 0, 18))
        painter.end()

    def _scroll_buffer(self) -> None:
        self._image.scroll(-1, 0, self._image.rect())

    def _draw_column(self, profile: list[float], gain: float, mode: str, coherence: float) -> None:
        width = self._image.width()
        x = width - 1
        height = self._image.height()
        for y, energy in enumerate(profile):
            intensity = min(1.0, energy * gain)
            color = energy_color(intensity, coherence, mode)
            self._image.setPixelColor(x, height - 1 - y, color)

    def _draw_corona(self, spectrum: list[float], mode: str) -> None:
        if not spectrum:
            return
        width = self._image.width()
        corona_height = int(self._image.height() * 0.27)
        painter = QtGui.QPainter(self._image)
        painter.setCompositionMode(QtGui.QPainter.CompositionMode.CompositionMode_Plus)
        bins = len(spectrum)
        for x in range(width):
            idx = int(x / width * bins)
            intensity = spectrum[min(idx, bins - 1)]
            color = corona_color(intensity, mode)
            alpha = int(90 + 140 * intensity)
            color.setAlpha(alpha)
            y0 = 0
            y1 = int(corona_height * (0.4 + 0.6 * intensity))
            painter.setPen(QtGui.QPen(color, 1))
            painter.drawLine(x, y0, x, y1)
        painter.end()

    def _update_fps(self) -> None:
        now = time.monotonic()
        self._frame_count += 1
        if now - self._last_fps_update >= 0.5:
            elapsed = now - self._last_fps_update
            self._fps = self._frame_count / max(1e-6, elapsed)
            self._frame_count = 0
            self._last_fps_update = now

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        painter = QtGui.QPainter(self)
        painter.drawImage(0, 0, self._image)
        self._draw_overlay(painter)
        painter.end()

    def _draw_overlay(self, painter: QtGui.QPainter) -> None:
        painter.save()
        painter.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing)
        painter.setBrush(QtGui.QColor(10, 10, 20, 180))
        painter.setPen(QtGui.QColor(120, 180, 255))
        painter.drawRoundedRect(self._overlay_rect, 8, 8)
        painter.setPen(QtGui.QColor(200, 220, 255))
        font = QtGui.QFont("Consolas", 10)
        painter.setFont(font)
        lines = self._overlay_lines
        for i, text in enumerate(lines):
            painter.drawText(self._overlay_rect.adjusted(12, 10 + i * 18, -8, -8), text)
        painter.restore()

    @property
    def fps(self) -> float:
        return self._fps

    @property
    def _overlay_lines(self) -> list[str]:
        return getattr(self, "__overlay_lines", [])

    @_overlay_lines.setter
    def _overlay_lines(self, value: list[str]) -> None:
        setattr(self, "__overlay_lines", value)

    def update_overlay(self, lines: list[str]) -> None:
        self._overlay_lines = lines
