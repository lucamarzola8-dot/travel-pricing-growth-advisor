"""Property-based tests for the growth advisor (Kiro Lesson 4).

Encodes G1..G5 from the design over generated market/score/budget inputs.
"""

from __future__ import annotations

from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from travel_advisor.growth import allocate, opportunity_score, rank
from travel_advisor.models import MarketOpportunity

from .strategies import market_lists

_budgets = st.integers(min_value=0, max_value=10_000_000).map(lambda c: Decimal(c) / 100)


# G1 (req 3.2): allocations sum exactly to the total budget.
@given(total=_budgets, markets=market_lists())
def test_g1_allocations_sum_to_total(total, markets):
    allocations = allocate(total, markets)
    assert sum(a.amount for a in allocations) == total


# G2 (req 3.3): every allocation is non-negative.
@given(total=_budgets, markets=market_lists())
def test_g2_allocations_non_negative(total, markets):
    for a in allocate(total, markets):
        assert a.amount >= 0


# G3 (req 3.4): a strictly higher score never gets a smaller allocation.
@given(total=_budgets, markets=market_lists())
def test_g3_higher_score_not_less(total, markets):
    by_market = {a.market: a.amount for a in allocate(total, markets)}
    score = {m.market: m.score for m in markets}
    for a in markets:
        for b in markets:
            if score[a.market] > score[b.market]:
                assert by_market[a.market] >= by_market[b.market]


# G4 (req 3.1): opportunity_score is monotonic non-decreasing in demand.
@given(
    d1=st.floats(min_value=0, max_value=1000, allow_nan=False, allow_infinity=False),
    d2=st.floats(min_value=0, max_value=1000, allow_nan=False, allow_infinity=False),
    margin=st.floats(min_value=0, max_value=1000, allow_nan=False, allow_infinity=False),
)
def test_g4_score_monotonic_in_demand(d1, d2, margin):
    if d1 <= d2:
        assert opportunity_score(d1, margin) <= opportunity_score(d2, margin)


# G5 (req 3.5): rank output is sorted by non-increasing score.
@given(markets=market_lists())
def test_g5_rank_sorted_descending(markets):
    ranked = rank(markets)
    scores = [m.score for m in ranked]
    assert scores == sorted(scores, reverse=True)
