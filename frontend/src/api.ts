import type {
  GrowthResponse,
  OptimizeDay,
  OptimizeRangeResponse,
  PriceResponse,
  PricedDay,
  RoutesResponse,
  SimulateResponse,
  StorylineResponse,
} from "./types";

// In dev, Vite proxies /api -> http://127.0.0.1:8000 (see vite.config.ts).
const BASE = "/api";

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) {
    let message = `request failed (${res.status})`;
    try {
      const body = await res.json();
      if (body?.error) message = body.error;
    } catch {
      /* ignore parse errors, keep default message */
    }
    throw new Error(message);
  }
  return (await res.json()) as T;
}

export function fetchRoutes(): Promise<RoutesResponse> {
  return getJson<RoutesResponse>("/routes");
}

export function fetchSimulate(
  budget: number,
  from: string,
  to: string,
  amount: number
): Promise<SimulateResponse> {
  const q = new URLSearchParams({
    budget: String(budget),
    from,
    to,
    amount: String(amount),
  });
  return getJson<SimulateResponse>(`/simulate?${q.toString()}`);
}

/** URL of the deterministic SVG one-pager for the current selection. */
export function onePagerUrl(
  route: string,
  date: string,
  days: number,
  budget: number
): string {
  const q = new URLSearchParams({
    route,
    date,
    days: String(days),
    budget: String(budget),
  });
  return `${BASE}/onepager?${q.toString()}`;
}

export function fetchPrice(route: string, date: string): Promise<PriceResponse> {
  return getJson<PriceResponse>(
    `/price?route=${encodeURIComponent(route)}&date=${encodeURIComponent(date)}`
  );
}

export function fetchGrowth(
  budget: number,
  context?: { route: string; date: string; days: number }
): Promise<GrowthResponse> {
  const q = new URLSearchParams({ budget: String(budget) });
  if (context) {
    q.set("route", context.route);
    q.set("date", context.date);
    q.set("days", String(context.days));
  }
  return getJson<GrowthResponse>(`/growth?${q.toString()}`);
}

export function fetchStoryline(
  route: string,
  date: string,
  budget: number,
  days = 14
): Promise<StorylineResponse> {
  const q = new URLSearchParams({
    route,
    date,
    budget: String(budget),
    days: String(days),
  });
  return getJson<StorylineResponse>(`/storyline?${q.toString()}`);
}

/** URL of the consulting-style Markdown report for the current selection. */
export function reportUrl(
  route: string,
  date: string,
  days: number,
  budget: number
): string {
  const q = new URLSearchParams({
    route,
    date,
    days: String(days),
    budget: String(budget),
  });
  return `${BASE}/report?${q.toString()}`;
}

/** Profit-optimal prices for `days` consecutive days in one round trip. */
export function fetchOptimizeRange(
  route: string,
  start: string,
  days: number
): Promise<OptimizeRangeResponse> {
  const q = new URLSearchParams({ route, date: start, days: String(days) });
  return getJson<OptimizeRangeResponse>(`/optimize?${q.toString()}`);
}

/** Profit-optimal price for a single route/day (used by scenario compare). */
export function fetchOptimizeDay(route: string, date: string): Promise<OptimizeDay> {
  const q = new URLSearchParams({ route, date });
  return getJson<OptimizeDay>(`/optimize?${q.toString()}`);
}

/** Turn one /optimize entry into a calendar day carrying both price views. */
export function toPricedDay(o: OptimizeDay, base: number): PricedDay {
  const price = Number(o.recommended);
  return {
    date: o.date,
    price,
    base,
    deltaPct: base ? ((price - base) / base) * 100 : 0,
    factors: o.factors,
    breakdown: o.breakdown,
    optimal: o,
  };
}

/**
 * Fetch the pricing calendar for a range of days. A single /optimize call
 * returns, per day, the rule-based fare, its EUR/% breakdown and the
 * profit-optimal price, so the calendar needs one request instead of N.
 */
export async function fetchPriceRange(
  route: string,
  start: string,
  days: number
): Promise<PricedDay[]> {
  const [range, first] = await Promise.all([
    fetchOptimizeRange(route, start, days),
    fetchPrice(route, start), // one call to learn the base fare
  ]);
  const base = Number(first.base);
  return range.days.map((o) => toPricedDay(o, base));
}
