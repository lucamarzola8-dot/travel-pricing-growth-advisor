"""Domain models for the Travel Pricing & Growth Advisor.

All monetary amounts use :class:`decimal.Decimal` (never binary floats), per the
project tech steering. Multipliers/scores are plain floats. Every computed result
carries the factors that produced it, so nothing is ever an unexplained number.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class Market:
    """A destination market (airport/city) and its ISO country code."""

    code: str
    country: str


@dataclass(frozen=True)
class Route:
    """A sellable route with its base fare and price guardrails.

    ``floor`` and ``ceiling`` bound every recommended price. ``floor`` must not
    exceed ``ceiling``; this is validated at construction to avoid silently wrong
    prices later.
    """

    code: str
    origin: str
    destination_market: str
    destination_country: str
    base_fare: Decimal
    floor: Decimal
    ceiling: Decimal
    origin_city: str = ""
    destination_city: str = ""

    def __post_init__(self) -> None:
        if self.floor > self.ceiling:
            raise ValueError(
                f"route {self.code}: floor {self.floor} exceeds ceiling {self.ceiling}"
            )
        if self.base_fare < 0:
            raise ValueError(f"route {self.code}: base_fare must be non-negative")


@dataclass(frozen=True)
class Event:
    """A public event in a market that boosts travel demand.

    ``impact`` is a non-negative demand multiplier boost (0.35 == +35%).
    """

    market_code: str
    date: date
    name: str
    impact: float

    def __post_init__(self) -> None:
        if self.impact < 0:
            raise ValueError(f"event {self.name!r}: impact must be non-negative")


@dataclass(frozen=True)
class Factor:
    """One explainable contribution to a price or score.

    ``multiplier`` is what the running value was multiplied by; ``reason`` is the
    human-readable explanation shown to the user.
    """

    kind: str  # "seasonality" | "holiday" | "event"
    multiplier: float
    reason: str


@dataclass(frozen=True)
class PriceResult:
    """A recommended price plus the ordered factors that produced it."""

    price: Decimal
    base: Decimal
    factors: tuple[Factor, ...] = field(default_factory=tuple)

    @property
    def delta_pct(self) -> float:
        """Percentage difference of the final price versus the base fare."""
        if self.base == 0:
            return 0.0
        return float((self.price - self.base) / self.base * 100)


@dataclass(frozen=True)
class PricingRules:
    """Tunable pricing rules, loaded from data (not hard-coded).

    Adding or changing pricing behaviour is a data edit, not a code change.
    ``holiday_boost`` and event impacts are applied as ``1 + boost`` and must be
    ``>= 0`` so the corresponding factors never lower the pre-clamp price.
    """

    peak_months: frozenset[int] = frozenset({6, 7, 8, 12})
    peak_multiplier: float = 1.20
    low_months: frozenset[int] = frozenset({1, 2, 11})
    low_multiplier: float = 0.90
    shoulder_multiplier: float = 1.00
    holiday_boost: float = 0.10
    proximity_days: int = 3

    def __post_init__(self) -> None:
        if self.holiday_boost < 0:
            raise ValueError("holiday_boost must be non-negative")
        if self.proximity_days < 0:
            raise ValueError("proximity_days must be non-negative")


@dataclass(frozen=True)
class MarketOpportunity:
    """A market's computed growth-opportunity score (>= 0)."""

    market: str
    score: float


@dataclass(frozen=True)
class Allocation:
    """A suggested budget amount for a market (>= 0)."""

    market: str
    amount: Decimal
