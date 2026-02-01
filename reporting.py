from __future__ import annotations

import json
import os
import sqlite3
from collections import Counter
from typing import Any

import pandas as pd


def _load_table(db_path: str, query: str) -> pd.DataFrame:
    with sqlite3.connect(db_path) as connection:
        return pd.read_sql_query(query, connection)


def compute_summary(db_path: str, start_equity_usdt: float) -> dict[str, Any]:
    equity_df = _load_table(db_path, "SELECT * FROM equity_curve ORDER BY ts ASC")
    trades_df = _load_table(db_path, "SELECT * FROM trades_sim ORDER BY ts ASC")
    decisions_df = _load_table(db_path, "SELECT * FROM decisions ORDER BY ts ASC")

    if equity_df.empty:
        end_equity = start_equity_usdt
    else:
        end_equity = float(equity_df["equity_usdt"].iloc[-1])

    pnl_usdt = end_equity - start_equity_usdt
    pnl_pct = (pnl_usdt / start_equity_usdt * 100) if start_equity_usdt else 0.0

    switches_count = int(trades_df.shape[0])
    total_cost_paid_usdt = float(trades_df["cost_paid_usdt"].sum()) if not trades_df.empty else 0.0

    max_drawdown_pct = 0.0
    if not equity_df.empty:
        peak = float(equity_df["equity_usdt"].iloc[0])
        max_drawdown = 0.0
        for equity in equity_df["equity_usdt"].tolist():
            equity = float(equity)
            if equity > peak:
                peak = equity
            drawdown = (equity - peak) / peak if peak else 0.0
            max_drawdown = min(max_drawdown, drawdown)
        max_drawdown_pct = abs(max_drawdown) * 100

    ready_df = decisions_df[decisions_df["decision"] == "READY"]
    avg_edge_pct = float(ready_df["edge_pct"].mean()) if not ready_df.empty else 0.0
    avg_net_edge_pct = float(ready_df["net_edge_pct"].mean()) if not ready_df.empty else 0.0

    hold_df = decisions_df[decisions_df["decision"] == "HOLD"]
    reasons_counter: Counter[str] = Counter()
    if not hold_df.empty:
        for reasons_json in hold_df["reasons_json"].fillna("[]"):
            try:
                reasons = json.loads(reasons_json)
            except json.JSONDecodeError:
                reasons = []
            reasons_counter.update(reasons)

    top_reasons = reasons_counter.most_common(5)

    return {
        "start_equity_usdt": start_equity_usdt,
        "end_equity_usdt": end_equity,
        "pnl_usdt": pnl_usdt,
        "pnl_pct": pnl_pct,
        "switches_count": switches_count,
        "total_cost_paid_usdt": total_cost_paid_usdt,
        "max_drawdown_pct": max_drawdown_pct,
        "avg_edge_pct": avg_edge_pct,
        "avg_net_edge_pct": avg_net_edge_pct,
        "top_hold_reasons": [{"reason": reason, "count": count} for reason, count in top_reasons],
    }


def export_report(db_path: str, report_dir: str, start_equity_usdt: float) -> dict[str, Any]:
    os.makedirs(report_dir, exist_ok=True)

    equity_df = _load_table(db_path, "SELECT * FROM equity_curve ORDER BY ts ASC")
    trades_df = _load_table(db_path, "SELECT * FROM trades_sim ORDER BY ts ASC")

    equity_path = os.path.join(report_dir, "equity_curve.csv")
    trades_path = os.path.join(report_dir, "trades_sim.csv")
    summary_path = os.path.join(report_dir, "summary.json")

    equity_df.to_csv(equity_path, index=False)
    trades_df.to_csv(trades_path, index=False)

    summary = compute_summary(db_path, start_equity_usdt)
    with open(summary_path, "w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)

    return summary
