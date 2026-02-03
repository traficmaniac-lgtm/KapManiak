from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass
from threading import Lock
from typing import Deque, Dict, List, Tuple

import numpy as np


@dataclass
class FeatureSnapshot:
    tps: float
    volps: float
    spread_bps: float
    imbalance: float
    micro_vol: float
    direction: float
    spectral_energy: float
    mid: float
    age_ms: int
    ws_ok: bool
    norms: Dict[str, float]


class EMA:
    def __init__(self, alpha: float = 0.05, initial: float = 1e-6) -> None:
        self.alpha = alpha
        self.value = initial
        self.initialized = False

    def update(self, value: float) -> float:
        if not self.initialized:
            self.value = max(value, 1e-6)
            self.initialized = True
            return self.value
        self.value = self.value + self.alpha * (value - self.value)
        return self.value


class FeatureState:
    def __init__(self) -> None:
        self.lock = Lock()
        self.mid: float = 0.0
        self.prev_mid: float = 0.0
        self.spread_bps: float = 0.0
        self.imbalance: float = 0.0
        self.last_update: float = time.time()
        self.ws_ok: bool = False

        self.trade_window: Deque[Tuple[float, float]] = deque()
        self.returns: Deque[float] = deque(maxlen=128)

        self.ema_tps = EMA(alpha=0.05)
        self.ema_volps = EMA(alpha=0.05)
        self.ema_spread = EMA(alpha=0.05)
        self.ema_micro = EMA(alpha=0.05)
        self.ema_spec = EMA(alpha=0.05)

    def update_connection(self, ok: bool) -> None:
        with self.lock:
            self.ws_ok = ok

    def update_book(self, bid: float, ask: float, ts: float) -> None:
        mid = (bid + ask) / 2.0
        spread_bps = 0.0
        if mid > 0:
            spread_bps = (ask - bid) / mid * 10000.0

        with self.lock:
            self.prev_mid = self.mid or mid
            self.mid = mid
            if self.prev_mid > 0:
                ret = math.log(self.mid / self.prev_mid)
                self.returns.append(ret)
            self.spread_bps = spread_bps
            self.last_update = ts

    def update_trade(self, qty: float, ts: float) -> None:
        with self.lock:
            self.trade_window.append((ts, qty))
            self.last_update = ts

    def update_depth(self, bids: List[Tuple[float, float]], asks: List[Tuple[float, float]], ts: float) -> None:
        bid_qty = sum(qty for _, qty in bids)
        ask_qty = sum(qty for _, qty in asks)
        denom = bid_qty + ask_qty
        imbalance = 0.0
        if denom > 0:
            imbalance = (bid_qty - ask_qty) / denom
        with self.lock:
            self.imbalance = imbalance
            self.last_update = ts

    def _compute_trade_metrics(self, now_ts: float) -> Tuple[float, float]:
        while self.trade_window and self.trade_window[0][0] < now_ts - 1.0:
            self.trade_window.popleft()
        if not self.trade_window:
            return 0.0, 0.0
        tps = len(self.trade_window) / 1.0
        volps = sum(qty for _, qty in self.trade_window) / 1.0
        return tps, volps

    def snapshot(self) -> FeatureSnapshot:
        now_ts = time.time()
        with self.lock:
            tps, volps = self._compute_trade_metrics(now_ts)
            spread_bps = self.spread_bps
            imbalance = self.imbalance
            mid = self.mid
            direction = 0.0
            if self.prev_mid != 0.0:
                delta = self.mid - self.prev_mid
                direction = 1.0 if delta >= 0 else -1.0
            returns = np.array(self.returns, dtype=np.float32)
            ws_ok = self.ws_ok
            age_ms = int(max(0.0, now_ts - self.last_update) * 1000.0)

        micro_vol = float(np.std(returns)) if returns.size > 4 else 0.0
        spectral_energy = 0.0
        if returns.size >= 32:
            fft_vals = np.fft.rfft(returns, n=min(256, returns.size))
            mag = np.log1p(np.abs(fft_vals))
            spectral_energy = float(np.mean(mag[:64]))

        ema_tps = self.ema_tps.update(max(tps, 1e-6))
        ema_volps = self.ema_volps.update(max(volps, 1e-6))
        ema_spread = self.ema_spread.update(max(spread_bps, 1e-6))
        ema_micro = self.ema_micro.update(max(micro_vol, 1e-6))
        ema_spec = self.ema_spec.update(max(spectral_energy, 1e-6))

        norms = {
            "tps": clamp(tps / (ema_tps * 2.2)),
            "volps": clamp(volps / (ema_volps * 2.2)),
            "spread_bps": clamp(spread_bps / (ema_spread * 2.0)),
            "micro_vol": clamp(micro_vol / (ema_micro * 2.0)),
            "spectral_energy": clamp(spectral_energy / (ema_spec * 2.0)),
            "imbalance": clamp((imbalance + 1.0) / 2.0),
        }

        return FeatureSnapshot(
            tps=tps,
            volps=volps,
            spread_bps=spread_bps,
            imbalance=imbalance,
            micro_vol=micro_vol,
            direction=direction,
            spectral_energy=spectral_energy,
            mid=mid,
            age_ms=age_ms,
            ws_ok=ws_ok,
            norms=norms,
        )


def clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))
