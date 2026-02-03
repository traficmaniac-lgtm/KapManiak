import math
import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, List, Optional, Tuple

import numpy as np

from .ws_client import WSDataStore


@dataclass
class FeatureSnapshot:
    mid: float
    spread_bps: float
    imbalance: float
    tps: float
    volume_per_s: float
    micro_vol: float
    spectral_energy: float
    spectral_bins: List[float]
    direction: float
    norm: Dict[str, float]


class EMANormalizer:
    def __init__(self, alpha: float = 0.05) -> None:
        self.alpha = alpha
        self.baselines: Dict[str, float] = {}

    def _update(self, key: str, value: float) -> float:
        baseline = self.baselines.get(key, value)
        baseline = baseline * (1.0 - self.alpha) + value * self.alpha
        self.baselines[key] = max(baseline, 1e-9)
        return self.baselines[key]

    def normalize(self, key: str, value: float, k: float = 2.0) -> float:
        baseline = self._update(key, abs(value))
        return max(0.0, min(value / (baseline * k), 1.0))

    def normalize_signed(self, key: str, value: float, k: float = 2.0) -> float:
        baseline = self._update(key, abs(value))
        norm = max(-1.0, min(value / (baseline * k), 1.0))
        return norm


class FeatureLayer:
    def __init__(self) -> None:
        self.normalizer = EMANormalizer(alpha=0.06)
        self.trade_window: Deque[Tuple[float, float]] = deque()
        self.returns: Deque[float] = deque(maxlen=256)
        self.last_mid: Optional[float] = None
        self.last_trade_id: Optional[int] = None

    def process(self, store: WSDataStore) -> Optional[FeatureSnapshot]:
        with store.lock:
            book = store.book_ticker
            depth = store.depth
            trades = list(store.trades)
            status = store.status
        if status in {"DISCONNECTED", "ERROR", "CONNECTING"} and not book:
            return None
        if not book:
            return None

        try:
            bid = float(book.get("b", 0.0))
            ask = float(book.get("a", 0.0))
        except (TypeError, ValueError):
            return None
        if bid <= 0 or ask <= 0:
            return None
        mid = (bid + ask) / 2.0
        spread_bps = (ask - bid) / mid * 10000.0

        imbalance = 0.0
        if depth:
            bids = depth.get("b", [])
            asks = depth.get("a", [])
            try:
                bid_vol = sum(float(qty) for _, qty in bids)
                ask_vol = sum(float(qty) for _, qty in asks)
                total = bid_vol + ask_vol
                if total > 0:
                    imbalance = (bid_vol - ask_vol) / total
            except (TypeError, ValueError):
                imbalance = 0.0

        now = time.time()
        for trade in trades:
            trade_id = trade.get("a")
            if trade_id is None:
                continue
            if self.last_trade_id is not None and trade_id <= self.last_trade_id:
                continue
            self.last_trade_id = trade_id
            try:
                qty = float(trade.get("q", 0.0))
                ts = float(trade.get("T", 0)) / 1000.0
            except (TypeError, ValueError):
                continue
            ts = ts if ts > 0 else now
            self.trade_window.append((ts, qty))

        while self.trade_window and now - self.trade_window[0][0] > 1.0:
            self.trade_window.popleft()

        tps = float(len(self.trade_window))
        volume_per_s = float(sum(qty for _, qty in self.trade_window))

        direction = 0.0
        if self.last_mid is not None:
            direction = math.copysign(1.0, mid - self.last_mid) if mid != self.last_mid else 0.0
            self.returns.append(math.log(mid / self.last_mid))
        self.last_mid = mid

        micro_vol = float(np.std(self.returns)) if len(self.returns) > 5 else 0.0

        spectral_bins: List[float] = []
        spectral_energy = 0.0
        if len(self.returns) >= 128:
            window_size = min(256, len(self.returns))
            arr = np.array(list(self.returns)[-window_size:], dtype=np.float32)
            arr = arr - np.mean(arr)
            window = np.hanning(window_size).astype(np.float32)
            arr = arr * window
            fft_vals = np.fft.rfft(arr)
            mag = np.abs(fft_vals)[1:65]
            log_mag = np.log1p(mag)
            spectral_energy = float(np.mean(log_mag)) if log_mag.size else 0.0
            spectral_bins = log_mag.tolist()
        else:
            spectral_bins = [0.0] * 64

        norm = {
            "spread": self.normalizer.normalize("spread", spread_bps, k=2.0),
            "imbalance": self.normalizer.normalize_signed("imbalance", imbalance, k=1.8),
            "tps": self.normalizer.normalize("tps", tps, k=2.2),
            "volume": self.normalizer.normalize("volume", volume_per_s, k=2.2),
            "micro": self.normalizer.normalize("micro", micro_vol, k=2.0),
            "spectral": self.normalizer.normalize("spectral", spectral_energy, k=2.0),
        }

        if spectral_bins:
            normalized_bins: List[float] = []
            for idx, value in enumerate(spectral_bins):
                norm_value = self.normalizer.normalize(f"spec_bin_{idx}", value, k=2.0)
                normalized_bins.append(norm_value)
            spectral_bins = normalized_bins
        else:
            spectral_bins = [0.0] * 64

        return FeatureSnapshot(
            mid=mid,
            spread_bps=spread_bps,
            imbalance=imbalance,
            tps=tps,
            volume_per_s=volume_per_s,
            micro_vol=micro_vol,
            spectral_energy=spectral_energy,
            spectral_bins=spectral_bins,
            direction=direction,
            norm=norm,
        )
