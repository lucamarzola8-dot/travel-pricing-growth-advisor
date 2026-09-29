"""Tests for the advisor narrative (insight + action + evidence) and the Markdown
report. Every claim in the narrative must trace back to an engine result or a
rule parameter (requirement 4.3)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from travel_advisor.demand import optimize_price
from travel_advisor.models import Allocation, Event, PricingRules, Route
from travel_advisor.storyline import (
    advisor_insights,
    render_markdown_report,
)


def make_route(seats=180, segment="leisure") -> Route:
    return Route(
        code="TST-XXX",
        origin="TST",
        origin_city="Testville",
        destination_market="XXX",
        destination_city="Xanadu",
        destination_country="ES",
        base_fare=Decimal("150.00"),
        floor=Decimal("80.00"),
        ceiling=Decimal("400.00"),
        seats=seats,
        segment=segment,
    )


def period(route: Route, start: date, n: int, events, rules: PricingRules):
    out = []
    for i in range(n):
        d = start + timedelta(days=i)
        out.append((d, optimize_price(route, d, holiday=False, events=events, rules=rules)))
    return out


def test_peak_insight_dates_campaign_from_rules():
    """The 'campaigns live by' date is peak minus campaign_lead_days — not invented."""
    route = make_route()
    rules = PricingRules(campaign_lead_days=14)
    start = date(2026, 4, 13)  # Monday
    event = Event("XXX", date(2026, 4, 18), "Big Festival", 0.50)  # Saturday
    days = period(route, start, 7, [event], rules)
    insights = advisor_insights("Testville → Xanadu", days, rules)

    peak = [i for i in insights if i.kind == "peak"]
    assert len(peak) == 1
    assert "2026-04-18" in peak[0].insight  # the event day is the demand peak
    assert "Big Festival" in peak[0].insight
    assert (date(2026, 4, 18) - timedelta(days=14)).isoformat() in peak[0].action
    assert "14 days" in peak[0].action
    assert "campaign lead = 14 days" in peak[0].evidence


def test_capacity_insight_counts_capped_days():
    route = make_route(seats=180)
    rules = PricingRules()
    start = date(2026, 4, 13)
    event = Event("XXX", date(2026, 4, 18), "Big Festival", 0.50)
    days = period(route, start, 7, [event], rules)
    n_capped = sum(1 for _, o in days if o.capacity_constrained)
    insights = advisor_insights("R", days, rules)
    cap = [i for i in insights if i.kind == "capacity"]
    if n_capped:
        assert len(cap) == 1
        assert f"{n_capped} of 7 days" in cap[0].insight
        assert "180 seats" in cap[0].insight
    else:
        assert cap == []


def test_uplift_insight_matches_period_totals():
    route = make_route()
    rules = PricingRules()
    start = date(2026, 4, 13)
    event = Event("XXX", date(2026, 4, 18), "Big Festival", 0.50)
    days = period(route, start, 7, [event], rules)
    rec = sum((o.recommended_profit for _, o in days), Decimal("0"))
    opt = sum((o.expected_profit for _, o in days), Decimal("0"))
    pct = float((opt - rec) / rec * 100)
    insights = advisor_insights("R", days, rules)
    up = [i for i in insights if i.kind == "uplift"]
    if pct >= 1.0:
        assert len(up) == 1
        assert f"{pct:+.1f}%" in up[0].insight
    else:
        assert up == []


def test_weekday_insight_reads_rules():
    rules = PricingRules(dow_multipliers=(0.96, 0.94, 0.94, 1.00, 1.08, 1.03, 1.08))
    days = period(make_route(), date(2026, 4, 13), 7, [], rules)
    insights = advisor_insights("R", days, rules)
    wd = [i for i in insights if i.kind == "weekday"][0]
    # Lowest is Tue (0.94, first index wins the tie), highest is Fri (1.08, first index).
    assert "Tue" in wd.insight and "Fri" in wd.insight
    assert "-6%" in wd.insight and "+8%" in wd.insight


def test_quiet_period_yields_quiet_insight_and_no_peak():
    rules = PricingRules()
    days = period(make_route(), date(2026, 4, 13), 7, [], rules)  # no events
    insights = advisor_insights("R", days, rules)
    kinds = [i.kind for i in insights]
    assert "peak" not in kinds
    assert kinds[0] == "quiet"


def test_advisor_is_deterministic():
    rules = PricingRules()
    event = Event("XXX", date(2026, 4, 18), "Big Festival", 0.50)
    days = period(make_route(), date(2026, 4, 13), 7, [event], rules)
    a = advisor_insights("R", days, rules)
    b = advisor_insights("R", days, rules)
    assert a == b


def test_empty_period_gives_no_insights():
    assert advisor_insights("R", [], PricingRules()) == []


def test_markdown_report_has_sections_and_numbers():
    route = make_route()
    rules = PricingRules()
    start = date(2026, 4, 13)
    event = Event("XXX", date(2026, 4, 18), "Big Festival", 0.50)
    days = period(route, start, 7, [event], rules)
    insights = advisor_insights("Testville → Xanadu (TST-XXX)", days, rules)
    allocations = [Allocation("XXX", Decimal("6000.00")), Allocation("YYY", Decimal("4000.00"))]
    md = render_markdown_report(
        route_label="Testville → Xanadu (TST-XXX)",
        start=start,
        days=days,
        insights=insights,
        allocations=allocations,
        budget=Decimal("10000"),
        rules=rules,
    )
    assert md.startswith("# Pricing & Growth Recommendation")
    for section in ("## Headline", "## Recommendations", "## Day-by-day prices", "## Google Ads budget split"):
        assert section in md
    # One table row per day, and the event appears as a driver.
    assert md.count("| 2026-04-") == 7
    assert "Big Festival" in md
    # Budget split ordered by amount desc.
    assert md.index("| XXX |") < md.index("| YYY |")
    # Deterministic.
    assert md == render_markdown_report(
        route_label="Testville → Xanadu (TST-XXX)",
        start=start,
        days=days,
        insights=insights,
        allocations=allocations,
        budget=Decimal("10000"),
        rules=rules,
    )


def test_markdown_report_empty_period():
    md = render_markdown_report(
        route_label="R", start=date(2026, 1, 1), days=[], insights=[],
        allocations=[], budget=Decimal("0"), rules=PricingRules(),
    )
    assert "No days in range" in md
