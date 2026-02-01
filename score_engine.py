from __future__ import annotations

import pandas as pd

from config import DEFAULT_CONFIG


def compute_scores(price_snapshot: dict[str, dict[str, float]]) -> pd.DataFrame:
    if not price_snapshot:
        return pd.DataFrame(
            columns=[
                "asset",
                "score",
                "ret_15m",
                "ret_1h",
                "ret_4h",
            ]
        )

    records = []
    for symbol, prices in price_snapshot.items():
        price_now = prices["price_now"]
        ret_15m = price_now / prices["price_15m_ago"] - 1
        ret_1h = price_now / prices["price_1h_ago"] - 1
        ret_4h = price_now / prices["price_4h_ago"] - 1
        score = 0.5 * ret_15m + 0.3 * ret_1h + 0.2 * ret_4h
        records.append(
            {
                "asset": symbol,
                "score": score,
                "ret_15m": ret_15m,
                "ret_1h": ret_1h,
                "ret_4h": ret_4h,
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

    df = df.copy()
    df["edge"] = df["score"] - current_score
    df["cost"] = DEFAULT_CONFIG.cost_pct
    df["net_edge"] = df["edge"] - df["cost"]
    return df
