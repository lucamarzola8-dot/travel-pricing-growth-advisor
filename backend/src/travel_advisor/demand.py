"""Profit-maximising pricing via a price-elasticity demand model — pure code.

Where :mod:`pricing` applies bounded multipliers to *set* a price, this module
answers the revenue-manager's real question: **which price earns the most money,
given the seats we actually have?**

The idea, in four steps:

1. The same contextual factors the pricing engine computes (seasonality, day of
   week, nearby events, national holidays) are read as **demand signals** rather
   than price nudges. Their combined multiplier scales a baseline demand: a holiday
   or a nearby event means more people want to fly, an off-peak Tuesday fewer.
   (These multipliers were calibrated as price adjustments; reusing them as a
   demand-context index is a deliberate simplification that keeps the price view
   and the demand view from ever disagreeing about a day's context.)

2. Demand responds to price with constant elasticity ``e`` (per route segment —
   business travellers are less price-sensitive than leisure ones):

       demand(p) = base_demand * demand_multiplier * (p / p_ref) ** (-e)

   With ``e > 1`` a 10% price rise loses more than 10% of demand, so pushing price
   too high destroys profit.

3. Expected **profit** is ``(p - c) * demand(p)`` where ``c`` is the marginal cost
   to serve a seat. Its unconstrained maximiser is the classic revenue-management
   markup ``p* = c * e / (e - 1)``: an interior price above cost that depends on
   cost and elasticity only.

4. **Capacity.** An aircraft has a fixed number of seats. If demand at the markup
   price would exceed them, the airline cannot sell more seats — so profit becomes
   ``(p - c) * min(demand(p), seats)`` and the optimum moves up to the
   *market-clearing* price where ``demand(p) == seats``. This is what makes the
   optimal price rise on high-demand days (holidays, events, weekends): **peak
   pricing emerges from the constraint**, it is not a hand-tuned rule.

Everything is a pure function of its inputs and the data-driven rules: no clock, no
globals, equal inputs give equal output (determinism), mirroring :mod:`pricing`.
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from .models import Event, PriceResult, PricingRules, RevenueOptimization, Route
from .pricing import price_for

_CENTS = Decimal("0.01")
# Number of candidate prices sampled across [floor, ceiling] in the search. The
# closed-form markup and market-clearing prices are added as extra candidates, so
# the grid only needs to be fine enough for a smooth profit curve.
_GRID_POINTS = 200


def demand_multiplier(result: PriceResult) -> float:
    """Combine a price result's factors into a single demand multiplier (> 0).

    Reuses exactly the factors the pricing engine already computed, so the demand
    view and the price view can never disagree about the context of a day. The
    product of the factor multipliers is the relative demand versus an ordinary
    day (multiplier 1.0).
    """
    mult = 1.0
    for factor in result.factors:
        mult *= factor.multiplier
    return mult


def base_demand_for(route: Route, rules: PricingRules) -> float:
    """Baseline demand at the route's base fare on an ordinary day (>= 0)."""
    return rules.base_demand_per_seat * route.seats


def demand_at_price(
    price: Decimal,
    reference_price: Decimal,
    demand_mult: float,
    elasticity: float,
    base_demand: float,
) -> float:
    """Expected demand at ``price`` under constant-elasticity response (>= 0).

        demand = base_demand * demand_mult * (price / reference_price) ** (-elasticity)

    ``reference_price`` is the price at which ``base_demand`` applies (the route
    base fare). Pure and deterministic.
    """
    if reference_price <= 0 or price <= 0:
        return 0.0
    ratio = float(price) / float(reference_price)
    response = ratio ** (-elasticity)
    return max(base_demand * demand_mult * response, 0.0)


def markup_price(marginal_cost: Decimal, elasticity: float) -> Decimal:
    """Unconstrained profit-maximising price ``c * e / (e - 1)`` for ``e > 1``."""
    return marginal_cost * Decimal(str(elasticity)) / Decimal(str(elasticity - 1.0))


def market_clearing_price(
    reference_price: Decimal,
    demand_mult: float,
    elasticity: float,
    base_demand: float,
    seats: int,
) -> Decimal | None:
    """Price at which expected demand exactly equals ``seats`` (or None).

    Inverts the demand curve: ``p = p_ref * (base_demand * mult / seats) ** (1/e)``.
    Returns None when demand cannot reach the seats at any positive price
    (``base_demand * mult <= 0``).
    """
    total = base_demand * demand_mult
    if total <= 0 or seats <= 0:
        return None
    ratio = (total / seats) ** (1.0 / elasticity)
    return reference_price * Decimal(str(ratio))


def _quantize(amount: Decimal) -> Decimal:
    return amount.quantize(_CENTS, rounding=ROUND_HALF_UP)


def _profit_at(
    price: Decimal,
    reference_price: Decimal,
    demand_mult: float,
    marginal_cost: Decimal,
    elasticity: float,
    base_demand: float,
    seats: int,
) -> Decimal:
    """Expected profit ``(price - cost) * min(demand(price), seats)``.

    Selling is capped at the aircraft's seats; this cap is what turns high demand
    into a higher optimal price. May be negative below cost.
    """
    demand = demand_at_price(price, reference_price, demand_mult, elasticity, base_demand)
    sold = min(demand, float(seats))
    return (Decimal(str(price)) - marginal_cost) * Decimal(str(sold))


def optimize_price(
    route: Route,
    travel_date: date,
    *,
    holiday: bool,
    events: list[Event] | None = None,
    rules: PricingRules | None = None,
) -> RevenueOptimization:
    """Find the profit-maximising price for ``route`` on ``travel_date``.

    Uses the pricing engine's factors as demand signals, then searches the price on
    ``[floor, ceiling]`` for the maximum expected profit under the route's seat
    capacity. Returns the optimal price, the unconstrained markup price, and the
    rule-based recommended price with their expected demand/revenue/profit, so the
    UI can show the uplift and whether capacity forced the price up. Pure function
    of the inputs and data-driven rules.
    """
    rules = rules or PricingRules()
    events = events or []

    # 1. Reuse the pricing factors as the demand context for this day.
    rule_result = price_for(
        route, travel_date, holiday=holiday, events=events, rules=rules
    )
    demand_mult = demand_multiplier(rule_result)
    reference_price = route.base_fare
    elasticity = rules.elasticity_for(route.segment)
    base_demand = base_demand_for(route, rules)
    seats = route.seats
    marginal_cost = _quantize(reference_price * Decimal(str(rules.marginal_cost_ratio)))

    floor, ceiling = route.floor, route.ceiling

    def clamp(p: Decimal) -> Decimal:
        return min(max(p, floor), ceiling)

    def demand(p: Decimal) -> float:
        return demand_at_price(p, reference_price, demand_mult, elasticity, base_demand)

    def profit(p: Decimal) -> Decimal:
        return _profit_at(
            p, reference_price, demand_mult, marginal_cost, elasticity, base_demand, seats
        )

    # 2. Analytical candidates: the markup optimum and the market-clearing price.
    unconstrained = clamp(_quantize(markup_price(marginal_cost, elasticity)))
    clearing = market_clearing_price(reference_price, demand_mult, elasticity, base_demand, seats)

    # 3. Grid-search [floor, ceiling] (plus the analytical candidates) for the
    #    profit-maximising price under the seat cap.
    if ceiling <= floor:
        candidates = [floor]
    else:
        step = (ceiling - floor) / (_GRID_POINTS - 1)
        candidates = [floor + step * i for i in range(_GRID_POINTS)]
        candidates[-1] = ceiling  # guard against float drift missing the ceiling
    candidates.append(unconstrained)
    if clearing is not None:
        candidates.append(clamp(_quantize(clearing)))

    best_price = candidates[0]
    best_profit = profit(best_price)
    for p in candidates[1:]:
        pr = profit(p)
        # Prefer the higher profit; on a tie keep the lower price (deterministic).
        if pr > best_profit or (pr == best_profit and p < best_price):
            best_profit, best_price = pr, p

    optimal = _quantize(best_price)
    opt_demand_raw = demand(optimal)
    opt_sold = min(opt_demand_raw, float(seats))
    opt_revenue = _quantize(optimal * Decimal(str(opt_sold)))
    opt_profit = _quantize((optimal - marginal_cost) * Decimal(str(opt_sold)))

    # Capacity is "binding" when the optimiser had to move above the markup price
    # because the markup price alone would have overfilled the aircraft.
    capacity_constrained = demand(unconstrained) > float(seats) and optimal > unconstrained

    # 4. Revenue/profit the rule-based recommended price would earn, for comparison.
    rec_price = rule_result.price
    rec_sold = min(demand(rec_price), float(seats))
    rec_revenue = _quantize(rec_price * Decimal(str(rec_sold)))
    rec_profit = _quantize((rec_price - marginal_cost) * Decimal(str(rec_sold)))

    return RevenueOptimization(
        optimal_price=optimal,
        unconstrained_price=unconstrained,
        expected_demand=opt_sold,
        expected_revenue=opt_revenue,
        expected_profit=opt_profit,
        marginal_cost=marginal_cost,
        recommended=rec_price,
        recommended_revenue=rec_revenue,
        recommended_profit=rec_profit,
        demand_multiplier=demand_mult,
        elasticity=elasticity,
        segment=route.segment,
        seats=seats,
        capacity_constrained=capacity_constrained,
        factors=rule_result.factors,
    )
