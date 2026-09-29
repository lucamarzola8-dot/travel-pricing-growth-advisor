"""Example-based tests for the pricing engine and data loaders."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from travel_advisor.data import UnknownRouteError, get_route, is_holiday, load_routes
from travel_advisor.models import Event, Route
from travel_advisor.pricing import price_for, seasonality_multiplier


def make_route(base="100.00", floor="50.00", ceiling="300.00") -> Route:
    return Route(
        code="TST-XXX",
        origin="TST",
        destination_market="XXX",
        destination_country="ES",
        base_fare=Decimal(base),
        floor=Decimal(floor),
        ceiling=Decimal(ceiling),
    )


def test_base_price_no_holiday_no_event_shoulder_season():
    route = make_route()
    # 2026-04-16 is a Thursday -> shoulder season (1.0) and neutral weekday (1.0),
    # and no reference_date so no lead-time factor: price stays at base.
    result = price_for(route, date(2026, 4, 16), holiday=False, events=[])
    assert result.price == Decimal("100.00")
    assert [f.kind for f in result.factors] == ["seasonality", "day_of_week"]


def test_holiday_raises_price():
    route = make_route()
    plain = price_for(route, date(2026, 4, 15), holiday=False)
    with_holiday = price_for(route, date(2026, 4, 15), holiday=True)
    assert with_holiday.price > plain.price
    assert any(f.kind == "holiday" for f in with_holiday.factors)


def test_event_within_window_raises_price():
    route = make_route()
    event = Event("XXX", date(2026, 4, 16), "Trade Fair", 0.30)
    plain = price_for(route, date(2026, 4, 15), holiday=False, events=[])
    with_event = price_for(route, date(2026, 4, 15), holiday=False, events=[event])
    assert with_event.price > plain.price
    assert any(f.kind == "event" for f in with_event.factors)


def test_event_outside_window_ignored():
    route = make_route()
    far_event = Event("XXX", date(2026, 5, 1), "Far Event", 0.30)
    # 2026-04-16 (Thursday): neutral weekday + shoulder season, event out of window.
    result = price_for(route, date(2026, 4, 16), holiday=False, events=[far_event])
    assert result.price == Decimal("100.00")
    assert all(f.kind != "event" for f in result.factors)


def test_price_never_exceeds_ceiling():
    route = make_route(base="290.00", ceiling="300.00")
    big_event = Event("XXX", date(2026, 7, 15), "Huge", 5.0)
    result = price_for(route, date(2026, 7, 15), holiday=True, events=[big_event])
    assert result.price == Decimal("300.00")  # clamped


def test_price_never_below_floor():
    route = make_route(base="55.00", floor="60.00", ceiling="300.00")
    # January -> low season 0.9 would drop below floor
    result = price_for(route, date(2026, 1, 15), holiday=False)
    assert result.price == Decimal("60.00")  # clamped up to floor


def test_seasonality_bounds():
    assert seasonality_multiplier(date(2026, 7, 1)) == 1.20  # peak
    assert seasonality_multiplier(date(2026, 1, 1)) == 0.90  # low
    assert seasonality_multiplier(date(2026, 4, 1)) == 1.00  # shoulder


def test_day_of_week_differentiates_prices():
    """Different weekdays in the same quiet period yield different prices."""
    route = make_route()
    # A run of consecutive shoulder-season days with no holiday/event should NOT
    # all collapse to the same price now that day-of-week applies.
    prices = {
        d: price_for(route, date(2026, 4, d), holiday=False, events=[]).price
        for d in range(13, 20)  # Mon 13 .. Sun 19 April 2026
    }
    assert len(set(prices.values())) > 1  # visibly differentiated across the week
    # Friday (higher-demand) prices above Tuesday (lower-demand).
    assert prices[17] > prices[14]  # Fri 17 vs Tue 14
    assert all(f.kind == "day_of_week" for r in [
        price_for(route, date(2026, 4, 17), holiday=False)
    ] for f in r.factors if f.kind == "day_of_week")


def test_day_of_week_multiplier_matches_weekday():
    from travel_advisor.pricing import day_of_week_multiplier

    # Default dow_multipliers = (Mon..Sun). 2026-04-13 is a Monday.
    assert day_of_week_multiplier(date(2026, 4, 13)) == 0.96  # Monday
    assert day_of_week_multiplier(date(2026, 4, 17)) == 1.08  # Friday
    assert day_of_week_multiplier(date(2026, 4, 16)) == 1.00  # Thursday (neutral)


def test_lead_time_raises_near_term_departures():
    """With a reference date, a soon departure costs more than a far one."""
    route = make_route(ceiling="10000.00")
    ref = date(2026, 4, 16)  # Thursday, shoulder
    soon = price_for(route, date(2026, 4, 16), holiday=False, reference_date=ref)
    # 40 days out is beyond the 21-day window -> no lead-time premium.
    far = price_for(route, date(2026, 5, 26), holiday=False, reference_date=ref)
    assert any(f.kind == "lead_time" for f in soon.factors)
    assert all(f.kind != "lead_time" for f in far.factors)


def test_lead_time_skipped_without_reference_date():
    """Omitting reference_date keeps the engine free of the lead-time factor."""
    route = make_route()
    result = price_for(route, date(2026, 4, 16), holiday=False)
    assert all(f.kind != "lead_time" for f in result.factors)


def test_event_impact_fades_with_distance():
    """Event boost is strongest on the event day and weaker further away."""
    route = make_route(ceiling="10000.00")
    event = Event("XXX", date(2026, 4, 16), "Big Concert", 0.40)  # Thursday, dow 1.0

    def event_mult(travel_day: int) -> float:
        r = price_for(route, date(2026, 4, travel_day), holiday=False, events=[event])
        evs = [f for f in r.factors if f.kind == "event"]
        return evs[0].multiplier if evs else 1.0

    on_day = event_mult(16)      # distance 0 -> full impact
    one_off = event_mult(17)     # distance 1 -> partial
    two_off = event_mult(18)     # distance 2 -> smaller
    assert on_day > one_off > two_off > 1.0


def test_event_proximity_weight_shape():
    from travel_advisor.pricing import event_proximity_weight

    # window = proximity_days + 1 = 4
    assert event_proximity_weight(0, 3) == 1.0
    assert event_proximity_weight(3, 3) == 0.25
    assert event_proximity_weight(4, 3) == 0.0  # just outside the window
    assert event_proximity_weight(10, 3) == 0.0


def test_event_just_outside_window_ignored():
    route = make_route(ceiling="10000.00")
    # proximity_days default 3 -> window 4; distance 4 must carry no event factor.
    event = Event("XXX", date(2026, 4, 20), "Far Fair", 0.30)
    result = price_for(route, date(2026, 4, 16), holiday=False, events=[event])
    assert all(f.kind != "event" for f in result.factors)


def test_deterministic():
    route = make_route()
    event = Event("XXX", date(2026, 4, 16), "Fair", 0.2)
    a = price_for(route, date(2026, 4, 15), holiday=True, events=[event])
    b = price_for(route, date(2026, 4, 15), holiday=True, events=[event])
    assert a == b


def test_rules_are_data_driven():
    """A different (data-driven) ruleset deterministically changes the price."""
    from travel_advisor.models import PricingRules

    route = make_route()
    # 2026-04-16 is a Thursday: shoulder season (1.0) and neutral weekday (1.0), so
    # only the holiday boost moves the price. Default 0.10 -> 110.00; 0.50 -> 150.00.
    default = price_for(route, date(2026, 4, 16), holiday=True)
    custom = price_for(
        route,
        date(2026, 4, 16),
        holiday=True,
        rules=PricingRules(holiday_boost=0.50),
    )
    assert default.price == Decimal("110.00")
    assert custom.price == Decimal("150.00")


def test_load_pricing_rules_defaults(tmp_path):
    """Missing rules file falls back to defaults (deterministic)."""
    from travel_advisor.data import load_pricing_rules
    from travel_advisor.models import PricingRules

    rules = load_pricing_rules(tmp_path)  # empty dir -> no file
    assert rules == PricingRules()


def test_load_pricing_rules_from_file():
    from travel_advisor.data import load_pricing_rules

    rules = load_pricing_rules()  # repo data/pricing-rules.json
    assert rules.holiday_boost == 0.10
    assert rules.proximity_days == 3
    assert 6 in rules.peak_months
    # New day-of-week / lead-time factors are loaded from data too.
    assert len(rules.dow_multipliers) == 7
    assert rules.lead_time_days == 21
    assert rules.lead_time_boost == 0.12
    # Demand-model parameters (elasticity per segment, capacity scale, cost).
    assert rules.elasticity_for("business") == 1.30
    assert rules.elasticity_for("leisure") == 1.45
    assert rules.base_demand_per_seat == 1.1
    assert rules.marginal_cost_ratio == 0.30


def test_load_routes_carries_seats_and_segment():
    routes = load_routes()
    assert routes["MXP-LHR"].segment == "business"
    assert routes["MXP-BCN"].segment == "leisure"
    assert all(r.seats >= 100 for r in routes.values())


def test_load_routes_and_get_route():
    routes = load_routes()
    assert "MXP-BCN" in routes
    route = get_route("MXP-BCN")
    assert route.destination_country == "ES"


def test_unknown_route_raises():
    with pytest.raises(UnknownRouteError):
        get_route("NOPE-XXX")


def test_is_holiday_known_date():
    # New Year's Day is a public holiday in Spain.
    assert is_holiday("ES", date(2026, 1, 1)) is True
    assert is_holiday("ES", date(2026, 4, 15)) is False


def test_is_holiday_unknown_country_is_false():
    assert is_holiday("ZZ", date(2026, 1, 1)) is False
