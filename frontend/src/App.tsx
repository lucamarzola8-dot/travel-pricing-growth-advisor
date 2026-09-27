import { useEffect, useState } from "react";
import {
  fetchGrowth,
  fetchPriceRange,
  fetchRoutes,
  fetchStoryline,
  onePagerUrl,
} from "./api";
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

type Tab = "pricing" | "growth";

/** Today's date as YYYY-MM-DD, so the calendar starts from now by default. */
function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export function App() {
  const [routes, setRoutes] = useState<RouteInfo[]>(FALLBACK_ROUTES);
  const [route, setRoute] = useState(FALLBACK_ROUTES[0].code);
  const [start, setStart] = useState(todayIso());
  const [days, setDays] = useState(14);
  const [budget, setBudget] = useState(100000);
  const [tab, setTab] = useState<Tab>("pricing");

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
        fetchGrowth(budget, { route, date: start, days }),
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
          Turn public holidays and events into flight pricing and Google Ads
          budget decisions.
        </p>
      </header>

      <nav className="tabs">
        <button
          className={tab === "pricing" ? "tab active" : "tab"}
          onClick={() => setTab("pricing")}
        >
          Flight Pricing
        </button>
        <button
          className={tab === "growth" ? "tab active" : "tab"}
          onClick={() => setTab("growth")}
        >
          Ads Growth Allocation
        </button>
      </nav>

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
          Google Ads budget (€)
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
        <a
          className="secondary"
          href={onePagerUrl(route, start, days, budget)}
          target="_blank"
          rel="noopener noreferrer"
          title="Open the client-ready one-pager (SVG) for the current selection"
        >
          Open one-pager
        </a>
      </section>

      {error && <div className="error">Error: {error}</div>}

      {tab === "pricing" ? (
        <div className="grid">
          <section className="panel wide">
            <h2>Pricing calendar — {route}</h2>
            <p className="muted">
              Recommended fare per day for this route. Hover a day to see the
              factors (seasonality, holiday, event) behind its price.
            </p>
            <PricingCalendar days={priced} />
          </section>
        </div>
      ) : (
        <div className="grid">
          <section className="panel wide">
            <h2>Ads growth allocation</h2>
            <GrowthBoard growth={growth} />
          </section>

          <section className="panel wide">
            <h2>Client storyline</h2>
            <Storyline lines={storyline} />
          </section>
        </div>
      )}

      <footer className="muted">
        Flight Pricing tab = revenue management for one route. Ads Growth
        Allocation tab = where to spend the Google Ads budget across markets.
        Offline seed data + public holidays; figures are illustrative.
      </footer>
    </div>
  );
}
