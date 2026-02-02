from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Optional, Tuple

import requests

PRIMARY_URL = "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usdt.json"
FALLBACK_URL = "https://latest.currency-api.pages.dev/v1/currencies/usdt.json"


@dataclass
class RateResult:
    rate: Optional[float]
    status: str
    timestamp: str
    source: str


def fetch_rate(timeout: float = 8.0) -> RateResult:
    timestamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    try:
        data = _fetch_json(PRIMARY_URL, timeout)
        rate = data.get("usdt", {}).get("rub")
        if isinstance(rate, (int, float)):
            return RateResult(rate=float(rate), status="OK", timestamp=timestamp, source="primary")
    except requests.RequestException:
        pass

    try:
        data = _fetch_json(FALLBACK_URL, timeout)
        rate = data.get("usdt", {}).get("rub")
        if isinstance(rate, (int, float)):
            return RateResult(rate=float(rate), status="OK", timestamp=timestamp, source="fallback")
    except requests.RequestException:
        pass

    return RateResult(rate=None, status="OFFLINE", timestamp=timestamp, source="cache")


def _fetch_json(url: str, timeout: float) -> dict:
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    return response.json()
