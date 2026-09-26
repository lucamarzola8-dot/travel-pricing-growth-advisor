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
from .models import Allocation, MarketOpportunity, PriceResult


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
    from .pricing import price_for

    return price_for(route, travel_date, holiday=holiday, events=events)


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


def lambda_price(event, context=None):  # noqa: ANN001
    return _run(get_price, event)


def lambda_growth(event, context=None):  # noqa: ANN001
    return _run(get_growth, event)


def lambda_storyline(event, context=None):  # noqa: ANN001
    return _run(get_storyline, event)
