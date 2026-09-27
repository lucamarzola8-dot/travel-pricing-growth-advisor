"""Growth opportunity advisor — pure and deterministic.

Scores markets by growth opportunity, ranks them, and splits a marketing budget
across them proportionally to score. Designed so the spec's growth properties hold:

- allocations are non-negative (G2) and sum exactly to the total budget (G1);
- a strictly higher score never receives a smaller allocation (G3);
- ``opportunity_score`` is monotonic non-decreasing in demand (G4);
- ``rank`` is sorted by non-increasing score (G5).
"""

from __future__ import annotations

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
