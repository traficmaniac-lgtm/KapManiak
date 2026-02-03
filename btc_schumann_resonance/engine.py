from __future__ import annotations

from dataclasses import dataclass
import math
import random
from collections import deque


@dataclass
class HarmonicBand:
    center: float
    sigma: float
    amplitude: float


@dataclass
class ExposureState:
    gain: float = 1.0
    target: float = 0.35


class ResonanceEngine:
    """Generates Schumann-like harmonic energy profiles with auto-exposure."""

    def __init__(self, height: int, seed: int | None = None) -> None:
        self.height = height
        self._rng = random.Random(seed)
        self.bands = self._make_bands()
        self.exposure = ExposureState(gain=1.2)
        self.history = deque([0.0] * 96, maxlen=192)

    def _make_bands(self) -> list[HarmonicBand]:
        return [
            HarmonicBand(center=0.08, sigma=0.015, amplitude=1.0),
            HarmonicBand(center=0.17, sigma=0.02, amplitude=0.85),
            HarmonicBand(center=0.27, sigma=0.025, amplitude=0.8),
            HarmonicBand(center=0.39, sigma=0.03, amplitude=0.75),
            HarmonicBand(center=0.52, sigma=0.035, amplitude=0.7),
            HarmonicBand(center=0.65, sigma=0.04, amplitude=0.6),
            HarmonicBand(center=0.78, sigma=0.045, amplitude=0.5),
            HarmonicBand(center=0.9, sigma=0.05, amplitude=0.45),
        ]

    def _mode_width_scale(self, mode: str) -> float:
        return {
            "CALM": 0.9,
            "FLOW": 1.1,
            "NOISE": 1.25,
            "SHOCK": 1.35,
        }.get(mode, 1.0)

    def _mode_gain_boost(self, mode: str) -> float:
        return {
            "CALM": 0.95,
            "FLOW": 1.05,
            "NOISE": 1.15,
            "SHOCK": 1.35,
        }.get(mode, 1.0)

    def generate_profile(self, mode: str, coherence: float, volatility: float) -> tuple[list[float], float, float]:
        width_scale = self._mode_width_scale(mode)
        gain_boost = self._mode_gain_boost(mode)
        noise_amount = 0.05 + volatility * 0.15
        flow_tilt = self._rng.uniform(-0.08, 0.08) if mode == "FLOW" else 0.0

        profile: list[float] = []
        max_energy = 1e-6
        for y in range(self.height):
            y_norm = y / (self.height - 1)
            energy = 0.0
            for band in self.bands:
                center = band.center + flow_tilt
                sigma = band.sigma * width_scale
                amplitude = band.amplitude * gain_boost
                gaussian = math.exp(-((y_norm - center) ** 2) / (2 * sigma * sigma))
                energy += amplitude * gaussian
            energy += self._rng.uniform(-noise_amount, noise_amount) * (1.0 - coherence)
            energy = max(0.0, energy)
            profile.append(energy)
            max_energy = max(max_energy, energy)

        profile = [val / max_energy for val in profile]
        avg_energy = sum(profile) / len(profile)
        self.history.append(avg_energy)

        self._update_exposure(avg_energy)
        return profile, self.exposure.gain, avg_energy

    def _update_exposure(self, avg_energy: float) -> None:
        target = self.exposure.target
        desired_gain = target / max(avg_energy, 1e-3)
        current = self.exposure.gain
        ema = 0.08
        gain = current * (1.0 - ema) + desired_gain * ema
        self.exposure.gain = min(3.0, max(0.6, gain))

    def spectrum(self) -> list[float]:
        """Compute log-scaled FFT magnitude for the corona (simple DFT)."""
        values = list(self.history)
        n = len(values)
        if n == 0:
            return []
        windowed = [v * (0.5 - 0.5 * math.cos(2 * math.pi * i / (n - 1))) for i, v in enumerate(values)]
        half = n // 2
        spectrum: list[float] = []
        for k in range(half):
            re = 0.0
            im = 0.0
            for i, sample in enumerate(windowed):
                angle = 2 * math.pi * k * i / n
                re += sample * math.cos(angle)
                im -= sample * math.sin(angle)
            magnitude = math.sqrt(re * re + im * im)
            spectrum.append(math.log1p(magnitude))
        max_val = max(spectrum) if spectrum else 1.0
        return [val / max_val for val in spectrum]
