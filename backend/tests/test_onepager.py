"""Tests for the deterministic one-pager SVG generator and endpoint."""

from __future__ import annotations

from decimal import Decimal

from travel_advisor import api
from travel_advisor.models import Allocation, Factor, MarketOpportunity, PricedDay
from travel_advisor.onepager import build_onepager_svg


def _sample_days() -> list[PricedDay]:
    return [
        PricedDay("2026-03-01", 120.0, 120.0, 0.0, (Factor("seasonality", 1.0, "shoulder"),)),
        PricedDay("2026-03-02", 162.0, 120.0, 35.0, (Factor("event", 1.35, "MWC within 3 days"),)),
    ]


def test_onepager_is_deterministic():
    args = dict(
        route_label="Milan \u2192 Barcelona (MXP-BCN)",
        period="2026-03-01 · 2 days",
        days=_sample_days(),
        markets=[MarketOpportunity("BCN", 2.6), MarketOpportunity("CDG", 2.7)],
        allocations=[Allocation("CDG", Decimal("55.00")), Allocation("BCN", Decimal("45.00"))],
        storyline=["MXP-BCN: recommended fare 162.00 is 35% above base."],
    )
    a = build_onepager_svg(**args)
    b = build_onepager_svg(**args)
    assert a == b  # byte-identical for identical inputs


def test_onepager_contains_key_elements():
    svg = build_onepager_svg(
        route_label="Milan \u2192 Barcelona (MXP-BCN)",
        period="2026-03-01 · 2 days",
        days=_sample_days(),
        markets=[MarketOpportunity("BCN", 2.6)],
        allocations=[Allocation("BCN", Decimal("100.00"))],
        storyline=["Top growth market is BCN."],
    )
    assert svg.startswith("<svg")
    assert svg.rstrip().endswith("</svg>")
    assert "MXP-BCN" in svg
    assert "BCN" in svg
    assert "<rect" in svg  # bars rendered


def test_get_onepager_endpoint_returns_svg():
    status, svg, content_type = api.get_onepager(
        {"route": "MXP-BCN", "date": "2026-03-01", "days": "8", "budget": "100000"}
    )
    assert status == 200
    assert content_type == "image/svg+xml"
    assert svg.startswith("<svg")


def test_get_onepager_bad_days():
    import pytest

    with pytest.raises(api.BadRequest):
        api.get_onepager(
            {"route": "MXP-BCN", "date": "2026-03-01", "days": "999", "budget": "100000"}
        )


def test_get_onepager_unknown_route():
    import pytest

    with pytest.raises(api.BadRequest):
        api.get_onepager(
            {"route": "ZZZ-ZZZ", "date": "2026-03-01", "days": "8", "budget": "100000"}
        )
