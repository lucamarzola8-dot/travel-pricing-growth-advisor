"""Dynamic pricing engine — pure and deterministic.

``price_for`` starts from the route base fare and applies bounded multipliers for
seasonality, day of week, booking lead time, national holidays, and nearby events,
then clamps to the route's [floor, ceiling]. Seasonality and day-of-week may raise
or lower the price; lead-time, holiday, and event multipliers are always >= 1, so
they can only hold or raise the pre-clamp price (this is what makes properties
P2/P3 hold). Seasonality and day-of-week are always-present time factors derived
from the travel date; lead-time only applies when a reference ("today") date is
supplied, keeping the function pure otherwise.

Event impact is not an on/off step: it is strongest on the event day and fades
linearly to 0 at the edge of the proximity window (see ``event_proximity_weight``),
so demand ramps toward a peak and neighbouring days get distinct prices.

Pricing behaviour is driven by :class:`~travel_advisor.models.PricingRules` loaded
from data, not hard-coded — add or change a rule by editing ``pricing-rules.json``,
not this module. The function stays pure: pass in the reference data (holiday flag,
events, rules); it reads no clock and no globals, so equal inputs always yield equal
output (P5).
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from .models import BreakdownItem, Event, Factor, PriceResult, PricingRules, Route

_CENTS = Decimal("0.01")


_WEEKDAY_NAMES = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)


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


def day_of_week_multiplier(travel_date: date, rules: PricingRules | None = None) -> float:
    """Weekday multiplier (Mon..Sun) driven by the pricing rules.

    Models that weekend departures sell higher than mid-week ones. Deterministic
    function of the weekday and the (data-driven) rules only.
    """
    rules = rules or PricingRules()
    return rules.dow_multipliers[travel_date.weekday()]


def event_proximity_weight(distance_days: int, proximity_days: int) -> float:
    """Linear proximity weight in ``[0, 1]`` for an event ``distance_days`` away.

    1.0 on the event day, fading linearly to 0 just past ``proximity_days`` out
    (0 for anything at or beyond ``proximity_days + 1``). This turns the event
    boost into a ramp toward a demand peak instead of an on/off step, and is a
    pure function of the two integers. ``proximity_days == 0`` means only the
    event day itself carries weight.
    """
    window = proximity_days + 1
    if distance_days >= window:
        return 0.0
    return (window - distance_days) / window


def lead_time_multiplier(
    travel_date: date,
    reference_date: date,
    rules: PricingRules | None = None,
) -> float:
    """Advance-purchase multiplier: near-term departures cost more.

    Returns ``1 + boost`` where ``boost`` is ``lead_time_boost`` for a same-day
    departure, decaying linearly to 0 at ``lead_time_days`` out and staying 1.0
    beyond that. Departures in the past (before ``reference_date``) get the full
    boost. Deterministic function of the two dates and the rules only.
    """
    rules = rules or PricingRules()
    if rules.lead_time_boost <= 0:
        return 1.0
    days_out = (travel_date - reference_date).days
    if days_out >= rules.lead_time_days:
        return 1.0
    if days_out <= 0:
        return 1.0 + rules.lead_time_boost
    remaining = (rules.lead_time_days - days_out) / rules.lead_time_days
    return 1.0 + rules.lead_time_boost * remaining


def _quantize(amount: Decimal) -> Decimal:
    return amount.quantize(_CENTS, rounding=ROUND_HALF_UP)


def price_for(
    route: Route,
    travel_date: date,
    *,
    holiday: bool,
    events: list[Event] | None = None,
    rules: PricingRules | None = None,
    reference_date: date | None = None,
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
    reference_date:
        The "today" / booking date used for the advance-purchase (lead-time)
        factor. When ``None`` the lead-time factor is skipped, keeping the
        function a pure function of ``travel_date`` alone for callers that don't
        model booking horizon.
    """
    rules = rules or PricingRules()
    events = events or []
    factors: list[Factor] = []

    running = route.base_fare

    # 1. Seasonality (may raise or lower).
    season = seasonality_multiplier(travel_date, rules)
    running = running * Decimal(str(season))
    factors.append(Factor("seasonality", season, _season_reason(season)))

    # 2. Day of week (may raise or lower): weekend departures priced higher.
    dow = day_of_week_multiplier(travel_date, rules)
    running = running * Decimal(str(dow))
    factors.append(
        Factor("day_of_week", dow, _dow_reason(travel_date, dow))
    )

    # 3. Booking lead time (multiplier >= 1): near-term departures cost more.
    if reference_date is not None:
        lead = lead_time_multiplier(travel_date, reference_date, rules)
        if lead != 1.0:
            running = running * Decimal(str(lead))
            days_out = (travel_date - reference_date).days
            factors.append(
                Factor("lead_time", lead, _lead_time_reason(days_out))
            )

    # 4. National holiday (multiplier >= 1: never lowers pre-clamp price).
    if holiday:
        mult = 1.0 + rules.holiday_boost
        running = running * Decimal(str(mult))
        factors.append(
            Factor("holiday", mult, "national holiday in destination market")
        )

    # 5. Nearby events (each multiplier >= 1). The impact is strongest on the
    #    event day and fades linearly to 0 at the edge of the proximity window,
    #    so demand ramps up toward a peak rather than switching on abruptly. This
    #    also gives distinct day-to-day prices across weeks with different event
    #    distances. The multiplier stays >= 1 (P3 holds).
    for event in events:
        distance = abs((event.date - travel_date).days)
        weight = event_proximity_weight(distance, rules.proximity_days)
        if weight > 0.0:
            mult = 1.0 + event.impact * weight
            running = running * Decimal(str(mult))
            factors.append(
                Factor("event", mult, _event_reason(event.name, distance))
            )

    # 6. Clamp to route guardrails (req 2.2 / 2.3).
    clamped = min(max(running, route.floor), route.ceiling)

    return PriceResult(
        price=_quantize(clamped),
        base=route.base_fare,
        factors=tuple(factors),
    )


def price_breakdown(result: PriceResult) -> list[BreakdownItem]:
    """Explain a price as a list of euro/percentage contributions (pure).

    Replays the factors in order from the base fare, attributing to each the euros
    it added or removed at that point in the chain. If the guardrail clamp moved
    the price, a final ``"guardrail"`` item carries that adjustment. Invariant:
    ``base + sum(contribution_eur) == price`` exactly, so a stakeholder can read
    the table top-to-bottom and land on the recommended fare.
    """
    items: list[BreakdownItem] = []
    base = result.base
    running = base
    for factor in result.factors:
        after = running * Decimal(str(factor.multiplier))
        delta = _quantize(after) - _quantize(running)
        items.append(
            BreakdownItem(
                kind=factor.kind,
                reason=factor.reason,
                multiplier=factor.multiplier,
                contribution_eur=delta,
                contribution_pct=float(delta / base * 100) if base else 0.0,
            )
        )
        running = after

    # The gap between the un-clamped chain and the final price is the
    # floor/ceiling guardrail at work.
    chain_final = _quantize(running)
    clamp_delta = result.price - chain_final
    if clamp_delta != 0:
        direction = "ceiling cap" if clamp_delta < 0 else "floor protection"
        items.append(
            BreakdownItem(
                kind="guardrail",
                reason=f"route {direction} applied",
                multiplier=1.0,
                contribution_eur=clamp_delta,
                contribution_pct=float(clamp_delta / base * 100) if base else 0.0,
            )
        )

    # Per-step cent rounding can leave a 1-cent residual; fold it into the last
    # item so base + sum(contributions) == price holds exactly.
    if items:
        residual = result.price - (base + sum((i.contribution_eur for i in items), Decimal("0")))
        if residual != 0:
            last = items[-1]
            fixed = last.contribution_eur + residual
            items[-1] = BreakdownItem(
                kind=last.kind,
                reason=last.reason,
                multiplier=last.multiplier,
                contribution_eur=fixed,
                contribution_pct=float(fixed / base * 100) if base else 0.0,
            )
    return items


def _season_reason(season: float) -> str:
    if season > 1.0:
        return "peak season"
    if season < 1.0:
        return "low season"
    return "shoulder season"


def _dow_reason(travel_date: date, dow: float) -> str:
    name = _WEEKDAY_NAMES[travel_date.weekday()]
    if dow > 1.0:
        return f"{name} — higher-demand departure day"
    if dow < 1.0:
        return f"{name} — lower-demand departure day"
    return f"{name} — neutral departure day"


def _lead_time_reason(days_out: int) -> str:
    if days_out <= 0:
        return "same-day / past departure — peak advance-purchase premium"
    return f"{days_out} days to departure — advance-purchase premium"


def _event_reason(name: str, distance_days: int) -> str:
    if distance_days == 0:
        return f"{name} — on the event day (peak demand)"
    day_word = "day" if distance_days == 1 else "days"
    return f"{name} — {distance_days} {day_word} away (demand building)"
