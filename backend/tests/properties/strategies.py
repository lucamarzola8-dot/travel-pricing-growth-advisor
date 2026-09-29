"""Shared hypothesis strategies for property-based tests."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from hypothesis import strategies as st

from travel_advisor.models import Event, MarketOpportunity, PricingRules, Route


@st.composite
def routes(draw) -> Route:
    """A valid route: floor <= base within a sane band, floor <= ceiling."""
    floor = draw(st.integers(min_value=10, max_value=200))
    base = draw(st.integers(min_value=floor, max_value=floor + 300))
    ceiling = draw(st.integers(min_value=base, max_value=base + 500))
    return Route(
        code="P-XXX",
        origin="P",
        destination_market="XXX",
        destination_country="ES",
        base_fare=Decimal(base),
        floor=Decimal(floor),
        ceiling=Decimal(ceiling),
        seats=draw(st.integers(min_value=50, max_value=300)),
        segment=draw(st.sampled_from(["business", "leisure", "other"])),
    )


travel_dates = st.dates(min_value=date(2026, 1, 1), max_value=date(2027, 12, 31))


@st.composite
def events_near(draw, travel_date: date) -> Event:
    """An event within +/- 3 days of the given travel date."""
    offset = draw(st.integers(min_value=-3, max_value=3))
    impact = draw(st.floats(min_value=0.0, max_value=2.0, allow_nan=False, allow_infinity=False))
    return Event("XXX", travel_date + timedelta(days=offset), "Ev", impact)


@st.composite
def pricing_rules(draw) -> PricingRules:
    """A valid arbitrary ruleset (non-negative boosts, sane multipliers)."""
    months = st.integers(min_value=1, max_value=12)
    dow = st.floats(min_value=0.7, max_value=1.3, allow_nan=False, allow_infinity=False)
    return PricingRules(
        peak_months=frozenset(draw(st.sets(months, max_size=4))),
        peak_multiplier=draw(st.floats(min_value=1.0, max_value=2.0, allow_nan=False, allow_infinity=False)),
        low_months=frozenset(draw(st.sets(months, max_size=4))),
        low_multiplier=draw(st.floats(min_value=0.5, max_value=1.0, allow_nan=False, allow_infinity=False)),
        shoulder_multiplier=draw(st.floats(min_value=0.8, max_value=1.2, allow_nan=False, allow_infinity=False)),
        holiday_boost=draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)),
        proximity_days=draw(st.integers(min_value=0, max_value=7)),
        dow_multipliers=tuple(draw(st.lists(dow, min_size=7, max_size=7))),
        lead_time_boost=draw(st.floats(min_value=0.0, max_value=0.5, allow_nan=False, allow_infinity=False)),
        lead_time_days=draw(st.integers(min_value=1, max_value=60)),
        # Elasticity must stay > 1 for a finite markup; keep it in a sane band.
        elasticity=draw(st.floats(min_value=1.05, max_value=3.0, allow_nan=False, allow_infinity=False)),
        elasticity_by_segment=(
            ("business", draw(st.floats(min_value=1.05, max_value=3.0, allow_nan=False, allow_infinity=False))),
            ("leisure", draw(st.floats(min_value=1.05, max_value=3.0, allow_nan=False, allow_infinity=False))),
        ),
        base_demand_per_seat=draw(st.floats(min_value=0.1, max_value=4.0, allow_nan=False, allow_infinity=False)),
        marginal_cost_ratio=draw(st.floats(min_value=0.0, max_value=0.9, allow_nan=False, allow_infinity=False)),
    )


@st.composite
def market_lists(draw) -> list[MarketOpportunity]:
    n = draw(st.integers(min_value=1, max_value=6))
    scores = draw(
        st.lists(
            st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
            min_size=n,
            max_size=n,
        )
    )
    return [MarketOpportunity(f"M{i}", scores[i]) for i in range(n)]
