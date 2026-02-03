from __future__ import annotations

from dataclasses import dataclass
from PySide6.QtGui import QColor


@dataclass
class PaletteConfig:
    hue_range: tuple[float, float]
    saturation_boost: float


MODE_PALETTES = {
    "CALM": PaletteConfig(hue_range=(200.0, 280.0), saturation_boost=0.9),
    "FLOW": PaletteConfig(hue_range=(190.0, 310.0), saturation_boost=1.0),
    "NOISE": PaletteConfig(hue_range=(210.0, 330.0), saturation_boost=1.1),
    "SHOCK": PaletteConfig(hue_range=(240.0, 330.0), saturation_boost=1.2),
}


def energy_color(energy: float, coherence: float, mode: str) -> QColor:
    config = MODE_PALETTES.get(mode, MODE_PALETTES["CALM"])
    hue_start, hue_end = config.hue_range
    hue = hue_start + (hue_end - hue_start) * energy
    saturation = min(1.0, max(0.15, (0.4 + 0.6 * coherence) * config.saturation_boost))
    value = min(1.0, max(0.0, energy))
    color = QColor()
    color.setHsvF(hue / 360.0, saturation, value)
    return color


def corona_color(intensity: float, mode: str) -> QColor:
    config = MODE_PALETTES.get(mode, MODE_PALETTES["CALM"])
    hue = config.hue_range[1] - 20 + 40 * intensity
    saturation = min(1.0, 0.6 + 0.4 * intensity)
    value = min(1.0, 0.4 + 0.6 * intensity)
    color = QColor()
    color.setHsvF(hue / 360.0, saturation, value)
    return color
