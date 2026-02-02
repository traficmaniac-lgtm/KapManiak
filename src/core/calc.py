from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class Settings:
    coin_to_adena: Optional[float]
    rub_per_1kk_buyer: Optional[float]
    funpay_fee: float
    usdt_withdraw_fee: float
    rub_per_usdt: Optional[float]


@dataclass
class QuickCalc:
    fp_price_rub_buyer: Optional[float]
    fp_payout_rub_me: Optional[float]
    withdraw_rub_equiv: Optional[float]
    withdraw_usdt: Optional[float]


@dataclass
class ItemCalc:
    fp_price_rub_buyer: Optional[float]
    fp_payout_rub_me: Optional[float]
    withdraw_usdt: Optional[float]
    withdraw_rub_equiv: Optional[float]


def calc_rub_per_coin_buyer(settings: Settings) -> Optional[float]:
    if not _has_positive(settings.coin_to_adena) or not _has_positive(settings.rub_per_1kk_buyer):
        return None
    rub_per_1_adena = settings.rub_per_1kk_buyer / 1_000_000
    return settings.coin_to_adena * rub_per_1_adena


def calc_quick(settings: Settings, coins_qty: Optional[float]) -> QuickCalc:
    if not _has_positive(coins_qty):
        return QuickCalc(None, None, None, None)
    rub_per_coin_buyer = calc_rub_per_coin_buyer(settings)
    if rub_per_coin_buyer is None:
        return QuickCalc(None, None, None, None)

    fp_price_rub_buyer = coins_qty * rub_per_coin_buyer
    fp_payout_rub_me = fp_price_rub_buyer * (1 - settings.funpay_fee)

    if not _has_positive(settings.rub_per_usdt):
        return QuickCalc(fp_price_rub_buyer, fp_payout_rub_me, None, None)

    usdt_before_withdraw = fp_payout_rub_me / settings.rub_per_usdt
    withdraw_usdt = usdt_before_withdraw * (1 - settings.usdt_withdraw_fee)
    withdraw_rub_equiv = withdraw_usdt * settings.rub_per_usdt
    return QuickCalc(fp_price_rub_buyer, fp_payout_rub_me, withdraw_rub_equiv, withdraw_usdt)


def calc_item(settings: Settings, price_coins: Optional[float]) -> ItemCalc:
    if not _has_positive(price_coins):
        return ItemCalc(None, None, None, None)
    rub_per_coin_buyer = calc_rub_per_coin_buyer(settings)
    if rub_per_coin_buyer is None:
        return ItemCalc(None, None, None, None)

    fp_price_rub_buyer = price_coins * rub_per_coin_buyer
    fp_payout_rub_me = fp_price_rub_buyer * (1 - settings.funpay_fee)

    if not _has_positive(settings.rub_per_usdt):
        return ItemCalc(fp_price_rub_buyer, fp_payout_rub_me, None, None)

    withdraw_usdt = (fp_payout_rub_me / settings.rub_per_usdt) * (1 - settings.usdt_withdraw_fee)
    withdraw_rub_equiv = withdraw_usdt * settings.rub_per_usdt
    return ItemCalc(fp_price_rub_buyer, fp_payout_rub_me, withdraw_usdt, withdraw_rub_equiv)


def _has_positive(value: Optional[float]) -> bool:
    return value is not None and value > 0
