import json
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, Optional

import websocket

WS_URL = (
    "wss://stream.binance.com:9443/stream?streams="
    "btcusdt@bookTicker/btcusdt@aggTrade/btcusdt@depth20@100ms"
)


@dataclass
class WSDataStore:
    lock: threading.Lock = field(default_factory=threading.Lock)
    book_ticker: Optional[Dict] = None
    depth: Optional[Dict] = None
    trades: Deque[Dict] = field(default_factory=lambda: deque(maxlen=2000))
    book_ticks: Deque[float] = field(default_factory=lambda: deque(maxlen=2000))
    depth_ticks: Deque[float] = field(default_factory=lambda: deque(maxlen=2000))
    trade_ticks: Deque[float] = field(default_factory=lambda: deque(maxlen=4000))
    status: str = "DISCONNECTED"
    last_message_ts: float = 0.0

    def update_status(self, status: str) -> None:
        with self.lock:
            self.status = status

    def push_trade(self, trade: Dict) -> None:
        with self.lock:
            self.trades.append(trade)
            self.trade_ticks.append(time.time())
            self.last_message_ts = time.time()

    def set_book_ticker(self, data: Dict) -> None:
        with self.lock:
            self.book_ticker = data
            self.book_ticks.append(time.time())
            self.last_message_ts = time.time()

    def set_depth(self, data: Dict) -> None:
        with self.lock:
            self.depth = data
            self.depth_ticks.append(time.time())
            self.last_message_ts = time.time()

    def get_diagnostics(self) -> Dict[str, float]:
        now = time.time()
        with self.lock:
            self._prune_ticks(self.book_ticks, now)
            self._prune_ticks(self.depth_ticks, now)
            self._prune_ticks(self.trade_ticks, now)
            last_age_ms = (now - self.last_message_ts) * 1000.0 if self.last_message_ts else -1.0
            return {
                "ws_connected": self.status == "LIVE",
                "last_msg_age_ms": last_age_ms,
                "book_count": float(len(self.book_ticks)),
                "depth_count": float(len(self.depth_ticks)),
                "trade_count": float(len(self.trade_ticks)),
                "status": self.status,
            }

    @staticmethod
    def _prune_ticks(ticks: Deque[float], now: float, window: float = 2.0) -> None:
        while ticks and now - ticks[0] > window:
            ticks.popleft()


class WSClient(threading.Thread):
    def __init__(self, store: WSDataStore, reconnect_delay: float = 3.0) -> None:
        super().__init__(daemon=True)
        self.store = store
        self.reconnect_delay = reconnect_delay
        self._stop_event = threading.Event()
        self._ws: Optional[websocket.WebSocketApp] = None

    def stop(self) -> None:
        self._stop_event.set()
        if self._ws is not None:
            try:
                self._ws.close()
            except Exception:
                pass

    def run(self) -> None:
        while not self._stop_event.is_set():
            self._connect_once()
            if not self._stop_event.is_set():
                time.sleep(self.reconnect_delay)

    def _connect_once(self) -> None:
        self.store.update_status("CONNECTING")

        def on_open(_ws) -> None:
            self.store.update_status("LIVE")

        def on_message(_ws, message: str) -> None:
            try:
                payload = json.loads(message)
            except json.JSONDecodeError:
                return
            data = payload.get("data", {})
            stream = payload.get("stream", "")
            if stream.endswith("@bookTicker"):
                self.store.set_book_ticker(data)
            elif stream.endswith("@aggTrade"):
                self.store.push_trade(data)
            elif "@depth20" in stream:
                self.store.set_depth(data)

        def on_error(_ws, _error) -> None:
            self.store.update_status("ERROR")

        def on_close(_ws, _code, _msg) -> None:
            self.store.update_status("DISCONNECTED")

        self._ws = websocket.WebSocketApp(
            WS_URL,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
        )
        try:
            self._ws.run_forever(ping_interval=20, ping_timeout=10)
        except Exception:
            self.store.update_status("ERROR")
        finally:
            try:
                self._ws.close()
            except Exception:
                pass
