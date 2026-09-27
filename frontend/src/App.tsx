import { useEffect, useState } from "react";
import { fetchGrowth, fetchPriceRange, fetchRoutes, fetchStoryline } from "./api";
import type { GrowthResponse, PricedDay, RouteInfo } from "./types";
import { PricingCalendar } from "./components/PricingCalendar";
import { GrowthBoard } from "./components/GrowthBoard";
import { Storyline } from "./components/Storyline";

// Fallback labels if the API is unreachable, so the selector is never empty.
const FALLBACK_ROUTES: RouteInfo[] = [
  {
    code: "MXP-BCN",
    origin: "MXP",
    originCity: "Milan",
    destinationMarket: "BCN",
    destinationCity: "Barcelona",
    destinationCountry: "ES",
    label: "Milan \u2192 Barcelona (MXP-BCN)",
  },
];

export function App() {
  const [routes, setRoutes] = useState<RouteInfo[]>(FALLBACK_ROUTES);
  const [route, setRoute] = useState(FALLBACK_ROUTES[0].code);
  const [start, setStart] = useState("2026-03-01");
  const [days, setDays] = useState(14);
  const [budget, setBudget] = useState(100000);

  const [priced, setPriced] = useState<PricedDay[]>([]);
  const [growth, setGrowth] = useState<GrowthResponse | null>(null);
  const [storyline, setStoryline] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load the available routes (with city labels) once on mount.
  useEffect(() => {
    fetchRoutes()
      .then((r) => {
        if (r.routes.length > 0) {
          setRoutes(r.routes);
          setRoute(r.routes[0].code);
        }
      })
      .catch(() => {
        /* keep fallback routes; a clear error shows on Analyze if API is down */
      });
  }, []);

  async function analyze() {
    setLoading(true);
    setError(null);
    try {
      const [range, g, s] = await Promise.all([
        fetchPriceRange(route, start, days),
        fetchGrowth(budget),
        fetchStoryline(route, start, budget),
      ]);
      setPriced(range);
      setGrowth(g);
      setStoryline(s.storyline);
    } catch (e) {
      setError(e instanceof Error ? e.message : "request failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app">
      <header>
        <h1>Travel Pricing &amp; Growth Advisor</h1>
        <p className="subtitle">
          Turn public holidays and events into pricing and investment decisions.
        </p>
      </header>

      <section className="controls">
        <label>
          Route
          <select value={route} onChange={(e) => setRoute(e.target.value)}>
            {routes.map((r) => (
              <option key={r.code} value={r.code}>
                {r.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Start date
          <input
            type="date"
            value={start}
            onChange={(e) => setStart(e.target.value)}
          />
        </label>
        <label>
          Days
          <input
            type="number"
            min={1}
            max={31}
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
          />
        </label>
        <label>
          Budget (€)
          <input
            type="number"
            min={0}
            step={1000}
            value={budget}
            onChange={(e) => setBudget(Number(e.target.value))}
          />
        </label>
        <button className="primary" onClick={analyze} disabled={loading}>
          {loading ? "Analyzing…" : "Analyze"}
        </button>
      </section>

      {error && <div className="error">Error: {error}</div>}

      <div className="grid">
        <section className="panel">
          <h2>Pricing calendar</h2>
          <p className="muted">Hover a day to see the factors behind its price.</p>
          <PricingCalendar days={priced} />
        </section>

        <section className="panel">
          <h2>Growth opportunities</h2>
          <GrowthBoard growth={growth} />
        </section>

        <section className="panel wide">
          <h2>Client storyline</h2>
          <Storyline lines={storyline} />
        </section>
      </div>

      <footer className="muted">
        Data is offline seed data + public holidays. Prices are illustrative.
      </footer>
    </div>
  );
}
