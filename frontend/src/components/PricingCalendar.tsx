import { useEffect, useState } from "react";
import type { PricedDay } from "../types";
import { PriceBreakdown } from "./PriceBreakdown";

export type PriceView = "rules" | "optimal";

interface Props {
  days: PricedDay[];
  view: PriceView;
  onViewChange: (v: PriceView) => void;
}

/** Colour a day by how far its shown price is above base. */
function heat(deltaPct: number): string {
  if (deltaPct >= 25) return "#b91c1c";
  if (deltaPct >= 12) return "#ea580c";
  if (deltaPct >= 4) return "#d97706";
  if (deltaPct <= -4) return "#2563eb";
  return "#334155";
}

function shownPrice(d: PricedDay, view: PriceView): number {
  return view === "optimal" && d.optimal ? Number(d.optimal.optimalPrice) : d.price;
}

export function PricingCalendar({ days, view, onViewChange }: Props) {
  const [active, setActive] = useState<PricedDay | null>(null);
  const [selected, setSelected] = useState<PricedDay | null>(null);

  // Reset the selection when a new range is loaded.
  useEffect(() => {
    setActive(null);
    setSelected(days[0] ?? null);
  }, [days]);

  if (days.length === 0) {
    return <p className="muted">Select a route and period, then load prices.</p>;
  }

  const focus = active ?? selected;
  const hasOptimal = days.some((d) => d.optimal);

  return (
    <div>
      <div className="view-toggle" role="tablist" aria-label="Price view">
        <button
          role="tab"
          aria-selected={view === "rules"}
          className={view === "rules" ? "toggle active" : "toggle"}
          onClick={() => onViewChange("rules")}
        >
          Rule-based fare
        </button>
        <button
          role="tab"
          aria-selected={view === "optimal"}
          className={view === "optimal" ? "toggle active" : "toggle"}
          onClick={() => onViewChange("optimal")}
          disabled={!hasOptimal}
          title="Price that maximises expected profit given demand elasticity and seat capacity"
        >
          Profit-optimal price
        </button>
        {view === "optimal" && (
          <span className="muted toggle-hint">
            <span className="cap-badge">seats</span> = capacity forced the price up (peak pricing)
          </span>
        )}
      </div>

      <div className="calendar">
        {days.map((d) => {
          const p = shownPrice(d, view);
          const delta = d.base ? ((p - d.base) / d.base) * 100 : 0;
          const capped = view === "optimal" && d.optimal?.capacityConstrained;
          const isSel = selected?.date === d.date;
          return (
            <button
              key={d.date}
              className={isSel ? "day selected" : "day"}
              style={{ borderColor: heat(delta) }}
              onMouseEnter={() => setActive(d)}
              onMouseLeave={() => setActive(null)}
              onFocus={() => setActive(d)}
              onClick={() => setSelected(d)}
              aria-pressed={isSel}
            >
              <span className="day-date">{d.date.slice(5)}</span>
              <span className="day-price" style={{ color: heat(delta) }}>
                €{p.toFixed(0)}
              </span>
              <span className="day-delta">
                {delta >= 0 ? "+" : ""}
                {delta.toFixed(0)}%
              </span>
              {capped && <span className="cap-badge">seats</span>}
            </button>
          );
        })}
      </div>

      {focus && view === "rules" && (
        <PriceBreakdown
          date={focus.date}
          base={focus.base}
          price={focus.price}
          items={focus.breakdown}
        />
      )}

      {focus && view === "optimal" && focus.optimal && (
        <OptimalDetail day={focus} />
      )}
    </div>
  );
}

function OptimalDetail({ day }: { day: PricedDay }) {
  const o = day.optimal!;
  const optimal = Number(o.optimalPrice);
  const markup = Number(o.unconstrainedPrice);
  const rec = Number(o.recommended);
  const uplift = o.upliftPct;
  return (
    <div className="ledger">
      <div className="ledger-head">
        <strong>
          {day.date}: profit-optimal €{optimal.toFixed(2)} vs rule-based €{rec.toFixed(2)}
        </strong>
        <span className="muted">
          {o.segment} route · elasticity {o.elasticity.toFixed(2)} · {o.seats} seats · marginal
          cost €{Number(o.marginalCost).toFixed(2)}/seat
        </span>
      </div>

      <div className="totals">
        <div className="totals-item">
          <span className="totals-value">€{optimal.toFixed(0)}</span>
          <span className="totals-label">optimal price</span>
        </div>
        <div className="totals-item">
          <span className="totals-value">{(o.loadFactor * 100).toFixed(0)}%</span>
          <span className="totals-label">expected load factor ({o.expectedDemand.toFixed(0)} seats)</span>
        </div>
        <div className="totals-item">
          <span className="totals-value">€{Number(o.expectedProfit).toLocaleString("en", { maximumFractionDigits: 0 })}</span>
          <span className="totals-label">expected profit</span>
        </div>
        <div className={`totals-item ${uplift >= 0 ? "good" : "bad"}`}>
          <span className="totals-value">
            {uplift >= 0 ? "+" : ""}
            {uplift.toFixed(1)}%
          </span>
          <span className="totals-label">profit vs rule-based fare</span>
        </div>
      </div>

      <p className="explain">
        {o.capacityConstrained ? (
          <>
            At the pure markup price (€{markup.toFixed(2)}) expected demand would exceed the{" "}
            {o.seats} seats, so the price is raised to the level that just fills the aircraft.
            <strong> Peak pricing here comes from capacity, not from a rule.</strong>
          </>
        ) : (
          <>
            Demand at the markup price fills {(o.loadFactor * 100).toFixed(0)}% of the seats, so
            capacity is not binding and the optimal price is the profit markup{" "}
            <code>cost × e/(e−1)</code> = €{markup.toFixed(2)}.
          </>
        )}
      </p>

      <ul className="factor-list">
        {o.factors.map((f, i) => (
          <li key={i}>
            <span className={`tag tag-${f.kind}`}>{f.kind}</span> ×{f.multiplier.toFixed(2)} —{" "}
            {f.reason}
          </li>
        ))}
        <li className="muted">
          combined demand context ×{o.demandMultiplier.toFixed(2)} vs an ordinary day
        </li>
      </ul>
    </div>
  );
}
