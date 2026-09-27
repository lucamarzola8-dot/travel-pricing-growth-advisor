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


def _market_opportunities(data_dir=None) -> list[MarketOpportunity]:
    """Derive per-market opportunity scores from the seed data.

    Demand index = number of known events in the market; margin index = a simple
    proxy from the route base fare. Deterministic and offline.
    """
    routes = data.load_routes(data_dir)
    events = data.load_events(data_dir)
    markets: list[MarketOpportunity] = []
    for route in routes.values():
        market = route.destination_market
        demand = float(len([e for e in events if e.market_code == market]))
        margin = float(route.base_fare) / 100.0
        markets.append(
            MarketOpportunity(market, growth.opportunity_score(demand, margin))
        )
    return markets


def get_growth(params: dict[str, Any], data_dir=None) -> tuple[int, dict[str, Any]]:
    """GET /growth?budget= -> ranked markets + allocations (req 5.3)."""
    budget = _parse_budget(_require(params, "budget"))
    markets = _market_opportunities(data_dir)
    ranked = growth.rank(markets)
    allocations = growth.allocate(budget, ranked)
    return 200, {
        "budget": str(budget),
        "markets": [
            {"market": m.market, "score": round(m.score, 4)} for m in ranked
        ],
        "allocations": [_allocation_to_dict(a) for a in allocations],
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
    allocations = growth.allocate(budget, growth.rank(_market_opportunities(data_dir)))
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

    markets = _market_opportunities(data_dir)
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
