from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class Settings:
    coin_to_adena: Optional[float]
    rub_per_1kk_buyer: Optional[float]
    funpay_fee: float
    sbp_fee_effective: float
    withdraw_markup_pct: float
    rub_per_usdt: Optional[float]


@dataclass
class QuickCalc:
    sbp_price_rub_buyer: Optional[float]
    fp_payout_rub_me: Optional[float]
    withdraw_rub: Optional[float]
    withdraw_usdt: Optional[float]


@dataclass
class ItemCalc:
    sbp_price_rub_buyer: Optional[float]
    fp_payout_rub_me: Optional[float]
    withdraw_usdt: Optional[float]
    withdraw_rub: Optional[float]


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
    sbp_price_rub_buyer = _calc_sbp_price(fp_payout_rub_me, settings.sbp_fee_effective)
    withdraw_rub = _calc_withdraw_rub(fp_payout_rub_me, settings.withdraw_markup_pct)

    if not _has_positive(settings.rub_per_usdt) or withdraw_rub is None:
        return QuickCalc(sbp_price_rub_buyer, fp_payout_rub_me, withdraw_rub, None)

    withdraw_usdt = withdraw_rub / settings.rub_per_usdt
    return QuickCalc(sbp_price_rub_buyer, fp_payout_rub_me, withdraw_rub, withdraw_usdt)


def calc_item(settings: Settings, price_coins: Optional[float]) -> ItemCalc:
    if not _has_positive(price_coins):
        return ItemCalc(None, None, None, None)
    rub_per_coin_buyer = calc_rub_per_coin_buyer(settings)
    if rub_per_coin_buyer is None:
        return ItemCalc(None, None, None, None)

    fp_price_rub_buyer = price_coins * rub_per_coin_buyer
    fp_payout_rub_me = fp_price_rub_buyer * (1 - settings.funpay_fee)
    sbp_price_rub_buyer = _calc_sbp_price(fp_payout_rub_me, settings.sbp_fee_effective)
    withdraw_rub = _calc_withdraw_rub(fp_payout_rub_me, settings.withdraw_markup_pct)

    if not _has_positive(settings.rub_per_usdt) or withdraw_rub is None:
        return ItemCalc(sbp_price_rub_buyer, fp_payout_rub_me, None, withdraw_rub)

    withdraw_usdt = withdraw_rub / settings.rub_per_usdt
    return ItemCalc(sbp_price_rub_buyer, fp_payout_rub_me, withdraw_usdt, withdraw_rub)


def _has_positive(value: Optional[float]) -> bool:
    return value is not None and value > 0


def _calc_sbp_price(me_rub: Optional[float], sbp_fee_effective: Optional[float]) -> Optional[float]:
    if me_rub is None or sbp_fee_effective is None:
        return None
    if sbp_fee_effective >= 1:
        return None
    return me_rub / (1 - sbp_fee_effective)


def _calc_withdraw_rub(me_rub: Optional[float], withdraw_markup_pct: Optional[float]) -> Optional[float]:
    if me_rub is None or withdraw_markup_pct is None:
        return None
    return me_rub * (1 + withdraw_markup_pct)
