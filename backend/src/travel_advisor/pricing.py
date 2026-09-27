"""Dynamic pricing engine — pure and deterministic.

``price_for`` starts from the route base fare and applies bounded multipliers for
seasonality, national holidays, and nearby events, then clamps to the route's
[floor, ceiling]. Holiday and event multipliers are always >= 1, so they can only
hold or raise the pre-clamp price (this is what makes properties P2/P3 hold).

Pricing behaviour is driven by :class:`~travel_advisor.models.PricingRules` loaded
from data, not hard-coded — add or change a rule by editing ``pricing-rules.json``,
not this module. The function stays pure: pass in the reference data (holiday flag,
events, rules); it reads no clock and no globals, so equal inputs always yield equal
output (P5).
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from .models import Event, Factor, PriceResult, PricingRules, Route

_CENTS = Decimal("0.01")


def seasonality_multiplier(travel_date: date, rules: PricingRules | None = None) -> float:
    """Bounded seasonal multiplier driven by month, per the pricing rules.

    Deterministic function of the month and the (data-driven) rules only.
    """
    rules = rules or PricingRules()
    if travel_date.month in rules.peak_months:
        return rules.peak_multiplier
    if travel_date.month in rules.low_months:
        return rules.low_multiplier
    return rules.shoulder_multiplier


def _quantize(amount: Decimal) -> Decimal:
    return amount.quantize(_CENTS, rounding=ROUND_HALF_UP)


def price_for(
    route: Route,
    travel_date: date,
    *,
    holiday: bool,
    events: list[Event] | None = None,
    rules: PricingRules | None = None,
) -> PriceResult:
    """Compute an explainable recommended price for ``route`` on ``travel_date``.

    Parameters
    ----------
    holiday:
        Whether ``travel_date`` is a national holiday in the destination market.
        Passed in (not looked up) to keep this function pure and testable.
    events:
        Events in the destination market to consider; only those within
        ``rules.proximity_days`` of ``travel_date`` apply.
    rules:
        Data-driven pricing rules. Defaults to :class:`PricingRules` defaults
        (which match the shipped ``pricing-rules.json``).
    """
    rules = rules or PricingRules()
    events = events or []
    factors: list[Factor] = []

    running = route.base_fare

    # 1. Seasonality (may raise or lower).
    season = seasonality_multiplier(travel_date, rules)
    running = running * Decimal(str(season))
    factors.append(Factor("seasonality", season, _season_reason(season)))

    # 2. National holiday (multiplier >= 1: never lowers pre-clamp price).
    if holiday:
        mult = 1.0 + rules.holiday_boost
        running = running * Decimal(str(mult))
        factors.append(
            Factor("holiday", mult, "national holiday in destination market")
        )

    # 3. Nearby events (each multiplier >= 1).
    for event in events:
        if abs((event.date - travel_date).days) <= rules.proximity_days:
            mult = 1.0 + event.impact
            running = running * Decimal(str(mult))
            factors.append(
                Factor("event", mult, f"{event.name} within {rules.proximity_days} days")
            )

    # 4. Clamp to route guardrails (req 2.2 / 2.3).
    clamped = min(max(running, route.floor), route.ceiling)

    return PriceResult(
        price=_quantize(clamped),
        base=route.base_fare,
        factors=tuple(factors),
    )


def _season_reason(season: float) -> str:
    if season > 1.0:
        return "peak season"
    if season < 1.0:
        return "low season"
    return "shoulder season"
