from __future__ import annotations

from dataclasses import dataclass
import random
import time


MODES = ("CALM", "FLOW", "NOISE", "SHOCK")


@dataclass
class MarketState:
    mode: str
    coherence: float
    volatility: float


class MarketFeed:
    """Mock market feed that cycles through modes and emits stability hints."""

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)
        self._mode_index = 0
        self._last_switch = time.monotonic()
        self._mode_duration = 12.0

    def _maybe_switch_mode(self) -> None:
        now = time.monotonic()
        if now - self._last_switch >= self._mode_duration:
            self._last_switch = now
            self._mode_index = (self._mode_index + 1) % len(MODES)
            self._mode_duration = self._rng.uniform(8.0, 16.0)

    def sample(self) -> MarketState:
        self._maybe_switch_mode()
        mode = MODES[self._mode_index]
        coherence = {
            "CALM": 0.9,
            "FLOW": 0.75,
            "NOISE": 0.5,
            "SHOCK": 0.3,
        }[mode]
        volatility = {
            "CALM": 0.2,
            "FLOW": 0.45,
            "NOISE": 0.7,
            "SHOCK": 1.0,
        }[mode]
        coherence += self._rng.uniform(-0.05, 0.05)
        volatility += self._rng.uniform(-0.05, 0.05)
        return MarketState(mode=mode, coherence=max(0.1, min(1.0, coherence)), volatility=max(0.05, min(1.2, volatility)))
