from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QSettings

from src.core.calc import Params, ItemResult, deserialize_item


class Storage:
    def __init__(self) -> None:
        self.settings = QSettings("KapManiak", "L2 Trade Helper")
        self.data_dir = Path(__file__).resolve().parents[2] / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.goods_path = self.data_dir / "goods.json"

    def load_params(self) -> Params:
        fee_fp = self._get_float("fee_fp", 0.15)
        fee_withdraw = self._get_float("fee_withdraw", 0.21)
        coins_in = self._get_float("coins_in", 1000)
        return Params(
            coin_per_1kkA=self._get_float("coin_per_1kkA"),
            fp_buyer_rub_per_1kkA=self._get_float("fp_buyer_rub_per_1kkA"),
            fee_fp=fee_fp if fee_fp is not None else 0.15,
            fee_withdraw=fee_withdraw if fee_withdraw is not None else 0.21,
            coins_in=coins_in if coins_in is not None else 1000,
            rub_per_usdt=self._get_float("rub_per_usdt"),
        )

    def save_params(self, params: Params) -> None:
        for key, value in asdict(params).items():
            if value is None:
                self.settings.remove(key)
            else:
                self.settings.setValue(key, float(value))

    def load_goods(self) -> List[Dict[str, Any]]:
        if not self.goods_path.exists():
            return []
        with self.goods_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return payload if isinstance(payload, list) else []

    def save_goods(self, goods: List[Dict[str, Any]]) -> None:
        with self.goods_path.open("w", encoding="utf-8") as handle:
            json.dump(goods, handle, ensure_ascii=False, indent=2)

    def load_rate_timestamp(self) -> Optional[str]:
        value = self.settings.value("rate_timestamp")
        return str(value) if value else None

    def save_rate(self, rate: float, timestamp: str) -> None:
        self.settings.setValue("rub_per_usdt", float(rate))
        self.settings.setValue("rate_timestamp", timestamp)

    def _get_float(self, key: str, fallback: Optional[float] = None) -> Optional[float]:
        value = self.settings.value(key)
        if value is None or value == "":
            return fallback
        try:
            return float(value)
        except (TypeError, ValueError):
            return fallback


def hydrate_goods(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for row in rows:
        if "calc" in row and isinstance(row["calc"], dict):
            item = deserialize_item(row["calc"])
            row["calc"] = item
        items.append(row)
    return items


def serialize_goods(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    payload: List[Dict[str, Any]] = []
    for row in rows:
        item = row.get("calc")
        if isinstance(item, ItemResult):
            row = dict(row)
            row["calc"] = {
                "item_coins": item.item_coins,
                "item_cost_rub": item.item_cost_rub,
                "item_adena_kk": item.item_adena_kk,
                "item_fp_buyer_rub": item.item_fp_buyer_rub,
                "item_fp_you_rub": item.item_fp_you_rub,
                "item_usdt_net": item.item_usdt_net,
                "profit_rub": item.profit_rub,
                "profit_usdt": item.profit_usdt,
            }
        payload.append(row)
    return payload
