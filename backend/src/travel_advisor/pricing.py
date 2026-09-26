"""Dynamic pricing engine — pure and deterministic.

``price_for`` starts from the route base fare and applies bounded multipliers for
seasonality, national holidays, and nearby events, then clamps to the route's
[floor, ceiling]. Holiday and event multipliers are always >= 1, so they can only
hold or raise the pre-clamp price (this is what makes properties P2/P3 hold).

The function is pure: pass in the reference data (holiday flag, events); it reads
no clock, no files, and no globals, so equal inputs always yield equal output (P5).
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from .models import Event, Factor, PriceResult, Route

# Tunable, but fixed at import time so results stay deterministic.
DEFAULT_HOLIDAY_BOOST = 0.10  # +10% on a national holiday
DEFAULT_PROXIMITY_DAYS = 3  # events within +/- N days of travel date count
_CENTS = Decimal("0.01")


def seasonality_multiplier(travel_date: date) -> float:
    """Bounded seasonal multiplier in [0.9, 1.2] driven by month.

    Summer (Jun-Aug) and December peak; deep winter (Jan-Feb) troughs. Deterministic
    function of the month only.
    """
    peak_months = {6, 7, 8, 12}
    low_months = {1, 2, 11}
    if travel_date.month in peak_months:
        return 1.20
    if travel_date.month in low_months:
        return 0.90
    return 1.00


def _quantize(amount: Decimal) -> Decimal:
    return amount.quantize(_CENTS, rounding=ROUND_HALF_UP)


def price_for(
    route: Route,
    travel_date: date,
    *,
    holiday: bool,
    events: list[Event] | None = None,
    holiday_boost: float = DEFAULT_HOLIDAY_BOOST,
    proximity_days: int = DEFAULT_PROXIMITY_DAYS,
) -> PriceResult:
    """Compute an explainable recommended price for ``route`` on ``travel_date``.

    Parameters
    ----------
    holiday:
        Whether ``travel_date`` is a national holiday in the destination market.
        Passed in (not looked up) to keep this function pure and testable.
    events:
        Events in the destination market to consider; only those within
        ``proximity_days`` of ``travel_date`` apply.
    """
    events = events or []
    factors: list[Factor] = []

    running = route.base_fare

    # 1. Seasonality (may raise or lower).
    season = seasonality_multiplier(travel_date)
    running = running * Decimal(str(season))
    factors.append(
        Factor("seasonality", season, _season_reason(travel_date, season))
    )

    # 2. National holiday (multiplier >= 1: never lowers pre-clamp price).
    if holiday:
        mult = 1.0 + holiday_boost
        running = running * Decimal(str(mult))
        factors.append(
            Factor("holiday", mult, "national holiday in destination market")
        )

    # 3. Nearby events (each multiplier >= 1).
    for event in events:
        if abs((event.date - travel_date).days) <= proximity_days:
            mult = 1.0 + event.impact
            running = running * Decimal(str(mult))
            factors.append(
                Factor("event", mult, f"{event.name} within {proximity_days} days")
            )

    # 4. Clamp to route guardrails (req 2.2 / 2.3).
    clamped = min(max(running, route.floor), route.ceiling)

    return PriceResult(
        price=_quantize(clamped),
        base=route.base_fare,
        factors=tuple(factors),
    )


def _season_reason(travel_date: date, season: float) -> str:
    if season > 1.0:
        return "peak season"
    if season < 1.0:
        return "low season"
    return "shoulder season"
