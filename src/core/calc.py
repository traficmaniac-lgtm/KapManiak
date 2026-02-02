from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

RUB_PER_COIN = 400 / 3200


@dataclass
class Params:
    coin_per_1kkA: Optional[float]
    fp_buyer_rub_per_1kkA: Optional[float]
    fee_fp: float
    fee_withdraw: float
    coins_in: Optional[float]
    rub_per_usdt: Optional[float]


@dataclass
class CalcResult:
    donate_rub: Optional[float]
    adena_kk: Optional[float]
    sum_fp_buyer_rub: Optional[float]
    sum_fp_you_rub: Optional[float]
    sum_fp_you_usdt: Optional[float]
    profit_rub: Optional[float]
    profit_usdt: Optional[float]


@dataclass
class ItemResult:
    item_coins: float
    item_cost_rub: float
    item_adena_kk: float
    item_fp_buyer_rub: float
    item_fp_you_rub: float
    item_usdt_net: float
    profit_rub: float
    profit_usdt: float


def _safe_div(numerator: float, denominator: Optional[float]) -> Optional[float]:
    if denominator is None or denominator == 0:
        return None
    return numerator / denominator


def calc_summary(params: Params) -> CalcResult:
    if params.coins_in is None:
        return CalcResult(None, None, None, None, None, None, None)
    donate_rub = params.coins_in * RUB_PER_COIN

    adena_kk = _safe_div(params.coins_in, params.coin_per_1kkA)
    sum_fp_buyer_rub = None
    sum_fp_you_rub = None
    sum_fp_you_usdt = None
    profit_rub = None
    profit_usdt = None

    if adena_kk is not None and params.fp_buyer_rub_per_1kkA is not None:
        sum_fp_buyer_rub = adena_kk * params.fp_buyer_rub_per_1kkA
        sum_fp_you_rub = sum_fp_buyer_rub * (1 - params.fee_fp)
        if params.rub_per_usdt:
            sum_fp_you_usdt = (sum_fp_you_rub / params.rub_per_usdt) * (1 - params.fee_withdraw)
            profit_usdt = sum_fp_you_usdt - (donate_rub / params.rub_per_usdt)
        profit_rub = sum_fp_you_rub - donate_rub

    return CalcResult(
        donate_rub=donate_rub,
        adena_kk=adena_kk,
        sum_fp_buyer_rub=sum_fp_buyer_rub,
        sum_fp_you_rub=sum_fp_you_rub,
        sum_fp_you_usdt=sum_fp_you_usdt,
        profit_rub=profit_rub,
        profit_usdt=profit_usdt,
    )


def calc_item_forward(params: Params, item_coins: float) -> Optional[ItemResult]:
    if params.coin_per_1kkA is None or params.fp_buyer_rub_per_1kkA is None:
        return None
    if params.rub_per_usdt is None:
        return None

    item_cost_rub = item_coins * RUB_PER_COIN
    item_adena_kk = item_coins / params.coin_per_1kkA
    item_fp_buyer_rub = item_adena_kk * params.fp_buyer_rub_per_1kkA
    item_fp_you_rub = item_fp_buyer_rub * (1 - params.fee_fp)
    item_usdt_net = (item_fp_you_rub / params.rub_per_usdt) * (1 - params.fee_withdraw)
    profit_rub = item_fp_you_rub - item_cost_rub
    profit_usdt = item_usdt_net - (item_cost_rub / params.rub_per_usdt)

    return ItemResult(
        item_coins=item_coins,
        item_cost_rub=item_cost_rub,
        item_adena_kk=item_adena_kk,
        item_fp_buyer_rub=item_fp_buyer_rub,
        item_fp_you_rub=item_fp_you_rub,
        item_usdt_net=item_usdt_net,
        profit_rub=profit_rub,
        profit_usdt=profit_usdt,
    )


def calc_item_inverse(params: Params, usdt_net: float) -> Optional[ItemResult]:
    if params.fp_buyer_rub_per_1kkA is None or params.coin_per_1kkA is None:
        return None
    if params.rub_per_usdt is None:
        return None

    fp_you_rub = (usdt_net / (1 - params.fee_withdraw)) * params.rub_per_usdt
    fp_buyer_rub = fp_you_rub / (1 - params.fee_fp)
    item_adena_kk = fp_buyer_rub / params.fp_buyer_rub_per_1kkA
    item_coins = item_adena_kk * params.coin_per_1kkA

    return calc_item_forward(params, item_coins)


def serialize_item(item: ItemResult) -> Dict[str, float]:
    return {
        "item_coins": item.item_coins,
        "item_cost_rub": item.item_cost_rub,
        "item_adena_kk": item.item_adena_kk,
        "item_fp_buyer_rub": item.item_fp_buyer_rub,
        "item_fp_you_rub": item.item_fp_you_rub,
        "item_usdt_net": item.item_usdt_net,
        "profit_rub": item.profit_rub,
        "profit_usdt": item.profit_usdt,
    }


def deserialize_item(payload: Dict[str, float]) -> ItemResult:
    return ItemResult(
        item_coins=payload["item_coins"],
        item_cost_rub=payload["item_cost_rub"],
        item_adena_kk=payload["item_adena_kk"],
        item_fp_buyer_rub=payload["item_fp_buyer_rub"],
        item_fp_you_rub=payload["item_fp_you_rub"],
        item_usdt_net=payload["item_usdt_net"],
        profit_rub=payload["profit_rub"],
        profit_usdt=payload["profit_usdt"],
    )
