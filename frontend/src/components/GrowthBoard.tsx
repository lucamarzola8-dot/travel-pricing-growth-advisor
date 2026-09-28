import { Fragment, useState } from "react";
import type { GrowthResponse } from "../types";

interface Props {
  growth: GrowthResponse | null;
}

export function GrowthBoard({ growth }: Props) {
  const [open, setOpen] = useState<string | null>(null);

  if (!growth) {
    return (
      <p className="muted">
        Set a Google Ads budget and run Analyze to see where it should go.
      </p>
    );
  }

  const amounts = growth.allocations.map((a) => Number(a.amount));
  const max = Math.max(...amounts, 1);
  const boosted =
    growth.focusMarket && (growth.focusUplift ?? 1) > 1
      ? `${growth.focusMarket} is demand-boosted ×${(growth.focusUplift ?? 1).toFixed(
          2
        )} from the holidays/events on the analysed route.`
      : null;

  const breakdownFor = (market: string) =>
    growth.breakdowns?.find((b) => b.market === market) ?? null;

  return (
    <div>
      <p className="muted">
        Google Ads budget €{Number(growth.budget).toLocaleString()} split across
        markets by ROI of ad spend — demand × margin ÷ cost-per-click.
      </p>
      {boosted && <p className="note">{boosted}</p>}

      {growth.totals && (
        <div className="totals">
          <div className="totals-item">
            <span className="totals-value">
              {growth.totals.clicks.toLocaleString()}
            </span>
            <span className="totals-label">expected clicks</span>
          </div>
          <div className="totals-item">
            <span className="totals-value">
              {growth.totals.bookings.toLocaleString()}
            </span>
            <span className="totals-label">expected bookings</span>
          </div>
          <div className="totals-item">
            <span className="totals-value">
              €{growth.totals.revenue.toLocaleString()}
            </span>
            <span className="totals-label">expected revenue</span>
          </div>
          <div className="totals-item">
            <span className="totals-value">{growth.totals.roas}×</span>
            <span className="totals-label">ROAS</span>
          </div>
        </div>
      )}

      <p className="muted">Click a market to see where its ad budget goes.</p>
      <table className="board">
        <thead>
          <tr>
            <th>Market</th>
            <th>Demand</th>
            <th>CPC</th>
            <th>ROI score</th>
            <th>Ad budget</th>
            <th>Bookings</th>
            <th>Revenue</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {growth.markets.map((m) => {
            const alloc = growth.allocations.find((a) => a.market === m.market);
            const amount = alloc ? Number(alloc.amount) : 0;
            const isOpen = open === m.market;
            const bd = breakdownFor(m.market);
            return (
              <Fragment key={m.market}>
                <tr
                  className={`clickable ${m.focused ? "focused" : ""}`}
                  onClick={() => setOpen(isOpen ? null : m.market)}
                >
                  <td className="market">
                    {isOpen ? "▾ " : "▸ "}
                    {m.market}
                    {m.focused ? " ★" : ""}
                  </td>
                  <td>{m.demandIndex}</td>
                  <td>€{m.cpcEur.toFixed(2)}</td>
                  <td>{m.score.toFixed(1)}</td>
                  <td>€{amount.toLocaleString()}</td>
                  <td>{m.bookings.toLocaleString()}</td>
                  <td>€{m.revenue.toLocaleString()}</td>
                  <td className="bar-cell">
                    <div
                      className="bar"
                      style={{ width: `${(amount / max) * 100}%` }}
                    />
                  </td>
                </tr>
                {isOpen && bd && (
                  <tr className="detail">
                    <td colSpan={8}>
                      <div className="breakdown">
                        <div className="breakdown-col">
                          <h4>Spend by channel</h4>
                          <ul>
                            {bd.channels.map((c) => (
                              <li key={c.channel}>
                                <span>{c.channel}</span>
                                <span>€{Number(c.amount).toLocaleString()}</span>
                              </li>
                            ))}
                          </ul>
                        </div>
                        <div className="breakdown-col">
                          <h4>Example keywords</h4>
                          <ul>
                            {bd.keywords.map((k) => (
                              <li key={k.term}>
                                <span>{k.term}</span>
                                <span className="muted">
                                  CPC €{k.cpcEur.toFixed(2)}
                                </span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
