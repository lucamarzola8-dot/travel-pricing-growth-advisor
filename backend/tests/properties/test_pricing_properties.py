"""Property-based tests for the pricing engine (Kiro Lesson 4).

These encode the general rules the pricing engine must always satisfy — P1..P5 in
the design — checked over hundreds of generated inputs rather than fixed examples.
"""

from __future__ import annotations

from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from travel_advisor.models import Event
from travel_advisor.pricing import price_for

from .strategies import events_near, routes, travel_dates


# P1 (req 2.2 / 2.3): price is always within [floor, ceiling].
@given(route=routes(), travel_date=travel_dates, holiday=st.booleans())
def test_p1_price_within_bounds(route, travel_date, holiday):
    result = price_for(route, travel_date, holiday=holiday)
    assert route.floor <= result.price <= route.ceiling


# P2 (req 2.4): adding a holiday never lowers the (pre-clamp) price.
# We use a route with a very high ceiling so clamping does not mask the effect.
@given(route=routes(), travel_date=travel_dates)
def test_p2_holiday_never_lowers(route, travel_date):
    from dataclasses import replace

    unclamped = replace(route, ceiling=Decimal("100000"), floor=Decimal("0"))
    without = price_for(unclamped, travel_date, holiday=False)
    with_hol = price_for(unclamped, travel_date, holiday=True)
    assert with_hol.price >= without.price


# P3 (req 2.5): adding an event within the window never lowers the price.
@given(data=st.data(), route=routes(), travel_date=travel_dates)
def test_p3_event_never_lowers(data, route, travel_date):
    from dataclasses import replace

    unclamped = replace(route, ceiling=Decimal("100000"), floor=Decimal("0"))
    event = data.draw(events_near(travel_date))
    without = price_for(unclamped, travel_date, holiday=False, events=[])
    with_ev = price_for(unclamped, travel_date, holiday=False, events=[event])
    assert with_ev.price >= without.price


# P4 (req 2.6): with no holiday and no events, the only factor is seasonality.
@given(route=routes(), travel_date=travel_dates)
def test_p4_no_signals_only_seasonality(route, travel_date):
    result = price_for(route, travel_date, holiday=False, events=[])
    assert [f.kind for f in result.factors] == ["seasonality"]


# P5 (req 2.7): equal inputs yield equal results (determinism).
@given(data=st.data(), route=routes(), travel_date=travel_dates, holiday=st.booleans())
def test_p5_deterministic(data, route, travel_date, holiday):
    events = [data.draw(events_near(travel_date))]
    a = price_for(route, travel_date, holiday=holiday, events=events)
    b = price_for(route, travel_date, holiday=holiday, events=events)
    assert a == b
