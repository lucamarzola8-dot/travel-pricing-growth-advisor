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
    # Seats available per departure — the capacity the revenue optimiser must not
    # exceed. When demand at the profit-maximising markup price would overfill
    # the aircraft, price rises to the market-clearing level (peak pricing).
    seats: int = 180
    # Demand segment ("business" | "leisure"): selects the price elasticity used
    # by the optimiser. Business travellers are less price-sensitive.
    segment: str = "leisure"

    def __post_init__(self) -> None:
        if self.floor > self.ceiling:
            raise ValueError(
                f"route {self.code}: floor {self.floor} exceeds ceiling {self.ceiling}"
            )
        if self.base_fare < 0:
            raise ValueError(f"route {self.code}: base_fare must be non-negative")
        if self.seats < 1:
            raise ValueError(f"route {self.code}: seats must be >= 1")


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

    kind: str  # "seasonality" | "day_of_week" | "lead_time" | "holiday" | "event"
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

    Two data-driven factors give day-to-day price variation even in quiet periods
    with no holidays or events:

    * ``dow_multipliers`` — a per-weekday multiplier (Mon=0 .. Sun=6), modelling
      that weekend departures (Fri/Sun) sell higher than mid-week (Tue/Wed).
    * booking lead time — ``lead_time_boost`` decaying over ``lead_time_days``
      makes near-term departures cost more than far-out ones, the classic airline
      advance-purchase curve. Only applied when a reference ("today") date is
      supplied, so the engine stays a pure function of its inputs.
    """

    peak_months: frozenset[int] = frozenset({6, 7, 8, 12})
    peak_multiplier: float = 1.20
    low_months: frozenset[int] = frozenset({1, 2, 11})
    low_multiplier: float = 0.90
    shoulder_multiplier: float = 1.00
    holiday_boost: float = 0.10
    proximity_days: int = 3
    # Weekday multipliers, index 0=Mon .. 6=Sun. Weekend departures priced higher.
    dow_multipliers: tuple[float, ...] = (0.96, 0.94, 0.94, 1.00, 1.08, 1.03, 1.08)
    # Advance-purchase curve: up to +lead_time_boost for a same-day departure,
    # decaying linearly to 0 at lead_time_days out. 0 boost disables the effect.
    lead_time_boost: float = 0.12
    lead_time_days: int = 21
    # Default price elasticity of demand for the revenue optimiser (demand.py),
    # used when a route's segment has no entry in ``elasticity_by_segment``. A
    # value of 1.3 means a +10% price change reduces demand by ~13%. Must be > 1
    # for the profit markup c*e/(e-1) to be finite.
    elasticity: float = 1.3
    # Per-segment elasticity (segment -> e). Business travellers are less
    # price-sensitive (lower e -> higher sustainable markup) than leisure ones.
    elasticity_by_segment: tuple[tuple[str, float], ...] = (
        ("business", 1.30),
        ("leisure", 1.45),
    )
    # Baseline demand at the reference (base) fare on an ordinary day, expressed as
    # a multiple of the route's seats. > 1 means the published base fare alone
    # would overfill the aircraft — the normal airline situation, and exactly why
    # yield management raises the price above it. Sets the scale at which the
    # seat capacity starts to bind in the optimiser.
    base_demand_per_seat: float = 1.1
    # Marginal cost to serve one seat (fuel, taxes, handling), as a fraction of the
    # route base fare. The optimiser maximises profit (p - cost) * demand, so the
    # unconstrained optimum is the revenue-management markup c * e/(e-1). With
    # the defaults this markup sits near the base fare (leisure) or ~30% above it
    # (business). Must be in [0, 1).
    marginal_cost_ratio: float = 0.30
    # How many days before a demand peak marketing campaigns should be live so
    # they capture the search interest that builds up ahead of an event or
    # holiday. Used by the advisor narrative to date its recommended actions —
    # never invented, always this parameter.
    campaign_lead_days: int = 21

    def elasticity_for(self, segment: str) -> float:
        """Elasticity for a route segment, falling back to the default."""
        for name, value in self.elasticity_by_segment:
            if name == segment:
                return value
        return self.elasticity

    def __post_init__(self) -> None:
        if self.holiday_boost < 0:
            raise ValueError("holiday_boost must be non-negative")
        if self.proximity_days < 0:
            raise ValueError("proximity_days must be non-negative")
        if len(self.dow_multipliers) != 7:
            raise ValueError("dow_multipliers must have exactly 7 entries (Mon..Sun)")
        if any(m <= 0 for m in self.dow_multipliers):
            raise ValueError("dow_multipliers must all be positive")
        if self.lead_time_boost < 0:
            raise ValueError("lead_time_boost must be non-negative")
        if self.lead_time_days < 1:
            raise ValueError("lead_time_days must be >= 1")
        if self.elasticity <= 1.0:
            raise ValueError("elasticity must be > 1 (elastic demand)")
        if any(e <= 1.0 for _, e in self.elasticity_by_segment):
            raise ValueError("every segment elasticity must be > 1")
        if self.base_demand_per_seat < 0:
            raise ValueError("base_demand_per_seat must be non-negative")
        if not 0.0 <= self.marginal_cost_ratio < 1.0:
            raise ValueError("marginal_cost_ratio must be in [0, 1)")
        if self.campaign_lead_days < 0:
            raise ValueError("campaign_lead_days must be non-negative")


@dataclass(frozen=True)
class PricedDay:
    """A single day on the pricing calendar (for the one-pager / range views)."""

    date: str
    price: float
    base: float
    deltaPct: float
    factors: tuple[Factor, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class MarketAdData:
    """Per-market advertising signals for Google Ads budget allocation.

    ``demand_index`` is a search-demand proxy (0-100, Google Trends-like),
    ``cpc_eur`` the average cost-per-click for travel keywords in that market,
    and ``margin_index`` (0-1) the relative booking profitability.
    """

    code: str
    city: str
    demand_index: float
    cpc_eur: float
    margin_index: float
    conversion_rate: float = 0.03
    avg_booking_value_eur: float = 180.0


@dataclass(frozen=True)
class MarketOpportunity:
    """A market's computed growth-opportunity score (>= 0).

    Carries the drivers behind the score so the UI can explain it: expected
    demand, the cost-per-click, and the market's margin.
    """

    market: str
    score: float
    demand_index: float = 0.0
    cpc_eur: float = 0.0
    margin_index: float = 0.0


@dataclass(frozen=True)
class Allocation:
    """A suggested budget amount for a market (>= 0)."""

    market: str
    amount: Decimal


@dataclass(frozen=True)
class AdChannel:
    """A Google Ads channel and the share of a market's budget it takes."""

    channel: str  # "Search" | "Performance Max" | "YouTube"
    weight: float


@dataclass(frozen=True)
class AdKeyword:
    """An example search term the ad spend targets, with its cost-per-click."""

    term: str
    cpc_eur: float


@dataclass(frozen=True)
class BreakdownItem:
    """One line of a price breakdown readable by a non-technical stakeholder.

    ``contribution_eur`` is how many euros this step added to (or removed from)
    the running price; ``contribution_pct`` is that amount as a % of the base
    fare. Summing all items' ``contribution_eur`` to the base fare gives the
    final price exactly.
    """

    kind: str
    reason: str
    multiplier: float
    contribution_eur: Decimal
    contribution_pct: float


@dataclass(frozen=True)
class RevenueOptimization:
    """Result of the profit-maximising price search for a route/date.

    ``recommended`` is the rule-based price from :func:`pricing.price_for` (kept for
    comparison); ``optimal_price`` is the price within ``[floor, ceiling]`` that
    maximises expected **profit** ``(price - marginal_cost) * min(demand, seats)``
    under the elasticity model. ``unconstrained_price`` is the markup optimum
    before the seat capacity is applied; when ``capacity_constrained`` is True the
    optimiser raised the price to the market-clearing level because demand at the
    markup price would have exceeded the aircraft's seats (peak pricing).
    ``uplift_pct`` is how much more profit the optimal price earns than the
    rule-based one.
    """

    optimal_price: Decimal
    unconstrained_price: Decimal
    expected_demand: float
    expected_revenue: Decimal
    expected_profit: Decimal
    marginal_cost: Decimal
    recommended: Decimal
    recommended_revenue: Decimal
    recommended_profit: Decimal
    demand_multiplier: float
    elasticity: float
    segment: str
    seats: int
    capacity_constrained: bool
    factors: tuple[Factor, ...] = field(default_factory=tuple)

    @property
    def load_factor(self) -> float:
        """Expected seats sold as a share of capacity (0..1)."""
        if self.seats <= 0:
            return 0.0
        return min(self.expected_demand / self.seats, 1.0)

    @property
    def uplift_pct(self) -> float:
        """Extra profit of the optimal price over the rule-based price, in %."""
        if self.recommended_profit == 0:
            return 0.0
        return float(
            (self.expected_profit - self.recommended_profit)
            / self.recommended_profit
            * 100
        )
