import math
import random
from dataclasses import dataclass
from typing import List, Tuple

from PySide6.QtGui import QColor, QImage, QPainter, QPen

from .features import FeatureSnapshot


@dataclass
class FieldConfig:
    field_mode: bool = True
    palette_shift: float = 0.0


class ResonanceField:
    def __init__(self) -> None:
        self.phase = 0.0
        self.noise_seed = random.random() * 10.0
        self.last_drive = 0.0

    def build_column(self, height: int, snapshot: FeatureSnapshot, config: FieldConfig) -> QImage:
        column = QImage(1, height, QImage.Format_ARGB32)
        column.fill(0)
        painter = QPainter(column)
        try:
            painter.setRenderHint(QPainter.Antialiasing, False)
            if config.field_mode:
                self._draw_field(painter, height, snapshot, config)
            else:
                self._draw_baseline(painter, height, snapshot, config)
                self._draw_main_wave(painter, height, snapshot, config)
                self._draw_crown(painter, height, snapshot, config)
                self._draw_direction_marker(painter, height, snapshot)
        finally:
            painter.end()
        self.phase += 0.14
        return column

    def _draw_field(
        self,
        painter: QPainter,
        height: int,
        snapshot: FeatureSnapshot,
        config: FieldConfig,
    ) -> None:
        if height <= 0:
            return
        tps = snapshot.norm["tps"]
        volume = snapshot.norm["volume"]
        micro = snapshot.norm["micro"]
        spectral = snapshot.norm["spectral"]
        spread = snapshot.norm["spread"]
        imbalance = snapshot.norm["imbalance"]
        drive = min(1.0, 0.45 * tps + 0.45 * volume + 0.15 * micro + 0.2 * spectral)
        drive *= max(0.25, 1.0 - 0.35 * spread)
        self.last_drive = drive

        positions = [0.82, 0.72, 0.64, 0.56, 0.48, 0.40]
        sigma_min = 0.015
        sigma_max = 0.04
        harmonics: List[Tuple[float, float, float]] = []
        for i, pos in enumerate(positions):
            sigma = sigma_max - (sigma_max - sigma_min) * (i / max(1, len(positions) - 1))
            base_amp = (0.15 + 0.85 * drive) * (1.0 / (i + 1))
            omega = 0.18 + i * 0.07
            phase_i = self.noise_seed * 1.7 + i * 0.6
            mod = 0.55 + 0.45 * math.sin(phase_i + self.phase * omega)
            harmonics.append((pos, sigma, base_amp * mod))

        crown = [0.0 for _ in range(height)]
        bins = snapshot.spectral_bins[:32]
        if bins:
            for idx, value in enumerate(bins):
                if value <= 0.01:
                    continue
                y_norm = (idx / max(1, len(bins) - 1)) * 0.25
                center = int(y_norm * (height - 1))
                sigma_px = max(1, int(height * 0.012))
                start = max(0, center - 3 * sigma_px)
                end = min(height - 1, center + 3 * sigma_px)
                for y in range(start, end + 1):
                    dist = (y - center) / max(1.0, sigma_px)
                    crown[y] += value * math.exp(-(dist * dist) / 2.0)

        imbalance_norm = imbalance * 0.5 + 0.5
        hue_base = 0.62 + config.palette_shift
        for y in range(height):
            y_norm = y / max(1, height - 1)
            energy = 0.0
            drift = imbalance * 0.02 + math.sin(self.phase * 0.08 + self.noise_seed) * 0.004
            for pos, sigma, amp in harmonics:
                dy = y_norm - pos - drift
                energy += amp * math.exp(-(dy * dy) / (2.0 * sigma * sigma))
            crown_energy = spectral * max(0.0, (0.28 - y_norm) / 0.28)
            energy += crown[y] * (0.5 + spectral * 0.7) + crown_energy
            ripple = (math.sin(y_norm * 55.0 + self.phase * 1.3 + self.noise_seed * 3.3) + 1.0) * 0.5
            energy += ripple * micro * 0.15
            energy *= max(0.2, 1.0 - 0.25 * spread)
            energy = max(0.0, min(1.0, energy))

            hue = hue_base + 0.30 * (1.0 - y_norm) + 0.10 * (imbalance_norm - 0.5) + 0.05 * math.sin(
                self.phase * 0.2
            )
            hue %= 1.0
            saturation = min(1.0, 0.65 + 0.35 * drive)
            value = max(0.05, min(1.0, 0.05 + 0.95 * energy))
            if energy > 0.85 and micro > 0.6:
                value = 1.0
                saturation *= 0.45
            alpha = min(1.0, 0.2 + 0.8 * energy)
            color = QColor.fromHsvF(hue, saturation, value, alpha)
            painter.setPen(color)
            painter.drawPoint(0, y)

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
        if not config.field_mode:
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
        if not config.field_mode:
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
