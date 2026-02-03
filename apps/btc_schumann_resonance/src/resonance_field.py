import math
import random
from dataclasses import dataclass
from typing import List

from PySide6.QtGui import QColor, QImage, QPainter, QPen

from .features import FeatureSnapshot


@dataclass
class FieldConfig:
    stacked_mode: bool = True


class ResonanceField:
    def __init__(self) -> None:
        self.phase = 0.0
        self.noise_seed = random.random() * 10.0

    def build_column(self, height: int, snapshot: FeatureSnapshot, config: FieldConfig) -> QImage:
        column = QImage(1, height, QImage.Format_ARGB32)
        column.fill(0)
        painter = QPainter(column)
        try:
            painter.setRenderHint(QPainter.Antialiasing, False)
            self._draw_baseline(painter, height, snapshot, config)
            self._draw_main_wave(painter, height, snapshot, config)
            self._draw_crown(painter, height, snapshot, config)
            self._draw_direction_marker(painter, height, snapshot)
        finally:
            painter.end()
        self.phase += 0.18
        return column

    def _draw_baseline(
        self,
        painter: QPainter,
        height: int,
        snapshot: FeatureSnapshot,
        config: FieldConfig,
    ) -> None:
        spread = snapshot.norm["spread"]
        imbalance = snapshot.norm["imbalance"]
        band_height = int(height * 0.25)
        base_center = int(height * 0.85)
        if config.stacked_mode:
            base_center = height - band_height // 2
        sway = math.sin(self.phase * 0.25 + self.noise_seed) * band_height * 0.05
        offset = imbalance * band_height * 0.3
        amplitude = max(1.0, spread * band_height * 0.4)
        y_center = int(base_center + offset + sway)
        hue = 0.62 - spread * 0.12
        color = QColor.fromHsvF(hue, 0.75, 0.9, 0.8)
        pen = QPen(color)
        pen.setWidthF(1.0 + spread * 1.5)
        painter.setPen(pen)
        painter.drawLine(0, int(y_center - amplitude), 0, int(y_center + amplitude))

    def _draw_main_wave(
        self,
        painter: QPainter,
        height: int,
        snapshot: FeatureSnapshot,
        config: FieldConfig,
    ) -> None:
        tps = snapshot.norm["tps"]
        volume = snapshot.norm["volume"]
        micro = snapshot.norm["micro"]
        band_height = int(height * 0.45)
        if config.stacked_mode:
            band_center = int(height * 0.55)
        else:
            band_center = int(height * 0.55 + math.sin(self.phase * 0.2) * height * 0.05)
        amplitude = max(4.0, tps * band_height * 0.5)
        freq = 6.0 + micro * 8.0
        base_hue = 0.48 + micro * 0.18
        for i in range(-band_height // 2, band_height // 2):
            y = band_center + i
            if y < 0 or y >= height:
                continue
            rel = i / max(1.0, amplitude)
            wave = math.sin(rel * freq + self.phase) * (0.6 + micro)
            ripple = math.sin(rel * 12.0 + self.phase * 1.5) * micro
            intensity = max(0.0, wave + ripple)
            if intensity <= 0.01:
                continue
            hue = (base_hue + intensity * 0.08) % 1.0
            alpha = min(0.9, 0.3 + intensity * 0.6 + volume * 0.3)
            color = QColor.fromHsvF(hue, 0.7, 0.95, alpha)
            painter.setPen(color)
            painter.drawPoint(0, y)

    def _draw_crown(
        self,
        painter: QPainter,
        height: int,
        snapshot: FeatureSnapshot,
        config: FieldConfig,
    ) -> None:
        bins = snapshot.spectral_bins
        if not bins:
            return
        crown_height = int(height * 0.25)
        crown_base = crown_height
        energy = snapshot.norm["spectral"]
        for idx, value in enumerate(bins[:32]):
            if value <= 0.01:
                continue
            freq_pos = idx / 32.0
            ray_height = int(value * crown_height * (0.6 + energy))
            y_start = crown_base - ray_height
            hue = 0.78 + freq_pos * 0.12
            alpha = min(0.9, 0.25 + value * 0.7 + energy * 0.2)
            color = QColor.fromHsvF(hue, 0.65, 0.98, alpha)
            pen = QPen(color)
            pen.setWidthF(1.0)
            painter.setPen(pen)
            painter.drawLine(0, crown_base, 0, max(0, y_start))

    def _draw_direction_marker(self, painter: QPainter, height: int, snapshot: FeatureSnapshot) -> None:
        direction = snapshot.direction
        if direction == 0.0:
            return
        color = QColor(80, 255, 120, 200) if direction > 0 else QColor(255, 80, 100, 200)
        painter.setPen(color)
        painter.drawPoint(0, height - 2)
