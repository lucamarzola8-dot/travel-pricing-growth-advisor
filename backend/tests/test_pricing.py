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
    # April -> shoulder season, multiplier 1.0
    result = price_for(route, date(2026, 4, 15), holiday=False, events=[])
    assert result.price == Decimal("100.00")
    assert [f.kind for f in result.factors] == ["seasonality"]


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
    result = price_for(route, date(2026, 4, 15), holiday=False, events=[far_event])
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


def test_deterministic():
    route = make_route()
    event = Event("XXX", date(2026, 4, 16), "Fair", 0.2)
    a = price_for(route, date(2026, 4, 15), holiday=True, events=[event])
    b = price_for(route, date(2026, 4, 15), holiday=True, events=[event])
    assert a == b


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
