"""Storyline generation — turn computed results into business-language insights.

Every insight is backed by a real :class:`Factor` or allocation; nothing is
fabricated (requirement 4.3). The output is a plain list of sentences a consultant
can read to a client, plus the numbers behind them.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from .models import Allocation, PriceResult, PricingRules, RevenueOptimization

_WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


@dataclass(frozen=True)
class Insight:
    """One advisor recommendation for a business stakeholder.

    ``insight`` states what the numbers show, ``action`` what to do about it, and
    ``evidence`` the computed figures that back both — so nothing here is opinion
    without a number behind it (requirement 4.3).
    """

    insight: str
    action: str
    evidence: str
    kind: str  # "peak" | "capacity" | "uplift" | "weekday" | "quiet"


def _eur(v: Decimal | float, digits: int = 0) -> str:
    return f"\u20ac{float(v):,.{digits}f}"


def advisor_insights(
    route_label: str,
    days: list[tuple[date, RevenueOptimization]],
    rules: PricingRules,
) -> list[Insight]:
    """Turn a period's optimisations into insight + action pairs (pure).

    Every sentence is derived from the ``RevenueOptimization`` results passed in
    and the data-driven ``rules`` (e.g. the campaign lead time); no figure is
    invented. Deterministic for equal inputs.
    """
    if not days:
        return []
    out: list[Insight] = []
    n = len(days)

    # 1. Demand peak: the day with the strongest demand context, but only when a
    #    real driver (event / holiday) is behind it — a busy Friday is the weekday
    #    pattern, not a peak worth a dedicated campaign.
    peak_date, peak = max(days, key=lambda t: (t[1].demand_multiplier, t[0]))
    peak_pct = (peak.demand_multiplier - 1.0) * 100
    drivers = [f.reason for f in peak.factors if f.kind in ("event", "holiday")]
    if drivers and peak_pct >= 5.0:
        launch = peak_date - timedelta(days=rules.campaign_lead_days)
        driver_txt = "; ".join(drivers)
        out.append(
            Insight(
                kind="peak",
                insight=(
                    f"Demand on {route_label} peaks on {peak_date.isoformat()} "
                    f"({peak_pct:+.0f}% vs an ordinary day), driven by {driver_txt}."
                ),
                action=(
                    f"Have Google Ads campaigns live by {launch.isoformat()} "
                    f"({rules.campaign_lead_days} days ahead) so they capture the "
                    f"search interest that builds before the peak."
                ),
                evidence=(
                    f"demand multiplier x{peak.demand_multiplier:.2f}; optimal price "
                    f"{_eur(peak.optimal_price, 2)}; campaign lead = "
                    f"{rules.campaign_lead_days} days (pricing-rules.json)"
                ),
            )
        )

    # 2. Capacity: on how many days is the price set by seats, not by markup?
    capped = [(d, o) for d, o in days if o.capacity_constrained]
    if capped:
        first, last = capped[0][0], capped[-1][0]
        span = first.isoformat() if first == last else f"{first.isoformat()} to {last.isoformat()}"
        top_d, top_o = max(capped, key=lambda t: (t[1].optimal_price, t[0]))
        out.append(
            Insight(
                kind="capacity",
                insight=(
                    f"Seat capacity binds on {len(capped)} of {n} days ({span}): the "
                    f"aircraft fills at the markup price, so the price is set by the "
                    f"{top_o.seats} seats, peaking at {_eur(top_o.optimal_price, 2)} on "
                    f"{top_d.isoformat()}."
                ),
                action=(
                    "Do not discount these dates; hold the optimal fare and shift "
                    "promotional budget to non-capped days where extra demand still "
                    "converts into extra seats sold."
                ),
                evidence=(
                    f"expected load factor 100% on {len(capped)} days; markup price "
                    f"{_eur(top_o.unconstrained_price, 2)} vs market-clearing "
                    f"{_eur(top_o.optimal_price, 2)}"
                ),
            )
        )

    # 3. Profit uplift of optimising vs the rule-based fare over the period.
    rec_total = sum((o.recommended_profit for _, o in days), Decimal("0"))
    opt_total = sum((o.expected_profit for _, o in days), Decimal("0"))
    if rec_total > 0:
        uplift_pct = float((opt_total - rec_total) / rec_total * 100)
        if uplift_pct >= 1.0:
            best_d, best_o = max(days, key=lambda t: (t[1].uplift_pct, t[0]))
            out.append(
                Insight(
                    kind="uplift",
                    insight=(
                        f"Pricing at the profit-optimal level instead of the rule-based "
                        f"fare adds {uplift_pct:+.1f}% expected profit over {n} days "
                        f"({_eur(opt_total - rec_total)} on {_eur(rec_total)})."
                    ),
                    action=(
                        f"Adopt the optimal fare first on {best_d.isoformat()} "
                        f"({best_o.uplift_pct:+.1f}% profit), then roll it out across the "
                        f"period."
                    ),
                    evidence=(
                        f"rule-based profit {_eur(rec_total)} vs optimal {_eur(opt_total)}; "
                        f"segment {best_o.segment}, elasticity {best_o.elasticity:.2f}"
                    ),
                )
            )

    # 4. Weekday pattern from the rules: cheapest vs dearest departure days.
    dow = rules.dow_multipliers
    lo_i = min(range(7), key=lambda i: (dow[i], i))
    hi_i = max(range(7), key=lambda i: (dow[i], -i))
    if dow[hi_i] > dow[lo_i]:
        out.append(
            Insight(
                kind="weekday",
                insight=(
                    f"{_WEEKDAYS[hi_i]} departures carry the highest weekday premium "
                    f"({(dow[hi_i] - 1) * 100:+.0f}%), {_WEEKDAYS[lo_i]} the lowest "
                    f"({(dow[lo_i] - 1) * 100:+.0f}%)."
                ),
                action=(
                    f"Target price-sensitive audiences with {_WEEKDAYS[lo_i]} departures "
                    f"and keep premium messaging for {_WEEKDAYS[hi_i]}."
                ),
                evidence=(
                    f"day_of_week_multipliers {_WEEKDAYS[lo_i]} x{dow[lo_i]:.2f}, "
                    f"{_WEEKDAYS[hi_i]} x{dow[hi_i]:.2f} (pricing-rules.json)"
                ),
            )
        )

    # 5. Quiet period: no event or holiday anywhere in the window.
    any_driver = any(
        f.kind in ("event", "holiday") for _, o in days for f in o.factors
    )
    if not any_driver:
        out.insert(
            0,
            Insight(
                kind="quiet",
                insight=(
                    f"No holiday or event lifts demand on {route_label} in this "
                    f"{n}-day window; prices follow season and weekday only."
                ),
                action=(
                    "Use this window for always-on campaigns; reserve peak budgets for "
                    "dates with events or holidays."
                ),
                evidence="max demand multiplier "
                f"x{max(o.demand_multiplier for _, o in days):.2f}",
            ),
        )
    return out


def pricing_insights(route_code: str, result: PriceResult) -> list[str]:
    """Insights explaining a price versus its base fare (req 4.1 / 4.2)."""
    insights: list[str] = []
    delta = result.delta_pct

    if abs(delta) < 0.5:
        insights.append(
            f"{route_code}: recommended fare is in line with the base fare "
            f"({result.price})."
        )
    else:
        direction = "above" if delta > 0 else "below"
        reasons = [f.reason for f in result.factors if f.kind != "seasonality"]
        reason_text = "; ".join(reasons) if reasons else "seasonal demand"
        insights.append(
            f"{route_code}: recommended fare {result.price} is {abs(delta):.0f}% "
            f"{direction} base — driven by {reason_text}."
        )

    # Call out an event driver explicitly if present.
    event_factors = [f for f in result.factors if f.kind == "event"]
    if event_factors:
        insights.append(
            f"Demand uplift expected from: {', '.join(f.reason for f in event_factors)}."
        )
    return insights


def growth_insights(allocations: list[Allocation]) -> list[str]:
    """Insights describing where budget should go (req 4.1)."""
    if not allocations:
        return []
    ranked = sorted(allocations, key=lambda a: a.amount, reverse=True)
    top = ranked[0]
    total = sum(a.amount for a in allocations)
    insights = [
        f"Best Google Ads ROI is {top.market}: allocate {top.amount} of the "
        f"{total} ad budget there first."
    ]
    if len(ranked) > 1:
        others = ", ".join(f"{a.market} ({a.amount})" for a in ranked[1:])
        insights.append(f"Remaining ad budget is spread across: {others}.")
    return insights


def build_storyline(
    route_code: str,
    price: PriceResult,
    allocations: list[Allocation],
) -> list[str]:
    """Compose the full client-ready storyline from computed results."""
    return pricing_insights(route_code, price) + growth_insights(allocations)


def render_markdown_report(
    *,
    route_label: str,
    start: date,
    days: list[tuple[date, RevenueOptimization]],
    insights: list[Insight],
    allocations: list[Allocation],
    budget: Decimal,
    rules: PricingRules,
) -> str:
    """Render a consulting-style one-pager in Markdown (pure, deterministic).

    Sections: headline numbers, recommendations (insight / action / evidence),
    the day-by-day price table, and the ad-budget split. Every number comes from
    the engine results passed in.
    """
    if not days:
        return f"# {route_label}\n\nNo days in range.\n"
    n = len(days)
    end = days[-1][0]
    rec_total = sum((o.recommended_profit for _, o in days), Decimal("0"))
    opt_total = sum((o.expected_profit for _, o in days), Decimal("0"))
    uplift = float((opt_total - rec_total) / rec_total * 100) if rec_total else 0.0
    capped = sum(1 for _, o in days if o.capacity_constrained)
    avg_lf = sum(o.load_factor for _, o in days) / n
    seg = days[0][1].segment
    e = days[0][1].elasticity

    lines: list[str] = []
    lines.append(f"# Pricing & Growth Recommendation — {route_label}")
    lines.append("")
    lines.append(
        f"*Period {start.isoformat()} → {end.isoformat()} ({n} days) · "
        f"{seg} segment, elasticity {e:.2f} · Google Ads budget {_eur(budget)}*"
    )
    lines.append("")
    lines.append("## Headline")
    lines.append("")
    lines.append(f"- Expected profit at optimal prices: **{_eur(opt_total)}** "
                 f"({uplift:+.1f}% vs rule-based fares, {_eur(rec_total)}).")
    lines.append(f"- Seat capacity sets the price on **{capped} of {n} days**; "
                 f"average expected load factor {avg_lf * 100:.0f}%.")
    lines.append(f"- Campaigns should go live **{rules.campaign_lead_days} days** before a "
                 f"demand peak (planning rule).")
    lines.append("")
    lines.append("## Recommendations")
    lines.append("")
    for i, ins in enumerate(insights, 1):
        lines.append(f"### {i}. {ins.insight}")
        lines.append("")
        lines.append(f"**Action:** {ins.action}")
        lines.append("")
        lines.append(f"*Evidence:* {ins.evidence}")
        lines.append("")
    lines.append("## Day-by-day prices")
    lines.append("")
    lines.append("| Date | Day | Rule-based | Optimal | Capacity | Load | Profit | Drivers |")
    lines.append("|---|---|---:|---:|:---:|---:|---:|---|")
    for d, o in days:
        drivers = ", ".join(
            f.reason for f in o.factors if f.kind in ("event", "holiday")
        ) or "—"
        lines.append(
            f"| {d.isoformat()} | {_WEEKDAYS[d.weekday()]} | {_eur(o.recommended, 2)} | "
            f"{_eur(o.optimal_price, 2)} | {'seats' if o.capacity_constrained else ''} | "
            f"{o.load_factor * 100:.0f}% | {_eur(o.expected_profit)} | {drivers} |"
        )
    lines.append("")
    if allocations:
        lines.append("## Google Ads budget split")
        lines.append("")
        lines.append("| Market | Allocation |")
        lines.append("|---|---:|")
        for a in sorted(allocations, key=lambda x: x.amount, reverse=True):
            lines.append(f"| {a.market} | {_eur(a.amount)} |")
        lines.append("")
    lines.append("---")
    lines.append(
        "*Deterministic output of the Travel Pricing & Growth Advisor engine. "
        "Offline seed data and public holidays; figures are illustrative.*"
    )
    lines.append("")
    return "\n".join(lines)
