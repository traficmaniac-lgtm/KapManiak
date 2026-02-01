from __future__ import annotations

import json
import sqlite3
from pathlib import Path


def _to_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False)


class SQLiteStorage:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._connection = sqlite3.connect(self.db_path)
        self._connection.execute("PRAGMA journal_mode=WAL;")

    def init_db(self) -> None:
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS ticks (
                ts INTEGER,
                prices_json TEXT,
                data_age_sec REAL
            );
            CREATE TABLE IF NOT EXISTS decisions (
                ts INTEGER,
                current_asset TEXT,
                leader_asset TEXT,
                decision TEXT,
                reasons_json TEXT,
                edge_pct REAL,
                net_edge_pct REAL,
                cost_pct REAL,
                confirm_k INTEGER,
                confirm_n INTEGER
            );
            CREATE TABLE IF NOT EXISTS trades_sim (
                ts INTEGER,
                from_asset TEXT,
                to_asset TEXT,
                v_before_usdt REAL,
                v_after_usdt REAL,
                cost_paid_usdt REAL,
                px_used REAL
            );
            CREATE TABLE IF NOT EXISTS equity_curve (
                ts INTEGER,
                equity_usdt REAL,
                asset TEXT,
                qty REAL
            );
            """
        )
        self._connection.commit()

    def insert_tick(self, ts_ms: int, prices: dict[str, float], data_age_sec: float | None) -> None:
        self._connection.execute(
            "INSERT INTO ticks (ts, prices_json, data_age_sec) VALUES (?, ?, ?)",
            (ts_ms, _to_json(prices), data_age_sec),
        )
        self._connection.commit()

    def insert_decision(
        self,
        ts_ms: int,
        current_asset: str,
        leader_asset: str,
        decision: str,
        reasons: list[str],
        edge_pct: float,
        net_edge_pct: float,
        cost_pct: float,
        confirm_k: int,
        confirm_n: int,
    ) -> None:
        self._connection.execute(
            """
            INSERT INTO decisions (
                ts,
                current_asset,
                leader_asset,
                decision,
                reasons_json,
                edge_pct,
                net_edge_pct,
                cost_pct,
                confirm_k,
                confirm_n
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ts_ms,
                current_asset,
                leader_asset,
                decision,
                _to_json(reasons),
                edge_pct,
                net_edge_pct,
                cost_pct,
                confirm_k,
                confirm_n,
            ),
        )
        self._connection.commit()

    def insert_trade_sim(
        self,
        ts_ms: int,
        from_asset: str,
        to_asset: str,
        v_before_usdt: float,
        v_after_usdt: float,
        cost_paid_usdt: float,
        px_used: float | None,
    ) -> None:
        self._connection.execute(
            """
            INSERT INTO trades_sim (
                ts,
                from_asset,
                to_asset,
                v_before_usdt,
                v_after_usdt,
                cost_paid_usdt,
                px_used
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ts_ms,
                from_asset,
                to_asset,
                v_before_usdt,
                v_after_usdt,
                cost_paid_usdt,
                px_used,
            ),
        )
        self._connection.commit()

    def insert_equity_curve(
        self,
        ts_ms: int,
        equity_usdt: float,
        asset: str,
        qty: float,
    ) -> None:
        self._connection.execute(
            "INSERT INTO equity_curve (ts, equity_usdt, asset, qty) VALUES (?, ?, ?, ?)",
            (ts_ms, equity_usdt, asset, qty),
        )
        self._connection.commit()

    def close(self) -> None:
        if self._connection:
            self._connection.close()


def ensure_db_path(db_path: str) -> str:
    path = Path(db_path)
    if path.parent and not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
    return str(path)
