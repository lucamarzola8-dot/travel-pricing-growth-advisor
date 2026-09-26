"""Storyline generation — turn computed results into business-language insights.

Every insight is backed by a real :class:`Factor` or allocation; nothing is
fabricated (requirement 4.3). The output is a plain list of sentences a consultant
can read to a client, plus the numbers behind them.
"""

from __future__ import annotations

from .models import Allocation, PriceResult


def pricing_insights(route_code: str, result: PriceResult) -> list[str]:
    """Insights explaining a price versus its base fare (req 4.1 / 4.2)."""
    insights: list[str] = []
    delta = result.delta_pct

    if abs(delta) < 0.5:
        insights.append(
            f"{route_code}: recommended fare is in line with the base fare "
            f"({result.price})."
        )
    else:
        direction = "above" if delta > 0 else "below"
        reasons = [f.reason for f in result.factors if f.kind != "seasonality"]
        reason_text = "; ".join(reasons) if reasons else "seasonal demand"
        insights.append(
            f"{route_code}: recommended fare {result.price} is {abs(delta):.0f}% "
            f"{direction} base — driven by {reason_text}."
        )

    # Call out an event driver explicitly if present.
    event_factors = [f for f in result.factors if f.kind == "event"]
    if event_factors:
        insights.append(
            f"Demand uplift expected from: {', '.join(f.reason for f in event_factors)}."
        )
    return insights


def growth_insights(allocations: list[Allocation]) -> list[str]:
    """Insights describing where budget should go (req 4.1)."""
    if not allocations:
        return []
    ranked = sorted(allocations, key=lambda a: a.amount, reverse=True)
    top = ranked[0]
    total = sum(a.amount for a in allocations)
    insights = [
        f"Top growth market is {top.market}, receiving {top.amount} of the "
        f"{total} budget."
    ]
    if len(ranked) > 1:
        others = ", ".join(f"{a.market} ({a.amount})" for a in ranked[1:])
        insights.append(f"Remaining budget is spread across: {others}.")
    return insights


def build_storyline(
    route_code: str,
    price: PriceResult,
    allocations: list[Allocation],
) -> list[str]:
    """Compose the full client-ready storyline from computed results."""
    return pricing_insights(route_code, price) + growth_insights(allocations)
