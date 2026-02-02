from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class Settings:
    coin_to_adena: Optional[float]
    rub_per_1kk_buyer: Optional[float]
    funpay_fee: float
    sbp_fee_effective: float
    k_card_ru: float
    k_sbp_qr: float
    withdraw_fee_pct: float
    withdraw_fee_min_rub: float
    withdraw_rate_rub_per_usdt: Optional[float]
    rub_per_usdt: Optional[float]


@dataclass
class QuickCalc:
    fp_payout_rub_me: Optional[float]
    base_rub: Optional[float]
    card_rub: Optional[float]
    sbp_rub: Optional[float]
    withdraw_amount_rub: Optional[float]
    withdraw_fee_rub: Optional[float]
    withdraw_rub: Optional[float]
    withdraw_usdt: Optional[float]


@dataclass
class ItemCalc:
    fp_payout_rub_me: Optional[float]
    base_rub: Optional[float]
    card_rub: Optional[float]
    sbp_rub: Optional[float]
    withdraw_amount_rub: Optional[float]
    withdraw_usdt: Optional[float]
    withdraw_rub: Optional[float]


def calc_rub_per_coin_buyer(settings: Settings) -> Optional[float]:
    if not _has_positive(settings.coin_to_adena) or not _has_positive(settings.rub_per_1kk_buyer):
        return None
    rub_per_1_adena = settings.rub_per_1kk_buyer / 1_000_000
    return settings.coin_to_adena * rub_per_1_adena


def calc_quick(
    settings: Settings,
    coins_qty: Optional[float],
    base_rub_override: Optional[float],
    withdraw_amount_override: Optional[float],
) -> QuickCalc:
    if not _has_positive(coins_qty):
        return QuickCalc(None, None, None, None, None, None, None, None)
    rub_per_coin_buyer = calc_rub_per_coin_buyer(settings)
    if rub_per_coin_buyer is None:
        return QuickCalc(None, None, None, None, None, None, None, None)

    fp_price_rub_buyer = coins_qty * rub_per_coin_buyer
    fp_payout_rub_me = fp_price_rub_buyer * (1 - settings.funpay_fee)
    base_rub = base_rub_override if _has_positive(base_rub_override) else fp_payout_rub_me
    card_rub = base_rub * settings.k_card_ru if _has_positive(base_rub) else None
    sbp_rub = base_rub * settings.k_sbp_qr if _has_positive(base_rub) else None
    withdraw_amount_rub = (
        withdraw_amount_override if _has_positive(withdraw_amount_override) else fp_payout_rub_me
    )
    fee_rub, withdraw_rub = _calc_withdraw_breakdown(
        withdraw_amount_rub,
        settings.withdraw_fee_pct,
        settings.withdraw_fee_min_rub,
    )

    if not _has_positive(settings.withdraw_rate_rub_per_usdt) or withdraw_rub is None:
        return QuickCalc(
            fp_payout_rub_me,
            base_rub,
            card_rub,
            sbp_rub,
            withdraw_amount_rub,
            fee_rub,
            withdraw_rub,
            None,
        )

    withdraw_usdt = withdraw_rub / settings.withdraw_rate_rub_per_usdt
    return QuickCalc(
        fp_payout_rub_me,
        base_rub,
        card_rub,
        sbp_rub,
        withdraw_amount_rub,
        fee_rub,
        withdraw_rub,
        withdraw_usdt,
    )


def calc_item(settings: Settings, price_coins: Optional[float]) -> ItemCalc:
    if not _has_positive(price_coins):
        return ItemCalc(None, None, None, None, None, None)
    rub_per_coin_buyer = calc_rub_per_coin_buyer(settings)
    if rub_per_coin_buyer is None:
        return ItemCalc(None, None, None, None, None, None)

    fp_price_rub_buyer = price_coins * rub_per_coin_buyer
    fp_payout_rub_me = fp_price_rub_buyer * (1 - settings.funpay_fee)
    base_rub = fp_payout_rub_me
    card_rub = base_rub * settings.k_card_ru if _has_positive(base_rub) else None
    sbp_rub = base_rub * settings.k_sbp_qr if _has_positive(base_rub) else None
    withdraw_amount_rub = fp_payout_rub_me
    _, withdraw_rub = _calc_withdraw_breakdown(
        withdraw_amount_rub,
        settings.withdraw_fee_pct,
        settings.withdraw_fee_min_rub,
    )

    if not _has_positive(settings.withdraw_rate_rub_per_usdt) or withdraw_rub is None:
        return ItemCalc(fp_payout_rub_me, base_rub, card_rub, sbp_rub, withdraw_amount_rub, None, withdraw_rub)

    withdraw_usdt = withdraw_rub / settings.withdraw_rate_rub_per_usdt
    return ItemCalc(
        fp_payout_rub_me,
        base_rub,
        card_rub,
        sbp_rub,
        withdraw_amount_rub,
        withdraw_usdt,
        withdraw_rub,
    )


def _has_positive(value: Optional[float]) -> bool:
    return value is not None and value > 0


def _calc_withdraw_breakdown(
    me_rub: Optional[float],
    withdraw_fee_pct: Optional[float],
    withdraw_fee_min_rub: Optional[float],
) -> tuple[Optional[float], Optional[float]]:
    if me_rub is None or withdraw_fee_pct is None or withdraw_fee_min_rub is None:
        return None, None
    fee_rub = max(me_rub * withdraw_fee_pct, withdraw_fee_min_rub)
    net_rub = me_rub - fee_rub
    return fee_rub, net_rub
