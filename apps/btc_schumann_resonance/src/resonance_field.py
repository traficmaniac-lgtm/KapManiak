import math
import random
from dataclasses import dataclass
from typing import List, Tuple

from PySide6.QtGui import QColor, QImage, QPainter, QPen

from .features import FeatureSnapshot


@dataclass
class FieldConfig:
    field_mode: bool = True
    energy_gain: float = 1.8
    energy_floor: float = 0.04
    gamma: float = 0.65
    crown_gain: float = 1.4
    palette_base: float = 0.60
    palette_shift: float = 0.0


class ResonanceField:
    def __init__(self) -> None:
        self.phase = 0.0
        self.noise_seed = random.random() * 10.0
        self.last_drive = 0.0
        self.hue_shift = 0.0

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
        self.hue_shift = (self.hue_shift + 0.0005) % 1.0
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

        positions = [0.10, 0.18, 0.26, 0.34, 0.42, 0.50, 0.58, 0.66]
        sigma_low = 0.028
        sigma_high = 0.012
        harmonics: List[Tuple[float, float, float]] = []
        for i, pos in enumerate(positions):
            sigma = sigma_low - (sigma_low - sigma_high) * (i / max(1, len(positions) - 1))
            base_amp = (0.25 + 0.75 * drive) * (1.0 / (1.0 + i * 0.35))
            omega = 0.15 + i * 0.04
            phase_i = self.noise_seed * 1.7 + i * 0.9
            mod = 0.70 + 0.30 * math.sin(phase_i + self.phase * omega)
            band_noise = 0.5 + 0.5 * math.sin(self.noise_seed * 4.1 + i * 2.3)
            amp = base_amp * mod * (1.0 + 0.25 * micro * band_noise)
            harmonics.append((pos, sigma, amp))

        bins = snapshot.spectral_bins[:64] if snapshot.spectral_bins else []
        spec_drive = 0.0
        if bins:
            spec_drive = min(1.0, sum(bins) / len(bins))
        crown_ratio = 0.30
        crown_gain = config.crown_gain * (0.6 + 1.4 * spec_drive)

        imbalance_norm = imbalance * 0.5 + 0.5
        hue_base = config.palette_base + config.palette_shift + self.hue_shift
        for y in range(height):
            y_norm = y / max(1, height - 1)
            y_bottom = 1.0 - y_norm
            energy = 0.0
            drift = imbalance * 0.015 + math.sin(self.phase * 0.08 + self.noise_seed) * 0.004
            for pos, sigma, amp in harmonics:
                dy = y_bottom - pos - drift
                energy += amp * math.exp(-(dy * dy) / (2.0 * sigma * sigma))
            if bins and y_norm <= crown_ratio:
                rel = 1.0 - y_norm / crown_ratio
                idx = int(rel * (len(bins) - 1))
                crown_energy = bins[idx] * (0.35 + 0.65 * rel)
                energy += crown_gain * crown_energy
            noise = 0.5 + 0.5 * math.sin(y_norm * 28.0 + self.noise_seed * 6.7)
            energy += noise * micro * 0.12
            energy *= max(0.2, 1.0 - 0.25 * spread)
            energy = max(0.0, min(1.0, energy))
            energy = max(config.energy_floor, min(1.0, config.energy_floor + energy * config.energy_gain))

            hue = hue_base + 0.35 * (1.0 - y_norm) + 0.10 * (imbalance_norm - 0.5)
            hue %= 1.0
            saturation = min(1.0, 0.75 + 0.25 * drive)
            value = pow(max(0.0, min(1.0, energy)), config.gamma)
            if value > 0.85:
                value = 1.0
                saturation *= 0.65
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
        spec_drive = min(1.0, sum(bins) / len(bins)) if bins else 0.0
        gain = config.crown_gain * (0.6 + 1.4 * spec_drive)
        for idx, value in enumerate(bins[:64]):
            if value <= 0.01:
                continue
            freq_pos = idx / 64.0
            ray_height = int(value * crown_height * gain)
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
