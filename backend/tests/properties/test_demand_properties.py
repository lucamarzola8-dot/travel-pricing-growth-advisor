"""Property-based tests for the profit-optimising demand model (Kiro Lesson 4).

These encode the rules the elasticity + capacity optimiser must always satisfy
(D1..D5 for the optimiser, C1..C3 for capacity, E1 for segment elasticity),
checked over hundreds of generated inputs rather than fixed examples.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from travel_advisor.demand import (
    base_demand_for,
    demand_at_price,
    markup_price,
    optimize_price,
)

from .strategies import pricing_rules, routes, travel_dates


def _demand_fn(route, opt, rules):
    e = opt.elasticity
    bd = base_demand_for(route, rules)

    def demand(p: Decimal) -> float:
        return demand_at_price(p, route.base_fare, opt.demand_multiplier, e, bd)

    return demand


# D1: the optimal price is always within [floor, ceiling].
@given(route=routes(), travel_date=travel_dates, holiday=st.booleans(), rules=pricing_rules())
def test_d1_optimal_within_bounds(route, travel_date, holiday, rules):
    opt = optimize_price(route, travel_date, holiday=holiday, rules=rules)
    assert route.floor <= opt.optimal_price <= route.ceiling


# D2: the optimal price earns at least as much PROFIT (under the seat cap) as
# either bound — it is a maximiser over the price range.
@given(route=routes(), travel_date=travel_dates, holiday=st.booleans(), rules=pricing_rules())
def test_d2_optimal_profit_beats_bounds(route, travel_date, holiday, rules):
    opt = optimize_price(route, travel_date, holiday=holiday, rules=rules)
    demand = _demand_fn(route, opt, rules)
    cost = opt.marginal_cost

    def profit(p: Decimal) -> Decimal:
        sold = min(demand(p), float(route.seats))
        return (Decimal(str(p)) - cost) * Decimal(str(sold))

    tol = abs(opt.expected_profit) * Decimal("0.02") + Decimal("0.01")
    assert opt.expected_profit + tol >= profit(route.floor)
    assert opt.expected_profit + tol >= profit(route.ceiling)


# D3: the optimiser is deterministic — equal inputs give equal results.
@given(route=routes(), travel_date=travel_dates, holiday=st.booleans(), rules=pricing_rules())
def test_d3_deterministic(route, travel_date, holiday, rules):
    a = optimize_price(route, travel_date, holiday=holiday, rules=rules)
    b = optimize_price(route, travel_date, holiday=holiday, rules=rules)
    assert a == b


# D4: demand is non-increasing in price (positive elasticity) for any rules.
@given(route=routes(), rules=pricing_rules())
def test_d4_demand_monotonic_in_price(route, rules):
    e = rules.elasticity_for(route.segment)
    bd = base_demand_for(route, rules)
    lo = demand_at_price(route.floor, route.base_fare, 1.0, e, bd)
    hi = demand_at_price(route.ceiling, route.base_fare, 1.0, e, bd)
    assert lo >= hi


# D5: the optimal price is never below marginal cost whenever the route's price
# range allows it (ceiling >= cost) — a profit-maximiser refuses to sell at a loss.
@given(route=routes(), travel_date=travel_dates, holiday=st.booleans(), rules=pricing_rules())
def test_d5_optimal_price_covers_cost(route, travel_date, holiday, rules):
    opt = optimize_price(route, travel_date, holiday=holiday, rules=rules)
    if route.ceiling >= opt.marginal_cost:
        assert opt.optimal_price >= opt.marginal_cost


# C1: expected seats sold never exceed the aircraft's seats.
@given(route=routes(), travel_date=travel_dates, holiday=st.booleans(), rules=pricing_rules())
def test_c1_never_oversell(route, travel_date, holiday, rules):
    opt = optimize_price(route, travel_date, holiday=holiday, rules=rules)
    assert opt.expected_demand <= route.seats + 1e-9
    assert 0.0 <= opt.load_factor <= 1.0


# C2: the optimal price is never below the unconstrained markup price — capacity
# can only push the price UP, never down.
@given(route=routes(), travel_date=travel_dates, holiday=st.booleans(), rules=pricing_rules())
def test_c2_capacity_only_raises_price(route, travel_date, holiday, rules):
    opt = optimize_price(route, travel_date, holiday=holiday, rules=rules)
    # Allow one grid step of tolerance for the sampled search.
    step = (route.ceiling - route.floor) / 199 if route.ceiling > route.floor else Decimal("0")
    assert opt.optimal_price + step + Decimal("0.01") >= opt.unconstrained_price


# C3: more seats never raise the optimal price — a bigger aircraft can only relax
# the capacity constraint.
@given(route=routes(), travel_date=travel_dates, holiday=st.booleans(), rules=pricing_rules())
def test_c3_more_seats_never_raise_price(route, travel_date, holiday, rules):
    small = optimize_price(route, travel_date, holiday=holiday, rules=rules)
    bigger = replace(route, seats=route.seats * 2)
    large = optimize_price(bigger, travel_date, holiday=holiday, rules=rules)
    step = (route.ceiling - route.floor) / 199 if route.ceiling > route.floor else Decimal("0")
    assert large.optimal_price <= small.optimal_price + step + Decimal("0.01")


# E1: with capacity slack, a less elastic segment supports a higher (or equal)
# unconstrained markup price — the markup c*e/(e-1) is decreasing in e.
@given(
    cost=st.decimals(min_value=Decimal("10"), max_value=Decimal("500"), places=2),
    e_low=st.floats(min_value=1.05, max_value=3.0, allow_nan=False, allow_infinity=False),
    e_high=st.floats(min_value=1.05, max_value=3.0, allow_nan=False, allow_infinity=False),
)
def test_e1_lower_elasticity_higher_markup(cost, e_low, e_high):
    lo, hi = sorted((e_low, e_high))
    assert markup_price(cost, lo) >= markup_price(cost, hi)
