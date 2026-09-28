import { useEffect, useState } from "react";
import { fetchSimulate } from "../api";
import type { SimulateResponse } from "../types";

interface Props {
  budget: number;
  markets: string[];
}

/** What-if: move ad budget from one market to another and see the impact. */
export function WhatIf({ budget, markets }: Props) {
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [amount, setAmount] = useState(5000);
  const [result, setResult] = useState<SimulateResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Default the two dropdowns once markets arrive.
  useEffect(() => {
    if (markets.length >= 2) {
      setFrom((f) => f || markets[markets.length - 1]); // lowest-ROI by default
      setTo((t) => t || markets[0]); // highest-ROI by default
    }
  }, [markets]);

  async function run() {
    setLoading(true);
    setError(null);
    try {
      const r = await fetchSimulate(budget, from, to, amount);
      setResult(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : "simulation failed");
      setResult(null);
    } finally {
      setLoading(false);
    }
  }

  if (markets.length === 0) {
    return <p className="muted">Run Analyze first, then simulate budget shifts.</p>;
  }

  return (
    <div className="whatif">
      <p className="muted">
        Test a budget shift: move spend from one market to another and see the
        change in expected bookings and revenue.
      </p>
      <div className="whatif-controls">
        <label>
          Move €
          <input
            type="number"
            min={0}
            step={500}
            value={amount}
            onChange={(e) => setAmount(Number(e.target.value))}
          />
        </label>
        <label>
          from
          <select value={from} onChange={(e) => setFrom(e.target.value)}>
            {markets.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </label>
        <label>
          to
          <select value={to} onChange={(e) => setTo(e.target.value)}>
            {markets.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </label>
        <button className="primary" onClick={run} disabled={loading || from === to}>
          {loading ? "Simulating…" : "Simulate"}
        </button>
      </div>

      {error && <div className="error">Error: {error}</div>}

      {result && (
        <div className="whatif-result">
          <p>
            Moving <strong>€{Number(result.move.amount).toLocaleString()}</strong>{" "}
            from <strong>{result.move.from}</strong> to{" "}
            <strong>{result.move.to}</strong>:
          </p>
          <div className="whatif-deltas">
            <div className={`delta ${result.delta.bookings >= 0 ? "up" : "down"}`}>
              <span className="delta-value">
                {result.delta.bookings >= 0 ? "+" : ""}
                {result.delta.bookings.toLocaleString()}
              </span>
              <span className="delta-label">bookings</span>
            </div>
            <div className={`delta ${result.delta.revenue >= 0 ? "up" : "down"}`}>
              <span className="delta-value">
                {result.delta.revenue >= 0 ? "+" : ""}€
                {result.delta.revenue.toLocaleString()}
              </span>
              <span className="delta-label">revenue</span>
            </div>
          </div>
          <p className="muted">
            Bookings {result.before.bookings.toLocaleString()} →{" "}
            {result.after.bookings.toLocaleString()} · Revenue €
            {result.before.revenue.toLocaleString()} → €
            {result.after.revenue.toLocaleString()}
          </p>
        </div>
      )}
    </div>
  );
}
