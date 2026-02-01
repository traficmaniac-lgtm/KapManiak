from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class SwitchRecord:
    timestamp: float
    from_asset: str
    to_asset: str
    reason: str
    equity_usdt: float
    edge_pct: Optional[float]
    net_edge_pct: Optional[float]


class Storage:
    """SQLite storage for equity curve and switches."""

    def __init__(self, logger) -> None:
        self._logger = logger
        self._path = os.path.join("data", "kapmaniak.sqlite")
        os.makedirs("data", exist_ok=True)
        self._conn = sqlite3.connect(self._path)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS equity_curve (
                timestamp REAL NOT NULL,
                asset TEXT NOT NULL,
                equity_usdt REAL NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS switches (
                timestamp REAL NOT NULL,
                from_asset TEXT NOT NULL,
                to_asset TEXT NOT NULL,
                reason TEXT NOT NULL,
                equity_usdt REAL NOT NULL,
                edge_pct REAL,
                net_edge_pct REAL
            )
            """
        )
        self._conn.commit()

    def append_equity(self, timestamp: float, asset: str, equity_usdt: float) -> None:
        self._conn.execute(
            "INSERT INTO equity_curve (timestamp, asset, equity_usdt) VALUES (?, ?, ?)",
            (timestamp, asset, equity_usdt),
        )
        self._conn.commit()

    def append_switch(
        self,
        timestamp: float,
        from_asset: str,
        to_asset: str,
        reason: str,
        equity_usdt: float,
        edge_pct: Optional[float],
        net_edge_pct: Optional[float],
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO switches (timestamp, from_asset, to_asset, reason, equity_usdt, edge_pct, net_edge_pct)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (timestamp, from_asset, to_asset, reason, equity_usdt, edge_pct, net_edge_pct),
        )
        self._conn.commit()

    def load_equity(self) -> List[Tuple[float, str, float]]:
        cursor = self._conn.execute(
            "SELECT timestamp, asset, equity_usdt FROM equity_curve ORDER BY timestamp DESC LIMIT 1000"
        )
        return cursor.fetchall()

    def load_switches(self) -> List[SwitchRecord]:
        cursor = self._conn.execute(
            """
            SELECT timestamp, from_asset, to_asset, reason, equity_usdt, edge_pct, net_edge_pct
            FROM switches
            ORDER BY timestamp DESC
            LIMIT 500
            """
        )
        return [SwitchRecord(*row) for row in cursor.fetchall()]

    def close(self) -> None:
        self._conn.close()
