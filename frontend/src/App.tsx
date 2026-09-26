import { useState } from "react";
import { fetchGrowth, fetchPriceRange, fetchStoryline } from "./api";
import type { GrowthResponse, PricedDay } from "./types";
import { PricingCalendar } from "./components/PricingCalendar";
import { GrowthBoard } from "./components/GrowthBoard";
import { Storyline } from "./components/Storyline";

const ROUTES = ["MXP-BCN", "MXP-CDG", "MXP-BER", "MXP-AMS", "MXP-LHR"];

export function App() {
  const [route, setRoute] = useState(ROUTES[0]);
  const [start, setStart] = useState("2026-03-01");
  const [days, setDays] = useState(14);
  const [budget, setBudget] = useState(100000);

  const [priced, setPriced] = useState<PricedDay[]>([]);
  const [growth, setGrowth] = useState<GrowthResponse | null>(null);
  const [storyline, setStoryline] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
            {ROUTES.map((r) => (
              <option key={r} value={r}>
                {r}
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
