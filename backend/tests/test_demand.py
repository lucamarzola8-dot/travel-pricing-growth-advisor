"""Example-based tests for the profit-optimising demand model (demand.py) and the
euro/percent price breakdown (pricing.price_breakdown)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from travel_advisor.demand import (
    base_demand_for,
    demand_at_price,
    demand_multiplier,
    markup_price,
    market_clearing_price,
    optimize_price,
)
from travel_advisor.models import Event, PricingRules, Route
from travel_advisor.pricing import price_breakdown, price_for


def make_route(
    base="150.00", floor="80.00", ceiling="400.00", seats=180, segment="leisure"
) -> Route:
    return Route(
        code="TST-XXX",
        origin="TST",
        destination_market="XXX",
        destination_country="ES",
        base_fare=Decimal(base),
        floor=Decimal(floor),
        ceiling=Decimal(ceiling),
        seats=seats,
        segment=segment,
    )


# --- demand curve ----------------------------------------------------------- #


def test_demand_falls_as_price_rises():
    ref = Decimal("150.00")
    lo = demand_at_price(Decimal("120.00"), ref, 1.0, 1.3, 100.0)
    mid = demand_at_price(Decimal("150.00"), ref, 1.0, 1.3, 100.0)
    hi = demand_at_price(Decimal("200.00"), ref, 1.0, 1.3, 100.0)
    assert lo > mid > hi > 0.0


def test_demand_at_reference_equals_base_times_multiplier():
    ref = Decimal("150.00")
    assert demand_at_price(ref, ref, 1.0, 1.3, 100.0) == 100.0
    assert demand_at_price(ref, ref, 1.5, 1.3, 100.0) == 150.0


def test_base_demand_scales_with_seats():
    rules = PricingRules(base_demand_per_seat=1.6)
    assert base_demand_for(make_route(seats=100), rules) == 160.0
    assert base_demand_for(make_route(seats=200), rules) == 320.0


def test_demand_multiplier_is_product_of_factors():
    route = make_route()
    plain = price_for(route, date(2026, 4, 16), holiday=False)
    holi = price_for(route, date(2026, 4, 16), holiday=True)
    assert demand_multiplier(holi) > demand_multiplier(plain)


def test_market_clearing_price_inverts_demand():
    ref = Decimal("150.00")
    p = market_clearing_price(ref, 1.0, 1.4, 288.0, 180)
    assert p is not None
    # At the clearing price demand equals the seats (within float noise).
    assert abs(demand_at_price(p, ref, 1.0, 1.4, 288.0) - 180.0) < 1e-6


# --- optimiser: markup ------------------------------------------------------ #


def test_optimal_price_within_bounds():
    route = make_route()
    opt = optimize_price(route, date(2026, 4, 16), holiday=False)
    assert route.floor <= opt.optimal_price <= route.ceiling


def test_profit_optimum_is_interior_markup_when_capacity_slack():
    """With plenty of seats the optimum is the markup c*e/(e-1), not a bound.

    base 150, cost ratio 0.30 -> c = 45.00; leisure e = 1.45 -> 45*1.45/0.45 = 145.00.
    """
    route = make_route()
    # Low demand relative to seats -> the seat cap never binds.
    rules = PricingRules(marginal_cost_ratio=0.30, base_demand_per_seat=0.2)
    opt = optimize_price(route, date(2026, 4, 16), holiday=False, rules=rules)
    assert route.floor < opt.optimal_price < route.ceiling
    assert abs(float(opt.optimal_price) - 145.00) <= 0.01
    assert opt.capacity_constrained is False


def test_optimal_price_above_marginal_cost():
    route = make_route()
    opt = optimize_price(route, date(2026, 4, 16), holiday=False)
    assert opt.optimal_price >= opt.marginal_cost


def test_optimal_profit_at_least_recommended_profit():
    route = make_route()
    event = Event("XXX", date(2026, 4, 16), "Big Fair", 0.40)
    opt = optimize_price(route, date(2026, 4, 16), holiday=True, events=[event])
    assert opt.expected_profit >= opt.recommended_profit
    assert opt.uplift_pct >= 0.0


def test_optimize_is_deterministic():
    route = make_route()
    event = Event("XXX", date(2026, 4, 17), "Fair", 0.2)
    a = optimize_price(route, date(2026, 4, 16), holiday=True, events=[event])
    b = optimize_price(route, date(2026, 4, 16), holiday=True, events=[event])
    assert a == b


def test_optimize_carries_factors_for_explainability():
    route = make_route()
    opt = optimize_price(route, date(2026, 4, 16), holiday=True)
    kinds = [f.kind for f in opt.factors]
    assert "seasonality" in kinds and "holiday" in kinds


# --- optimiser: segment elasticity ----------------------------------------- #


def test_segment_elasticity_is_selected():
    rules = PricingRules(elasticity_by_segment=(("business", 1.30), ("leisure", 1.45)))
    assert rules.elasticity_for("business") == 1.30
    assert rules.elasticity_for("leisure") == 1.45
    assert rules.elasticity_for("unknown") == rules.elasticity  # fallback


def test_business_route_prices_higher_than_leisure_with_slack():
    """Same fare/cost, no capacity pressure: the less elastic business segment
    sustains a higher markup, hence a higher optimal price."""
    rules = PricingRules(base_demand_per_seat=0.2)  # capacity slack on both
    biz = optimize_price(make_route(segment="business"), date(2026, 4, 16), holiday=False, rules=rules)
    lei = optimize_price(make_route(segment="leisure"), date(2026, 4, 16), holiday=False, rules=rules)
    assert biz.optimal_price > lei.optimal_price
    assert biz.elasticity < lei.elasticity


def test_markup_decreasing_in_elasticity():
    c = Decimal("45.00")
    assert markup_price(c, 1.30) > markup_price(c, 1.45) > markup_price(c, 2.0)


# --- optimiser: capacity / peak pricing ------------------------------------ #


def test_capacity_binds_on_hot_day_and_raises_price():
    """On a high-demand day the markup price would overfill the plane, so the
    optimiser raises the price to the market-clearing level (peak pricing)."""
    route = make_route(seats=180, ceiling="1000.00")
    event = Event("XXX", date(2026, 4, 17), "Mega Festival", 0.60)  # Friday
    quiet = optimize_price(route, date(2026, 4, 16), holiday=False)
    hot = optimize_price(route, date(2026, 4, 17), holiday=True, events=[event])
    assert hot.capacity_constrained is True
    assert hot.optimal_price > hot.unconstrained_price
    assert hot.optimal_price > quiet.optimal_price
    # Never oversells.
    assert hot.expected_demand <= route.seats + 1e-9


def test_capacity_not_binding_keeps_markup_price():
    route = make_route()
    rules = PricingRules(base_demand_per_seat=0.2)  # demand far below seats
    opt = optimize_price(route, date(2026, 4, 16), holiday=False, rules=rules)
    assert opt.capacity_constrained is False
    assert opt.optimal_price == opt.unconstrained_price


def test_smaller_aircraft_raises_price_when_binding():
    route_big = make_route(seats=300, ceiling="1000.00")
    route_small = make_route(seats=120, ceiling="1000.00")
    event = Event("XXX", date(2026, 4, 17), "Mega Festival", 0.60)
    big = optimize_price(route_big, date(2026, 4, 17), holiday=True, events=[event])
    small = optimize_price(route_small, date(2026, 4, 17), holiday=True, events=[event])
    assert small.optimal_price >= big.optimal_price


def test_load_factor_is_bounded():
    route = make_route(seats=180)
    event = Event("XXX", date(2026, 4, 17), "Mega Festival", 0.60)
    opt = optimize_price(route, date(2026, 4, 17), holiday=True, events=[event])
    assert 0.0 <= opt.load_factor <= 1.0


# --- price breakdown (EUR / %) --------------------------------------------- #


def test_breakdown_sums_to_final_price():
    route = make_route(base="150.00", floor="80.00", ceiling="400.00")
    event = Event("XXX", date(2026, 4, 17), "Fair", 0.30)
    result = price_for(route, date(2026, 4, 17), holiday=True, events=[event])
    items = price_breakdown(result)
    total = result.base + sum((i.contribution_eur for i in items), Decimal("0"))
    assert total == result.price
    assert [i.kind for i in items][: len(result.factors)] == [f.kind for f in result.factors]


def test_breakdown_shows_guardrail_when_clamped():
    route = make_route(base="290.00", floor="50.00", ceiling="300.00")
    big_event = Event("XXX", date(2026, 7, 15), "Huge", 5.0)
    result = price_for(route, date(2026, 7, 15), holiday=True, events=[big_event])
    items = price_breakdown(result)
    assert result.price == Decimal("300.00")
    assert items[-1].kind == "guardrail"
    assert items[-1].contribution_eur < 0  # ceiling pulled the price down
    total = result.base + sum((i.contribution_eur for i in items), Decimal("0"))
    assert total == result.price


def test_breakdown_percentages_are_relative_to_base():
    route = make_route(base="100.00")
    # Thursday, shoulder: only neutral factors; then a 10% holiday boost.
    result = price_for(route, date(2026, 4, 16), holiday=True)
    items = {i.kind: i for i in price_breakdown(result)}
    assert items["holiday"].contribution_eur == Decimal("10.00")
    assert abs(items["holiday"].contribution_pct - 10.0) < 1e-9
