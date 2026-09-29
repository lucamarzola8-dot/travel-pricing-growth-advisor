import type { BreakdownItem, FactorKind } from "../types";

interface Props {
  date: string;
  base: number;
  price: number;
  items: BreakdownItem[];
}

const LABELS: Record<FactorKind, string> = {
  seasonality: "Season",
  day_of_week: "Day of week",
  lead_time: "Booking lead time",
  holiday: "Public holiday",
  event: "Nearby event",
  guardrail: "Price guardrail",
};

function eur(v: number): string {
  const sign = v > 0 ? "+" : v < 0 ? "−" : "";
  return `${sign}€${Math.abs(v).toFixed(2)}`;
}

function pct(v: number): string {
  const sign = v > 0 ? "+" : v < 0 ? "−" : "";
  return `${sign}${Math.abs(v).toFixed(1)}%`;
}

/**
 * Explains a day's fare as a short ledger a business stakeholder can read
 * top-to-bottom: start at the base fare, add/subtract each factor in euros and
 * as a % of base, land on the recommended fare. The rows always sum exactly.
 */
export function PriceBreakdown({ date, base, price, items }: Props) {
  return (
    <div className="ledger">
      <div className="ledger-head">
        <strong>Why €{price.toFixed(2)} on {date}?</strong>
        <span className="muted">
          Each line is one driver; amounts are in € and as a % of the base fare.
        </span>
      </div>
      <table className="ledger-table">
        <tbody>
          <tr className="ledger-base">
            <td>Base fare</td>
            <td className="muted">published fare for this route</td>
            <td className="num">€{base.toFixed(2)}</td>
            <td className="num muted">—</td>
          </tr>
          {items.map((it, i) => {
            const v = Number(it.contributionEur);
            const cls = v > 0 ? "up" : v < 0 ? "down" : "";
            return (
              <tr key={i} className={cls}>
                <td>
                  <span className={`tag tag-${it.kind}`}>{LABELS[it.kind] ?? it.kind}</span>
                </td>
                <td className="muted">{it.reason}</td>
                <td className="num">{eur(v)}</td>
                <td className="num">{pct(it.contributionPct)}</td>
              </tr>
            );
          })}
          <tr className="ledger-total">
            <td>Recommended fare</td>
            <td className="muted">base + all drivers</td>
            <td className="num">€{price.toFixed(2)}</td>
            <td className="num">{pct(base ? ((price - base) / base) * 100 : 0)}</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}
