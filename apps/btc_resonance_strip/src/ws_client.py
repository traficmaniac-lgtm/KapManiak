from __future__ import annotations

import json
import threading
import time
from typing import Any, Dict

import websocket

from features import FeatureState


class BinanceWSClient(threading.Thread):
    def __init__(self, state: FeatureState) -> None:
        super().__init__(daemon=True)
        self.state = state
        self.stop_event = threading.Event()
        self.url = (
            "wss://stream.binance.com:9443/stream?streams="
            "btcusdt@bookTicker/btcusdt@aggTrade/btcusdt@depth20@100ms"
        )

    def stop(self) -> None:
        self.stop_event.set()

    def run(self) -> None:
        backoff = 1.0
        while not self.stop_event.is_set():
            ws_app = websocket.WebSocketApp(
                self.url,
                on_message=self._on_message,
                on_open=self._on_open,
                on_close=self._on_close,
                on_error=self._on_error,
            )
            ws_app.run_forever(ping_interval=20, ping_timeout=10)
            if self.stop_event.is_set():
                break
            time.sleep(backoff)
            backoff = min(backoff * 1.5, 10.0)

    def _on_open(self, ws: websocket.WebSocketApp) -> None:
        self.state.update_connection(True)

    def _on_close(self, ws: websocket.WebSocketApp, status_code: int, msg: str) -> None:
        self.state.update_connection(False)

    def _on_error(self, ws: websocket.WebSocketApp, error: Exception) -> None:
        self.state.update_connection(False)

    def _on_message(self, ws: websocket.WebSocketApp, message: str) -> None:
        try:
            payload: Dict[str, Any] = json.loads(message)
        except json.JSONDecodeError:
            return

        stream = payload.get("stream", "")
        data = payload.get("data", {})
        if "bookTicker" in stream:
            bid = float(data.get("b", 0.0))
            ask = float(data.get("a", 0.0))
            ts = data.get("E", int(time.time() * 1000)) / 1000.0
            self.state.update_book(bid, ask, ts)
        elif "aggTrade" in stream:
            qty = float(data.get("q", 0.0))
            ts = data.get("T", int(time.time() * 1000)) / 1000.0
            self.state.update_trade(qty, ts)
        elif "depth20" in stream:
            bids = [(float(price), float(qty)) for price, qty in data.get("b", [])]
            asks = [(float(price), float(qty)) for price, qty in data.get("a", [])]
            ts = data.get("E", int(time.time() * 1000)) / 1000.0
            self.state.update_depth(bids, asks, ts)
