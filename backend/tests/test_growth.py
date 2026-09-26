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
