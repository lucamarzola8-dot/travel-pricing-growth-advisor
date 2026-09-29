import { useEffect, useState } from "react";
import { fetchOptimizeDay } from "../api";
import type { OptimizeDay, RouteInfo } from "../types";

interface Props {
  routes: RouteInfo[];
  /** Scenario A = the current selection (route + first calendar day). */
  baseRoute: string;
  baseDate: string;
}

function n(v: string | number): number {
  return typeof v === "number" ? v : Number(v);
}

function fmtEur(v: number, digits = 0): string {
  return `€${v.toLocaleString("en", { maximumFractionDigits: digits, minimumFractionDigits: digits })}`;
}

function deltaPct(a: number, b: number): string {
  if (!a) return "—";
  const d = ((b - a) / a) * 100;
  return `${d >= 0 ? "+" : ""}${d.toFixed(1)}%`;
}

/** Factors present in B but not in A (or with a different multiplier). */
function explainDifference(a: OptimizeDay, b: OptimizeDay): string[] {
  const out: string[] = [];
  const byKind = (d: OptimizeDay) =>
    Object.fromEntries(d.factors.map((f) => [f.kind + ":" + f.reason, f.multiplier]));
  const fa = byKind(a);
  const fb = byKind(b);
  for (const f of b.factors) {
    const key = f.kind + ":" + f.reason;
    if (!(key in fa)) out.push(`B has ${f.kind}: ${f.reason} (×${f.multiplier.toFixed(2)})`);
  }
  for (const f of a.factors) {
    const key = f.kind + ":" + f.reason;
    if (!(key in fb)) out.push(`A has ${f.kind}: ${f.reason} (×${f.multiplier.toFixed(2)})`);
  }
  if (a.segment !== b.segment) {
    out.push(
      `Different segments: A is ${a.segment} (e=${a.elasticity.toFixed(2)}), B is ${b.segment} (e=${b.elasticity.toFixed(2)}) — less elastic demand sustains a higher markup.`
    );
  }
  if (a.capacityConstrained !== b.capacityConstrained) {
    const which = b.capacityConstrained ? "B" : "A";
    out.push(`Seat capacity binds only in ${which}: its price is set by filling the aircraft, not by the markup.`);
  }
  if (a.seats !== b.seats) out.push(`Capacity differs: ${a.seats} vs ${b.seats} seats.`);
  if (out.length === 0) out.push("Same drivers on both sides; the difference comes from base fare and guardrails.");
  return out;
}

/**
 * Side-by-side what-if: compare the current selection with another route or
 * date and read why price and profit differ. Every line is backed by a factor
 * or parameter returned by the engine.
 */
export function ScenarioCompare({ routes, baseRoute, baseDate }: Props) {
  const [routeB, setRouteB] = useState(baseRoute);
  const [dateB, setDateB] = useState(baseDate);
  const [a, setA] = useState<OptimizeDay | null>(null);
  const [b, setB] = useState<OptimizeDay | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Keep scenario B's defaults in step with the main selection until edited.
  useEffect(() => {
    setRouteB(baseRoute);
    setDateB(baseDate);
    setA(null);
    setB(null);
  }, [baseRoute, baseDate]);

  async function compare() {
    setLoading(true);
    setError(null);
    try {
      const [ra, rb] = await Promise.all([
        fetchOptimizeDay(baseRoute, baseDate),
        fetchOptimizeDay(routeB, dateB),
      ]);
      setA(ra);
      setB(rb);
    } catch (e) {
      setError(e instanceof Error ? e.message : "request failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <p className="muted">
        Scenario A is your current selection ({baseRoute} on {baseDate}). Pick a second route or
        date and see how price and profit change — and why.
      </p>
      <div className="whatif-controls">
        <label>
          Scenario B route
          <select value={routeB} onChange={(e) => setRouteB(e.target.value)}>
            {routes.map((r) => (
              <option key={r.code} value={r.code}>
                {r.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Scenario B date
          <input type="date" value={dateB} onChange={(e) => setDateB(e.target.value)} />
        </label>
        <button className="primary" onClick={compare} disabled={loading}>
          {loading ? "Comparing…" : "Compare"}
        </button>
      </div>

      {error && <div className="error">Error: {error}</div>}

      {a && b && (
        <div className="compare">
          <table className="board">
            <thead>
              <tr>
                <th></th>
                <th>A · {a.route} · {a.date}</th>
                <th>B · {b.route} · {b.date}</th>
                <th>B vs A</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Rule-based fare</td>
                <td>{fmtEur(n(a.recommended), 2)}</td>
                <td>{fmtEur(n(b.recommended), 2)}</td>
                <td>{deltaPct(n(a.recommended), n(b.recommended))}</td>
              </tr>
              <tr>
                <td>Profit-optimal price</td>
                <td>
                  {fmtEur(n(a.optimalPrice), 2)}{" "}
                  {a.capacityConstrained && <span className="cap-badge">seats</span>}
                </td>
                <td>
                  {fmtEur(n(b.optimalPrice), 2)}{" "}
                  {b.capacityConstrained && <span className="cap-badge">seats</span>}
                </td>
                <td>{deltaPct(n(a.optimalPrice), n(b.optimalPrice))}</td>
              </tr>
              <tr>
                <td>Expected load factor</td>
                <td>{(a.loadFactor * 100).toFixed(0)}%</td>
                <td>{(b.loadFactor * 100).toFixed(0)}%</td>
                <td>{((b.loadFactor - a.loadFactor) * 100).toFixed(0)} pts</td>
              </tr>
              <tr>
                <td>Expected profit (optimal)</td>
                <td>{fmtEur(n(a.expectedProfit))}</td>
                <td>{fmtEur(n(b.expectedProfit))}</td>
                <td>{deltaPct(n(a.expectedProfit), n(b.expectedProfit))}</td>
              </tr>
              <tr>
                <td>Demand context vs ordinary day</td>
                <td>×{a.demandMultiplier.toFixed(2)}</td>
                <td>×{b.demandMultiplier.toFixed(2)}</td>
                <td>{deltaPct(a.demandMultiplier, b.demandMultiplier)}</td>
              </tr>
            </tbody>
          </table>

          <h4 className="compare-why">Why they differ</h4>
          <ul className="storyline">
            {explainDifference(a, b).map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
