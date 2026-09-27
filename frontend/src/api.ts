import type {
  GrowthResponse,
  PriceResponse,
  PricedDay,
  RoutesResponse,
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

export function fetchGrowth(budget: number): Promise<GrowthResponse> {
  return getJson<GrowthResponse>(`/growth?budget=${encodeURIComponent(budget)}`);
}

export function fetchStoryline(
  route: string,
  date: string,
  budget: number
): Promise<StorylineResponse> {
  return getJson<StorylineResponse>(
    `/storyline?route=${encodeURIComponent(route)}&date=${encodeURIComponent(
      date
    )}&budget=${encodeURIComponent(budget)}`
  );
}

/** Fetch prices for a range of days (inclusive) for the pricing calendar. */
export async function fetchPriceRange(
  route: string,
  start: string,
  days: number
): Promise<PricedDay[]> {
  const dates: string[] = [];
  const d = new Date(start + "T00:00:00Z");
  for (let i = 0; i < days; i++) {
    dates.push(d.toISOString().slice(0, 10));
    d.setUTCDate(d.getUTCDate() + 1);
  }
  const results = await Promise.all(
    dates.map(async (date) => {
      const p = await fetchPrice(route, date);
      return {
        date,
        price: Number(p.price),
        base: Number(p.base),
        deltaPct: p.deltaPct,
        factors: p.factors,
      } satisfies PricedDay;
    })
  );
  return results;
}
