"""Growth opportunity advisor — pure and deterministic.

Scores markets by growth opportunity, ranks them, and splits a marketing budget
across them proportionally to score. Designed so the spec's growth properties hold:

- allocations are non-negative (G2) and sum exactly to the total budget (G1);
- a strictly higher score never receives a smaller allocation (G3);
- ``opportunity_score`` is monotonic non-decreasing in demand (G4);
- ``rank`` is sorted by non-increasing score (G5).
"""

from __future__ import annotations

import math
from decimal import ROUND_DOWN, Decimal

from .models import Allocation, MarketOpportunity

_CENTS = Decimal("0.01")

# A margin index of 0 should still leave demand contributing to the score, so the
# margin acts as an uplift on top of a base of 1.0.
_MARGIN_UPLIFT = 1.0
# Guards against division by a zero / tiny cost-per-click.
_MIN_CPC = 0.05


def opportunity_score(
    expected_demand: float, margin: float = 0.0, cpc_eur: float = 1.0
) -> float:
    """ROI-of-ad-spend opportunity score (>= 0).

    Models the return on a euro of Google Ads spend in a market:

        score = demand * (1 + margin) / cpc

    - rises with search demand and with booking margin;
    - falls as the cost-per-click rises (the same budget buys fewer clicks);
    - is monotonic non-decreasing in demand (keeps property G4);
    - is always >= 0.

    ``cpc_eur`` defaults to 1.0 so the older two-argument call still works.
    """
    demand = max(expected_demand, 0.0)
    marg = max(margin, 0.0)
    cpc = max(cpc_eur, _MIN_CPC)
    return demand * (_MARGIN_UPLIFT + marg) / cpc


def normalize_interest(raw: dict[str, float]) -> dict[str, int]:
    """Scale raw search-interest values to a 0-100 demand index (pure, no network).

    The largest raw value maps to 100 and the rest scale linearly, matching the
    0-100 convention of ``demand_index`` in ``markets.json``. Used by the optional
    Google Trends enrichment to turn raw interest into the seed's index. Negative
    values are floored at 0; an all-zero (or empty) input yields all zeros.
    """
    if not raw:
        return {}
    clamped = {k: max(float(v), 0.0) for k, v in raw.items()}
    peak = max(clamped.values(), default=0.0)
    if peak <= 0:
        return {k: 0 for k in clamped}
    return {k: round(v / peak * 100) for k, v in clamped.items()}


def demand_uplift(holiday_days: int, event_hits: int) -> float:
    """Demand uplift factor (>= 1.0) for a market over an analysed period.

    Links the pricing view to the ads view: the more holiday days and nearby
    events fall in the analysed window for a market, the stronger the expected
    demand, so that market becomes a better place to spend ad budget.

    Each holiday day and each event hit adds a fixed, bounded boost. The factor
    is always >= 1.0, so context can only raise a market's score, never lower it
    (this keeps allocation monotonic and the growth properties intact).
    """
    hol = max(holiday_days, 0)
    ev = max(event_hits, 0)
    return 1.0 + 0.05 * hol + 0.08 * ev


def expected_outcome(
    amount: Decimal, cpc_eur: float, conversion_rate: float, avg_booking_value_eur: float
) -> dict[str, float]:
    """Turn an ad spend into expected clicks, bookings, and revenue (pure).

        clicks   = amount / cpc
        bookings = clicks × conversion_rate
        revenue  = bookings × avg_booking_value

    Deterministic; all outputs are non-negative and monotonic non-decreasing in
    ``amount`` (more spend never lowers expected outcomes). CPC is floored to avoid
    division by zero.
    """
    cpc = max(cpc_eur, 0.05)
    conv = max(conversion_rate, 0.0)
    aov = max(avg_booking_value_eur, 0.0)
    clicks = float(amount) / cpc
    bookings = clicks * conv
    revenue = bookings * aov
    return {"clicks": clicks, "bookings": bookings, "revenue": revenue}


def _saturating(amount: float) -> float:
    """Diminishing-returns transform: effective value grows with the square root
    of spend, so each extra euro returns a little less than the last."""
    return math.sqrt(max(amount, 0.0))


def rank(markets: list[MarketOpportunity]) -> list[MarketOpportunity]:
    """Return markets sorted by non-increasing score (stable) — G5."""
    return sorted(markets, key=lambda m: m.score, reverse=True)


def allocate(
    total_budget: Decimal, markets: list[MarketOpportunity]
) -> list[Allocation]:
    """Split ``total_budget`` across markets proportionally to score.

    Guarantees (for non-negative budget and scores):
    - every amount is >= 0 (G2);
    - the amounts sum exactly to ``total_budget`` (G1) — any rounding remainder is
      given to the highest-scored market, so a higher score never loses out (G3);
    - if all scores are zero, the budget is split as evenly as possible.
    """
    if total_budget < 0:
        raise ValueError("total_budget must be non-negative")
    if not markets:
        return []

    total_budget = total_budget.quantize(_CENTS)
    scores = [max(m.score, 0.0) for m in markets]
    score_sum = sum(scores)

    # Order markets by score desc so the rounding remainder lands on the top market;
    # this keeps allocations monotonic with score (G3).
    order = sorted(range(len(markets)), key=lambda i: scores[i], reverse=True)

    raw: list[Decimal] = [Decimal("0.00")] * len(markets)
    if score_sum <= 0:
        # All zero scores: even split, remainder to the first market.
        even = (total_budget / len(markets)).quantize(_CENTS, rounding=ROUND_DOWN)
        for i in range(len(markets)):
            raw[i] = even
    else:
        for i in range(len(markets)):
            share = Decimal(str(scores[i])) / Decimal(str(score_sum))
            raw[i] = (total_budget * share).quantize(_CENTS, rounding=ROUND_DOWN)

    # Distribute the leftover cents to the highest-scored markets first.
    allocated = sum(raw)
    remainder = total_budget - allocated
    cents = int((remainder / _CENTS).to_integral_value())
    for k in range(cents):
        raw[order[k % len(order)]] += _CENTS

    return [Allocation(market=markets[i].market, amount=raw[i]) for i in range(len(markets))]


# Per-market spend cap for the saturating allocation, as a multiple of the even
# share. A market can absorb at most this multiple of (budget / number of markets)
# before its budget spills over to others — modelling advertising saturation.
_SATURATION_CAP_FACTOR = 2.5


def allocate_with_saturation(
    total_budget: Decimal, markets: list[MarketOpportunity]
) -> list[Allocation]:
    """Allocate a budget under **diminishing returns** (water-filling).

    Instead of a flat proportional split, budget is poured in small increments,
    each time into the market with the highest *marginal* value:

        marginal value = score / sqrt(1 + euros already spent there)

    As a market receives more budget its marginal value falls, so later euros flow
    elsewhere — no single market absorbs budget linearly. This models ad saturation.

    Guarantees: amounts are non-negative and sum exactly to ``total_budget``. With
    all-zero scores it falls back to the plain even/proportional split.
    """
    if total_budget < 0:
        raise ValueError("total_budget must be non-negative")
    if not markets:
        return []

    scores = [max(m.score, 0.0) for m in markets]
    if sum(scores) <= 0:
        return allocate(total_budget, markets)

    total_budget = total_budget.quantize(_CENTS)
    if total_budget == 0:
        return [Allocation(m.market, Decimal("0.00")) for m in markets]

    budget_f = float(total_budget)
    n = len(markets)

    # Diminishing returns: budget is split in proportion to a *concave* function of
    # score (its square root), not the score itself. This keeps ordering (a higher
    # score still gets more) while compressing the extremes — the top market receives
    # less than a flat proportional split would give it, and the budget spreads toward
    # other markets. That compression is exactly the saturation effect.
    weights = [math.sqrt(s) for s in scores]

    # Iterative water-filling with a per-market cap = cap_factor * even_share, so a
    # dominant market saturates and the rest receive the overflow.
    even_share = budget_f / n
    cap = _SATURATION_CAP_FACTOR * even_share

    remaining = budget_f
    alloc = [0.0] * n
    active = list(range(n))
    # Distribute proportionally to weights, capping saturated markets and
    # redistributing their overflow, until nothing is capped.
    for _ in range(n + 1):
        wsum = sum(weights[i] for i in active)
        if wsum <= 0:
            break
        newly_capped = []
        for i in active:
            want = alloc[i] + remaining * weights[i] / wsum
            if want > cap:
                newly_capped.append(i)
        if not newly_capped:
            for i in active:
                alloc[i] += remaining * weights[i] / wsum
            remaining = 0.0
            break
        for i in newly_capped:
            remaining -= cap - alloc[i]
            alloc[i] = cap
            active.remove(i)
        if not active:
            break

    amounts = [Decimal(str(round(a, 2))).quantize(_CENTS) for a in alloc]
    # Fix rounding drift so the total is exact, adjusting the largest allocation.
    drift = total_budget - sum(amounts)
    if drift != 0:
        top = max(range(n), key=lambda i: amounts[i])
        amounts[top] += drift

    return [Allocation(markets[i].market, amounts[i]) for i in range(n)]
