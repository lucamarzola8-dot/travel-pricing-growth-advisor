"""Example-based tests for the growth advisor and storyline."""

from __future__ import annotations

from decimal import Decimal

from travel_advisor.growth import allocate, opportunity_score, rank
from travel_advisor.models import Allocation, MarketOpportunity, Factor, PriceResult
from travel_advisor.storyline import build_storyline


def test_opportunity_score_non_negative_and_monotonic():
    assert opportunity_score(0, 0) == 0.0
    assert opportunity_score(10, 0) > opportunity_score(5, 0)
    assert opportunity_score(5, 10) > opportunity_score(5, 5)


def test_opportunity_score_roi_falls_with_higher_cpc():
    """ROI framing: same demand/margin but a higher CPC yields a lower score."""
    cheap = opportunity_score(80, 0.6, cpc_eur=0.60)
    dear = opportunity_score(80, 0.6, cpc_eur=1.20)
    assert cheap > dear


def test_opportunity_score_rises_with_demand_and_margin_at_fixed_cpc():
    base = opportunity_score(50, 0.5, cpc_eur=0.80)
    assert opportunity_score(90, 0.5, cpc_eur=0.80) > base  # more demand
    assert opportunity_score(50, 0.9, cpc_eur=0.80) > base  # more margin


def test_load_markets_has_advertising_fields():
    from travel_advisor.data import load_markets

    markets = load_markets()
    assert "LHR" in markets
    lhr = markets["LHR"]
    assert lhr.demand_index > 0 and lhr.cpc_eur > 0 and 0 <= lhr.margin_index <= 1


def test_normalize_interest_scales_to_0_100():
    from travel_advisor.growth import normalize_interest

    out = normalize_interest({"A": 50.0, "B": 100.0, "C": 0.0})
    assert out == {"A": 50, "B": 100, "C": 0}


def test_normalize_interest_edge_cases():
    from travel_advisor.growth import normalize_interest

    assert normalize_interest({}) == {}
    # all zero -> all zero (no division by zero)
    assert normalize_interest({"A": 0.0, "B": 0.0}) == {"A": 0, "B": 0}
    # negatives floored at 0
    assert normalize_interest({"A": -10.0, "B": 20.0}) == {"A": 0, "B": 100}


def test_expected_outcome_computes_clicks_bookings_revenue():
    from travel_advisor.growth import expected_outcome

    # €1000 at €1.00 CPC -> 1000 clicks; 3% conv -> 30 bookings; €200 AOV -> €6000
    out = expected_outcome(Decimal("1000"), cpc_eur=1.0, conversion_rate=0.03, avg_booking_value_eur=200.0)
    assert out["clicks"] == 1000.0
    assert round(out["bookings"], 1) == 30.0
    assert round(out["revenue"], 2) == 6000.0


def test_expected_outcome_monotonic_and_non_negative():
    from travel_advisor.growth import expected_outcome

    small = expected_outcome(Decimal("100"), 0.8, 0.03, 180.0)
    big = expected_outcome(Decimal("500"), 0.8, 0.03, 180.0)
    assert big["revenue"] > small["revenue"]
    zero = expected_outcome(Decimal("0"), 0.8, 0.03, 180.0)
    assert zero["clicks"] == 0.0 and zero["revenue"] == 0.0


def test_saturation_allocation_sums_to_budget():
    from travel_advisor.growth import allocate_with_saturation
    from travel_advisor.models import MarketOpportunity

    markets = [
        MarketOpportunity("A", 200.0),
        MarketOpportunity("B", 150.0),
        MarketOpportunity("C", 100.0),
    ]
    allocs = allocate_with_saturation(Decimal("100000.00"), markets)
    assert sum(a.amount for a in allocs) == Decimal("100000.00")
    assert all(a.amount >= 0 for a in allocs)


def test_saturation_marginal_decreases_vs_linear():
    """Under diminishing returns, the top market gets a smaller share than a flat
    proportional split would give it (budget spreads out)."""
    from travel_advisor.growth import allocate, allocate_with_saturation
    from travel_advisor.models import MarketOpportunity

    markets = [MarketOpportunity("A", 300.0), MarketOpportunity("B", 100.0)]
    linear = {a.market: a.amount for a in allocate(Decimal("100000"), markets)}
    sat = {a.market: a.amount for a in allocate_with_saturation(Decimal("100000"), markets)}
    # Saturation gives the top market less than the pure proportional split.
    assert sat["A"] < linear["A"]
    assert sat["B"] > linear["B"]


def test_saturation_all_zero_scores_falls_back():
    from travel_advisor.growth import allocate_with_saturation
    from travel_advisor.models import MarketOpportunity

    markets = [MarketOpportunity("A", 0.0), MarketOpportunity("B", 0.0)]
    allocs = allocate_with_saturation(Decimal("100.00"), markets)
    assert sum(a.amount for a in allocs) == Decimal("100.00")


def test_ad_breakdown_channels_sum_to_amount():
    from travel_advisor.data import ad_breakdown

    split, keywords = ad_breakdown("BCN", Decimal("1000.00"))
    assert sum(amt for _ch, amt in split) == Decimal("1000.00")
    assert all(amt >= 0 for _ch, amt in split)
    assert len(keywords) >= 1


def test_demand_uplift_is_at_least_one_and_monotonic():
    from travel_advisor.growth import demand_uplift

    assert demand_uplift(0, 0) == 1.0
    assert demand_uplift(2, 0) > demand_uplift(0, 0)
    assert demand_uplift(0, 3) > demand_uplift(0, 0)
    assert demand_uplift(2, 3) > demand_uplift(1, 1)


def test_rank_orders_by_descending_score():
    markets = [
        MarketOpportunity("A", 1.0),
        MarketOpportunity("B", 3.0),
        MarketOpportunity("C", 2.0),
    ]
    ranked = rank(markets)
    assert [m.market for m in ranked] == ["B", "C", "A"]


def test_allocate_sums_to_total():
    markets = [
        MarketOpportunity("A", 3.0),
        MarketOpportunity("B", 1.0),
    ]
    allocations = allocate(Decimal("100.00"), markets)
    assert sum(a.amount for a in allocations) == Decimal("100.00")


def test_allocate_higher_score_gets_more():
    markets = [
        MarketOpportunity("A", 3.0),
        MarketOpportunity("B", 1.0),
    ]
    allocations = {a.market: a.amount for a in allocate(Decimal("100.00"), markets)}
    assert allocations["A"] > allocations["B"]


def test_allocate_all_zero_scores_even_split():
    markets = [MarketOpportunity("A", 0.0), MarketOpportunity("B", 0.0)]
    allocations = allocate(Decimal("100.00"), markets)
    assert sum(a.amount for a in allocations) == Decimal("100.00")
    assert all(a.amount >= 0 for a in allocations)


def test_allocate_empty_markets():
    assert allocate(Decimal("100.00"), []) == []


def test_build_storyline_references_real_factors():
    price = PriceResult(
        price=Decimal("236.00"),
        base=Decimal("200.00"),
        factors=(
            Factor("seasonality", 1.05, "peak season"),
            Factor("event", 1.06, "Mobile World Congress within 3 days"),
        ),
    )
    allocations = [Allocation("BCN", Decimal("60.00")), Allocation("CDG", Decimal("40.00"))]
    story = build_storyline("MXP-BCN", price, allocations)
    assert any("18%" in line for line in story)  # (236-200)/200 = 18%
    assert any("Mobile World Congress" in line for line in story)
    assert any("BCN" in line for line in story)
