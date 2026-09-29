export type FactorKind =
  | "seasonality"
  | "day_of_week"
  | "lead_time"
  | "holiday"
  | "event"
  | "guardrail";

export interface Factor {
  kind: FactorKind;
  multiplier: number;
  reason: string;
}

/** One readable line of a price explanation: euros and % of base fare. */
export interface BreakdownItem {
  kind: FactorKind;
  reason: string;
  multiplier: number;
  contributionEur: string;
  contributionPct: number;
}

export interface PriceResponse {
  route: string;
  price: string;
  base: string;
  deltaPct: number;
  factors: Factor[];
  breakdown: BreakdownItem[];
}

/** Profit-optimal price for one route/day (from /optimize). */
export interface OptimizeDay {
  route: string;
  date: string;
  optimalPrice: string;
  unconstrainedPrice: string;
  capacityConstrained: boolean;
  seats: number;
  loadFactor: number;
  expectedDemand: number;
  expectedRevenue: string;
  expectedProfit: string;
  marginalCost: string;
  recommended: string;
  recommendedRevenue: string;
  recommendedProfit: string;
  upliftPct: number;
  demandMultiplier: number;
  elasticity: number;
  segment: string;
  factors: Factor[];
  breakdown: BreakdownItem[];
}

export interface OptimizeRangeResponse {
  route: string;
  days: OptimizeDay[];
}

export interface MarketScore {
  market: string;
  score: number;
  demandIndex: number;
  cpcEur: number;
  marginIndex: number;
  focused: boolean;
  clicks: number;
  bookings: number;
  revenue: number;
}

export interface GrowthTotals {
  clicks: number;
  bookings: number;
  revenue: number;
  roas: number;
}

export interface SimulateResponse {
  budget: string;
  move: { from: string; to: string; amount: string };
  before: { bookings: number; revenue: number };
  after: { bookings: number; revenue: number };
  delta: { bookings: number; revenue: number };
}

export interface AllocationItem {
  market: string;
  amount: string;
}

export interface AdChannelSplit {
  channel: string;
  amount: string;
}

export interface AdKeyword {
  term: string;
  cpcEur: number;
}

export interface AdBreakdown {
  market: string;
  amount: string;
  channels: AdChannelSplit[];
  keywords: AdKeyword[];
}

export interface GrowthResponse {
  budget: string;
  budgetKind?: string;
  focusMarket?: string | null;
  focusUplift?: number;
  markets: MarketScore[];
  allocations: AllocationItem[];
  breakdowns?: AdBreakdown[];
  totals?: GrowthTotals;
}

/** One advisor recommendation: what the numbers show, what to do, and why. */
export interface AdvisorInsight {
  kind: "peak" | "capacity" | "uplift" | "weekday" | "quiet" | string;
  insight: string;
  action: string;
  evidence: string;
}

export interface StorylineResponse {
  route: string;
  storyline: string[];
  advisor: AdvisorInsight[];
}

export interface RouteInfo {
  code: string;
  origin: string;
  originCity: string;
  destinationMarket: string;
  destinationCity: string;
  destinationCountry: string;
  label: string;
}

export interface RoutesResponse {
  routes: RouteInfo[];
}

/** A single day on the pricing calendar, carrying both price views. */
export interface PricedDay {
  date: string;
  /** Rule-based recommended fare. */
  price: number;
  base: number;
  deltaPct: number;
  factors: Factor[];
  breakdown: BreakdownItem[];
  /** Profit-optimal view for the same day (present once /optimize is loaded). */
  optimal?: OptimizeDay;
}
