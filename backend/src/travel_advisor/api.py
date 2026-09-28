"""API layer — thin handlers over the pure core.

Handlers validate input, call the pricing/growth/storyline core, and return
JSON-serializable dicts. They do the I/O (data loading); the core stays pure.

The same functions back both the local dev server and AWS Lambda:
- ``get_price`` / ``get_growth`` / ``get_storyline`` take a plain params dict and
  return ``(status_code, body_dict)``.
- ``lambda_price`` / ``lambda_growth`` / ``lambda_storyline`` adapt those to the
  API Gateway proxy event/response shape.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from typing import Any

from . import data, growth, storyline
from .models import Allocation, MarketOpportunity, PriceResult, PricedDay


class BadRequest(ValueError):
    """Invalid client input; mapped to HTTP 400."""


# --------------------------------------------------------------------------- #
# Serialization helpers
# --------------------------------------------------------------------------- #

def _price_to_dict(route_code: str, result: PriceResult) -> dict[str, Any]:
    return {
        "route": route_code,
        "price": str(result.price),
        "base": str(result.base),
        "deltaPct": round(result.delta_pct, 2),
        "factors": [
            {"kind": f.kind, "multiplier": round(f.multiplier, 4), "reason": f.reason}
            for f in result.factors
        ],
    }


def _allocation_to_dict(a: Allocation) -> dict[str, Any]:
    return {"market": a.market, "amount": str(a.amount)}


# --------------------------------------------------------------------------- #
# Core request handling (params dict -> (status, body))
# --------------------------------------------------------------------------- #

def _require(params: dict[str, Any], key: str) -> str:
    value = params.get(key)
    if value is None or value == "":
        raise BadRequest(f"missing required parameter: {key}")
    return str(value)


def _parse_date(raw: str) -> date:
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise BadRequest(f"invalid date (expected YYYY-MM-DD): {raw!r}") from exc


def _parse_budget(raw: str) -> Decimal:
    try:
        budget = Decimal(raw)
    except Exception as exc:  # noqa: BLE001 - normalize any parse error to 400
        raise BadRequest(f"invalid budget: {raw!r}") from exc
    if budget < 0:
        raise BadRequest("budget must be non-negative")
    return budget


def _price_result_for(route_code: str, travel_date: date, data_dir=None) -> PriceResult:
    route = data.get_route(route_code, data_dir)  # raises UnknownRouteError
    events = data.events_for_market(data.load_events(data_dir), route.destination_market)
    holiday = data.is_holiday(route.destination_country, travel_date)
    rules = data.load_pricing_rules(data_dir)
    from .pricing import price_for

    return price_for(route, travel_date, holiday=holiday, events=events, rules=rules)


def get_routes(_params: dict[str, Any] | None = None, data_dir=None) -> tuple[int, dict[str, Any]]:
    """GET /routes -> available routes with human-friendly city labels.

    Lets the client show "Milan -> Barcelona (MXP-BCN)" instead of raw airport
    codes, so a user does not need to know airport codes by heart.
    """
    routes = data.load_routes(data_dir)
    items = []
    for r in sorted(routes.values(), key=lambda x: (x.destination_city or x.destination_market)):
        origin = r.origin_city or r.origin
        dest = r.destination_city or r.destination_market
        items.append(
            {
                "code": r.code,
                "origin": r.origin,
                "originCity": r.origin_city,
                "destinationMarket": r.destination_market,
                "destinationCity": r.destination_city,
                "destinationCountry": r.destination_country,
                "label": f"{origin} \u2192 {dest} ({r.code})",
            }
        )
    return 200, {"routes": items}


def get_price(params: dict[str, Any], data_dir=None) -> tuple[int, dict[str, Any]]:
    """GET /price?route=&date= -> price result (req 5.1 / 5.2)."""
    route_code = _require(params, "route")
    travel_date = _parse_date(_require(params, "date"))
    try:
        result = _price_result_for(route_code, travel_date, data_dir)
    except data.UnknownRouteError as exc:
        raise BadRequest(str(exc)) from exc
    return 200, _price_to_dict(route_code, result)


def _period_demand_uplift(
    route_code: str, start: date, days: int, data_dir=None
) -> tuple[str | None, float]:
    """Compute the demand uplift for the analysed route's market over the period.

    Counts national-holiday days and event hits (within the pricing proximity
    window) for the route's destination market across the ``days`` window, and
    turns them into an uplift factor. Returns (focus_market, uplift). If the route
    is unknown, returns (None, 1.0) so callers degrade gracefully.
    """
    from datetime import timedelta

    try:
        route = data.get_route(route_code, data_dir)
    except data.UnknownRouteError:
        return None, 1.0

    market = route.destination_market
    events = data.events_for_market(data.load_events(data_dir), market)
    rules = data.load_pricing_rules(data_dir)

    holiday_days = 0
    event_hits = 0
    for i in range(max(days, 0)):
        d = start + timedelta(days=i)
        if data.is_holiday(route.destination_country, d):
            holiday_days += 1
        for ev in events:
            if abs((ev.date - d).days) <= rules.proximity_days:
                event_hits += 1

    return market, growth.demand_uplift(holiday_days, event_hits)


def _market_opportunities(
    data_dir=None,
    *,
    focus_market: str | None = None,
    uplift: float = 1.0,
) -> list[MarketOpportunity]:
    """Derive per-market Google Ads opportunity scores from the seed data.

    Uses the advertising dataset (search-demand index, cost-per-click, and margin)
    to compute a ROI-of-ad-spend score per market. Deterministic and offline.
    Markets without advertising data are skipped.

    When ``focus_market``/``uplift`` are given, the focused market's score is
    multiplied by the uplift (>= 1.0), linking the pricing view (demand spikes on
    the analysed route) to the ads allocation.
    """
    ad_markets = data.load_markets(data_dir)
    opportunities: list[MarketOpportunity] = []
    for m in ad_markets.values():
        score = growth.opportunity_score(m.demand_index, m.margin_index, m.cpc_eur)
        if focus_market is not None and m.code == focus_market:
            score *= max(uplift, 1.0)
        opportunities.append(
            MarketOpportunity(
                market=m.code,
                score=score,
                demand_index=m.demand_index,
                cpc_eur=m.cpc_eur,
                margin_index=m.margin_index,
            )
        )
    return opportunities


def _growth_context(params: dict[str, Any], data_dir=None) -> tuple[str | None, float]:
    """Optional route/date/days context -> (focus_market, uplift).

    If a route and date are supplied, the analysed route's market gets a demand
    uplift derived from holidays/events in the window. Without context, returns
    (None, 1.0) so the allocation is the plain portfolio ranking.
    """
    route_code = params.get("route")
    date_raw = params.get("date")
    if not route_code or not date_raw:
        return None, 1.0
    start = _parse_date(date_raw)
    try:
        days = int(params.get("days", 14))
    except (TypeError, ValueError):
        days = 14
    return _period_demand_uplift(str(route_code), start, days, data_dir)


def get_growth(params: dict[str, Any], data_dir=None) -> tuple[int, dict[str, Any]]:
    """GET /growth?budget=[&route=&date=&days=] -> markets ranked by Google Ads ROI.

    ``budget`` is the Google Ads / marketing budget to allocate across markets,
    not a flight fare. If a route/date context is supplied, that route's market
    is demand-boosted from its holidays/events in the window, linking the pricing
    view to the ads allocation. Each market carries the drivers behind its score.
    """
    budget = _parse_budget(_require(params, "budget"))
    focus_market, uplift = _growth_context(params, data_dir)
    markets = _market_opportunities(data_dir, focus_market=focus_market, uplift=uplift)
    ranked = growth.rank(markets)
    # Diminishing-returns allocation: budget flows to the best marginal market.
    allocations = growth.allocate_with_saturation(budget, ranked)

    ad_markets = data.load_markets(data_dir)
    amount_by_market = {a.market: a.amount for a in allocations}

    market_rows = []
    total_clicks = total_bookings = total_revenue = 0.0
    for m in ranked:
        amt = amount_by_market.get(m.market, Decimal("0.00"))
        ad = ad_markets.get(m.market)
        conv = ad.conversion_rate if ad else 0.03
        aov = ad.avg_booking_value_eur if ad else 180.0
        outcome = growth.expected_outcome(amt, m.cpc_eur, conv, aov)
        total_clicks += outcome["clicks"]
        total_bookings += outcome["bookings"]
        total_revenue += outcome["revenue"]
        market_rows.append(
            {
                "market": m.market,
                "score": round(m.score, 2),
                "demandIndex": round(m.demand_index, 1),
                "cpcEur": round(m.cpc_eur, 2),
                "marginIndex": round(m.margin_index, 2),
                "focused": m.market == focus_market,
                "clicks": round(outcome["clicks"]),
                "bookings": round(outcome["bookings"], 1),
                "revenue": round(outcome["revenue"], 2),
            }
        )

    roas = round(total_revenue / float(budget), 2) if budget > 0 else 0.0
    return 200, {
        "budget": str(budget),
        "budgetKind": "google_ads",
        "focusMarket": focus_market,
        "focusUplift": round(uplift, 3),
        "markets": market_rows,
        "allocations": [_allocation_to_dict(a) for a in allocations],
        "breakdowns": [_ad_breakdown_dict(a, data_dir) for a in allocations],
        "totals": {
            "clicks": round(total_clicks),
            "bookings": round(total_bookings, 1),
            "revenue": round(total_revenue, 2),
            "roas": roas,
        },
    }


def _outcome_for_market(market: str, amount: Decimal, data_dir=None) -> dict[str, float]:
    """Expected clicks/bookings/revenue for a given spend in a market."""
    ad_markets = data.load_markets(data_dir)
    ad = ad_markets.get(market)
    if ad is None:
        return {"clicks": 0.0, "bookings": 0.0, "revenue": 0.0}
    return growth.expected_outcome(
        amount, ad.cpc_eur, ad.conversion_rate, ad.avg_booking_value_eur
    )


def get_simulate(params: dict[str, Any], data_dir=None) -> tuple[int, dict[str, Any]]:
    """GET /simulate?budget=&from=&to=&amount= -> what-if of moving ad budget.

    Starts from the recommended (saturating) allocation, moves ``amount`` euros
    from market ``from`` to market ``to``, and returns the before/after expected
    bookings and revenue plus the delta. Lets an analyst test "what if I shift
    budget from London to Lisbon?".
    """
    budget = _parse_budget(_require(params, "budget"))
    from_market = _require(params, "from")
    to_market = _require(params, "to")
    move = _parse_budget(_require(params, "amount"))

    ad_markets = data.load_markets(data_dir)
    if from_market not in ad_markets or to_market not in ad_markets:
        raise BadRequest("unknown market in 'from' or 'to'")

    ranked = growth.rank(_market_opportunities(data_dir))
    base = {a.market: a.amount for a in growth.allocate_with_saturation(budget, ranked)}

    if move > base.get(from_market, Decimal("0.00")):
        raise BadRequest(
            f"cannot move {move} from {from_market}: only {base.get(from_market, 0)} allocated there"
        )

    after = dict(base)
    after[from_market] = base[from_market] - move
    after[to_market] = base.get(to_market, Decimal("0.00")) + move

    def totals(alloc: dict[str, Decimal]) -> dict[str, float]:
        b = r = 0.0
        for mkt, amt in alloc.items():
            o = _outcome_for_market(mkt, amt, data_dir)
            b += o["bookings"]
            r += o["revenue"]
        return {"bookings": round(b, 1), "revenue": round(r, 2)}

    before_t = totals(base)
    after_t = totals(after)
    return 200, {
        "budget": str(budget),
        "move": {"from": from_market, "to": to_market, "amount": str(move)},
        "before": before_t,
        "after": after_t,
        "delta": {
            "bookings": round(after_t["bookings"] - before_t["bookings"], 1),
            "revenue": round(after_t["revenue"] - before_t["revenue"], 2),
        },
    }


def _ad_breakdown_dict(a: Allocation, data_dir=None) -> dict[str, Any]:
    """Where a market's allocated ad budget goes: channels + example keywords."""
    split, keywords = data.ad_breakdown(a.market, a.amount, data_dir)
    return {
        "market": a.market,
        "amount": str(a.amount),
        "channels": [
            {"channel": ch.channel, "amount": str(amt)} for ch, amt in split
        ],
        "keywords": [
            {"term": kw.term, "cpcEur": round(kw.cpc_eur, 2)} for kw in keywords
        ],
    }


def get_storyline(params: dict[str, Any], data_dir=None) -> tuple[int, dict[str, Any]]:
    """GET /storyline?route=&date=&budget= -> business-language insights."""
    route_code = _require(params, "route")
    travel_date = _parse_date(_require(params, "date"))
    budget = _parse_budget(_require(params, "budget"))
    try:
        price = _price_result_for(route_code, travel_date, data_dir)
    except data.UnknownRouteError as exc:
        raise BadRequest(str(exc)) from exc
    focus_market, uplift = _period_demand_uplift(
        route_code, travel_date, int(params.get("days", 14)) if str(params.get("days", "")).isdigit() else 14, data_dir
    )
    ranked = growth.rank(
        _market_opportunities(data_dir, focus_market=focus_market, uplift=uplift)
    )
    allocations = growth.allocate(budget, ranked)
    lines = storyline.build_storyline(route_code, price, allocations)
    return 200, {"route": route_code, "storyline": lines}


def get_onepager(params: dict[str, Any], data_dir=None) -> tuple[int, str, str]:
    """GET /onepager?route=&date=&days=&budget= -> deterministic SVG report.

    Returns (status, svg_string, content_type). This is the client-ready
    "one-pager" artifact, rendered straight from the engine.
    """
    from . import onepager as onepager_mod
    from .pricing import price_for

    route_code = _require(params, "route")
    start = _parse_date(_require(params, "date"))
    budget = _parse_budget(_require(params, "budget"))
    try:
        days_n = int(params.get("days", 14))
    except (TypeError, ValueError) as exc:
        raise BadRequest(f"invalid days: {params.get('days')!r}") from exc
    if not 1 <= days_n <= 31:
        raise BadRequest("days must be between 1 and 31")

    try:
        route = data.get_route(route_code, data_dir)
    except data.UnknownRouteError as exc:
        raise BadRequest(str(exc)) from exc

    events = data.events_for_market(data.load_events(data_dir), route.destination_market)
    rules = data.load_pricing_rules(data_dir)

    from datetime import timedelta

    priced: list[PricedDay] = []
    for i in range(days_n):
        d = start + timedelta(days=i)
        holiday = data.is_holiday(route.destination_country, d)
        pr = price_for(route, d, holiday=holiday, events=events, rules=rules)
        priced.append(
            PricedDay(
                date=d.isoformat(),
                price=float(pr.price),
                base=float(pr.base),
                deltaPct=round(pr.delta_pct, 2),
                factors=pr.factors,
            )
        )

    focus_market, uplift = _period_demand_uplift(route_code, start, days_n, data_dir)
    markets = _market_opportunities(data_dir, focus_market=focus_market, uplift=uplift)
    ranked = growth.rank(markets)
    allocations = growth.allocate(budget, ranked)
    mid_price = _price_result_for(route_code, start, data_dir)
    lines = storyline.build_storyline(route_code, mid_price, allocations)

    label = f"{route.origin_city or route.origin} \u2192 {route.destination_city or route.destination_market} ({route.code})"
    period = f"{start.isoformat()} · {days_n} days · budget \u20ac{budget}"
    svg = onepager_mod.build_onepager_svg(
        route_label=label,
        period=period,
        days=priced,
        markets=ranked,
        allocations=allocations,
        storyline=lines,
    )
    return 200, svg, "image/svg+xml"


# --------------------------------------------------------------------------- #
# AWS Lambda adapters (API Gateway proxy integration)
# --------------------------------------------------------------------------- #

def _run(handler, event: dict[str, Any]) -> dict[str, Any]:
    params = event.get("queryStringParameters") or {}
    try:
        status, body = handler(params)
    except BadRequest as exc:
        status, body = 400, {"error": str(exc)}
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body),
    }


def lambda_routes(event, context=None):  # noqa: ANN001
    return _run(get_routes, event)


def lambda_price(event, context=None):  # noqa: ANN001
    return _run(get_price, event)


def lambda_growth(event, context=None):  # noqa: ANN001
    return _run(get_growth, event)


def lambda_storyline(event, context=None):  # noqa: ANN001
    return _run(get_storyline, event)


def lambda_simulate(event, context=None):  # noqa: ANN001
    return _run(get_simulate, event)


def lambda_onepager(event, context=None):  # noqa: ANN001
    params = event.get("queryStringParameters") or {}
    try:
        status, svg, content_type = get_onepager(params)
        headers = {
            "Content-Type": content_type,
            "Access-Control-Allow-Origin": "*",
        }
        return {"statusCode": status, "headers": headers, "body": svg}
    except BadRequest as exc:
        return {
            "statusCode": 400,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps({"error": str(exc)}),
        }
