export interface Factor {
  kind: "seasonality" | "holiday" | "event";
  multiplier: number;
  reason: string;
}

export interface PriceResponse {
  route: string;
  price: string;
  base: string;
  deltaPct: number;
  factors: Factor[];
}

export interface MarketScore {
  market: string;
  score: number;
  demandIndex: number;
  cpcEur: number;
  marginIndex: number;
  focused: boolean;
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
}

export interface StorylineResponse {
  route: string;
  storyline: string[];
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

/** A single day on the pricing calendar. */
export interface PricedDay {
  date: string;
  price: number;
  base: number;
  deltaPct: number;
  factors: Factor[];
}
