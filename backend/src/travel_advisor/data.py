"""Offline data loading for the Travel Pricing & Growth Advisor.

All data comes from the local ``data/`` directory plus the ``holidays`` library.
No network access and no API keys are required (product steering: offline-first).

Malformed records are skipped rather than fatal (requirement 1.3): one bad row in
the events file must not prevent the rest from loading.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

import holidays

from .models import Event, PricingRules, Route

# Repo root is three parents up from this file: src/travel_advisor/data.py -> backend -> repo
_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_DATA_DIR = _REPO_ROOT / "data"


class UnknownRouteError(KeyError):
    """Raised when a route code is not present in the loaded routes."""


def _data_dir(data_dir: str | Path | None) -> Path:
    return Path(data_dir) if data_dir is not None else _DEFAULT_DATA_DIR


def load_routes(data_dir: str | Path | None = None) -> dict[str, Route]:
    """Load routes keyed by route code. Malformed records are skipped."""
    path = _data_dir(data_dir) / "routes.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    routes: dict[str, Route] = {}
    for rec in raw:
        try:
            route = Route(
                code=rec["code"],
                origin=rec["origin"],
                destination_market=rec["destination_market"],
                destination_country=rec["destination_country"],
                base_fare=Decimal(str(rec["base_fare"])),
                floor=Decimal(str(rec["floor"])),
                ceiling=Decimal(str(rec["ceiling"])),
                origin_city=rec.get("origin_city", ""),
                destination_city=rec.get("destination_city", ""),
            )
        except (KeyError, ValueError, InvalidOperation, TypeError):
            # Skip malformed route records; keep loading the rest.
            continue
        routes[route.code] = route
    return routes


def load_events(data_dir: str | Path | None = None) -> list[Event]:
    """Load events. Records missing market/date/impact are skipped (req 1.3)."""
    path = _data_dir(data_dir) / "events.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    events: list[Event] = []
    for rec in raw:
        try:
            event = Event(
                market_code=rec["market_code"],
                date=date.fromisoformat(rec["date"]),
                name=rec.get("name", "event"),
                impact=float(rec["impact"]),
            )
        except (KeyError, ValueError, TypeError):
            # Skip malformed event records; keep loading the rest.
            continue
        events.append(event)
    return events


def load_pricing_rules(data_dir: str | Path | None = None) -> PricingRules:
    """Load pricing rules from ``pricing-rules.json``.

    Falls back to :class:`PricingRules` defaults if the file is missing or any
    field is malformed, so the engine always has a valid, deterministic ruleset.
    """
    path = _data_dir(data_dir) / "pricing-rules.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return PricingRules()
    try:
        season = raw.get("seasonality", {})
        return PricingRules(
            peak_months=frozenset(int(m) for m in season.get("peak_months", [6, 7, 8, 12])),
            peak_multiplier=float(season.get("peak_multiplier", 1.20)),
            low_months=frozenset(int(m) for m in season.get("low_months", [1, 2, 11])),
            low_multiplier=float(season.get("low_multiplier", 0.90)),
            shoulder_multiplier=float(season.get("shoulder_multiplier", 1.00)),
            holiday_boost=float(raw.get("holiday_boost", 0.10)),
            proximity_days=int(raw.get("proximity_days", 3)),
        )
    except (KeyError, ValueError, TypeError):
        return PricingRules()


def get_route(code: str, data_dir: str | Path | None = None) -> Route:
    """Return the route for ``code`` or raise :class:`UnknownRouteError` (req 1.4)."""
    routes = load_routes(data_dir)
    try:
        return routes[code]
    except KeyError as exc:
        raise UnknownRouteError(f"unknown route: {code!r}") from exc


def is_holiday(country: str, on: date) -> bool:
    """Return True if ``on`` is a national public holiday in ``country`` (req 1.1).

    Uses the offline ``holidays`` library. Unknown country codes return False
    rather than raising, so pricing degrades gracefully.
    """
    try:
        country_holidays = holidays.country_holidays(country, years=on.year)
    except (KeyError, NotImplementedError):
        return False
    return on in country_holidays


def events_for_market(events: list[Event], market_code: str) -> list[Event]:
    """Filter loaded events down to a single market."""
    return [e for e in events if e.market_code == market_code]
