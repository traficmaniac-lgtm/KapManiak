from __future__ import annotations

import sys
from PySide6 import QtCore, QtWidgets

from .engine import ResonanceEngine
from .market_feed import MarketFeed
from .renderer import ResonanceRenderer


class ResonanceWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("BTC Schumann Resonance — LIVE")
        self.resize(960, 600)
        self._renderer = ResonanceRenderer(self)
        self.setCentralWidget(self._renderer)
        self._feed = MarketFeed()
        self._engine = ResonanceEngine(height=self._renderer.height())
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def _tick(self) -> None:
        state = self._feed.sample()
        if self._engine.height != self._renderer.height():
            self._engine = ResonanceEngine(height=self._renderer.height())
        profile, gain, avg_energy = self._engine.generate_profile(state.mode, state.coherence, state.volatility)
        spectrum = self._engine.spectrum()
        self._renderer.tick(profile, gain, avg_energy, spectrum, state.mode, state.coherence)
        self._renderer.update_overlay(
            [
                f"FPS: {self._renderer.fps:4.1f}",
                f"Mode: {state.mode}",
                f"Gain: {gain:4.2f}",
                f"Avg: {avg_energy:4.2f}",
                f"Coherence: {state.coherence:4.2f}",
            ]
        )


def main() -> int:
    app = QtWidgets.QApplication(sys.argv)
    window = ResonanceWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
