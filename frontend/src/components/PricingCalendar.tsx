import { useState } from "react";
import type { PricedDay } from "../types";

interface Props {
  days: PricedDay[];
}

/** Colour a day by how far its price is above base. */
function heat(deltaPct: number): string {
  if (deltaPct >= 25) return "#b91c1c";
  if (deltaPct >= 12) return "#ea580c";
  if (deltaPct >= 4) return "#d97706";
  if (deltaPct <= -4) return "#2563eb";
  return "#334155";
}

export function PricingCalendar({ days }: Props) {
  const [active, setActive] = useState<PricedDay | null>(null);

  if (days.length === 0) {
    return <p className="muted">Select a route and period, then load prices.</p>;
  }

  return (
    <div>
      <div className="calendar">
        {days.map((d) => (
          <button
            key={d.date}
            className="day"
            style={{ borderColor: heat(d.deltaPct) }}
            onMouseEnter={() => setActive(d)}
            onFocus={() => setActive(d)}
          >
            <span className="day-date">{d.date.slice(5)}</span>
            <span className="day-price" style={{ color: heat(d.deltaPct) }}>
              €{d.price.toFixed(0)}
            </span>
            <span className="day-delta">
              {d.deltaPct >= 0 ? "+" : ""}
              {d.deltaPct.toFixed(0)}%
            </span>
          </button>
        ))}
      </div>

      {active && (
        <div className="tooltip">
          <strong>{active.date}</strong> — €{active.price.toFixed(2)} (base €
          {active.base.toFixed(2)}, {active.deltaPct >= 0 ? "+" : ""}
          {active.deltaPct.toFixed(1)}%)
          <ul>
            {active.factors.map((f, i) => (
              <li key={i}>
                <span className={`tag tag-${f.kind}`}>{f.kind}</span> ×
                {f.multiplier.toFixed(2)} — {f.reason}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
