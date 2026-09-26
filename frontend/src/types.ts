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
}

export interface AllocationItem {
  market: string;
  amount: string;
}

export interface GrowthResponse {
  budget: string;
  markets: MarketScore[];
  allocations: AllocationItem[];
}

export interface StorylineResponse {
  route: string;
  storyline: string[];
}

/** A single day on the pricing calendar. */
export interface PricedDay {
  date: string;
  price: number;
  base: number;
  deltaPct: number;
  factors: Factor[];
}
