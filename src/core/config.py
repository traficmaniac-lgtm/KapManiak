from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional


CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.json"
GOODS_PATH = Path(__file__).resolve().parents[2] / "goods.json"


@dataclass
class AppConfig:
    coin_to_adena: Optional[float] = None
    rub_per_1kk_buyer: Optional[float] = None
    funpay_fee: float = 0.15
    sbp_fee_effective: float = 0.1309
    withdraw_fee_pct: float = 0.06
    withdraw_fee_min_rub: float = 150.0
    withdraw_rate_rub_per_usdt: Optional[float] = None
    rub_per_usdt: Optional[float] = None


@dataclass
class GoodsItem:
    name: str
    price_coins: float
    created_at: str


def load_config() -> AppConfig:
    if not CONFIG_PATH.exists():
        return AppConfig()
    try:
        payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return AppConfig()
    if not isinstance(payload, dict):
        return AppConfig()
    rub_per_usdt = _to_optional_float(payload.get("rub_per_usdt"))
    withdraw_rate = _to_optional_float(payload.get("withdraw_rate_rub_per_usdt"))
    if withdraw_rate is None:
        withdraw_rate = rub_per_usdt
    return AppConfig(
        coin_to_adena=_to_optional_float(payload.get("coin_to_adena")),
        rub_per_1kk_buyer=_to_optional_float(payload.get("rub_per_1kk_buyer")),
        funpay_fee=_to_float(payload.get("funpay_fee"), 0.15),
        sbp_fee_effective=_to_float(payload.get("sbp_fee_effective"), 0.1309),
        withdraw_fee_pct=_to_float(payload.get("withdraw_fee_pct"), 0.06),
        withdraw_fee_min_rub=_to_float(payload.get("withdraw_fee_min_rub"), 150.0),
        withdraw_rate_rub_per_usdt=withdraw_rate,
        rub_per_usdt=rub_per_usdt,
    )


def save_config(config: AppConfig) -> None:
    CONFIG_PATH.write_text(json.dumps(asdict(config), ensure_ascii=False, indent=2), encoding="utf-8")


def load_goods() -> List[GoodsItem]:
    if not GOODS_PATH.exists():
        return []
    try:
        payload = json.loads(GOODS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    items: List[GoodsItem] = []
    for row in payload:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "Без названия")
        price_coins = _to_optional_float(row.get("price_coins"))
        created_at = str(row.get("created_at") or "")
        if price_coins is None or price_coins <= 0:
            continue
        items.append(GoodsItem(name=name, price_coins=price_coins, created_at=created_at))
    return items


def save_goods(items: List[GoodsItem]) -> None:
    payload = [asdict(item) for item in items]
    GOODS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def new_goods_item(name: str, price_coins: float) -> GoodsItem:
    return GoodsItem(
        name=name.strip() or "Без названия",
        price_coins=price_coins,
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


def _to_optional_float(value: object) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_float(value: object, fallback: float) -> float:
    try:
        if value is None or value == "":
            return fallback
        return float(value)
    except (TypeError, ValueError):
        return fallback
