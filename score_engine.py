from __future__ import annotations

import math
import pandas as pd

from config import DEFAULT_CONFIG


def compute_scores(price_snapshot: dict[str, dict[str, float | None]]) -> pd.DataFrame:
    if not price_snapshot:
        return pd.DataFrame(
            columns=[
                "asset",
                "score",
                "ret_15m",
                "ret_1h",
                "ret_4h",
                "history_ok",
            ]
        )

    records = []
    for symbol, prices in price_snapshot.items():
        price_now = prices["price_now"]
        price_15m = prices["price_15m_ago"]
        price_1h = prices["price_1h_ago"]
        price_4h = prices["price_4h_ago"]
        history_ok = price_15m is not None and price_1h is not None and price_4h is not None
        if history_ok:
            ret_15m = price_now / price_15m - 1
            ret_1h = price_now / price_1h - 1
            ret_4h = price_now / price_4h - 1
            score = 0.5 * ret_15m + 0.3 * ret_1h + 0.2 * ret_4h
        else:
            ret_15m = math.nan
            ret_1h = math.nan
            ret_4h = math.nan
            score = math.nan
        records.append(
            {
                "asset": symbol,
                "score": score,
                "ret_15m": ret_15m,
                "ret_1h": ret_1h,
                "ret_4h": ret_4h,
                "history_ok": history_ok,
            }
        )

    df = pd.DataFrame.from_records(records)
    df.sort_values(by="score", ascending=False, inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def apply_costs(df: pd.DataFrame, current_asset: str) -> pd.DataFrame:
    current_score = 0.0
    if current_asset in df["asset"].values:
        current_score = float(df.loc[df["asset"] == current_asset, "score"].iloc[0])
        if math.isnan(current_score):
            current_score = 0.0

    df = df.copy()
    df["edge"] = df["score"] - current_score
    df["cost"] = DEFAULT_CONFIG.cost_pct
    df["net_edge"] = df["edge"] - df["cost"]
    return df
