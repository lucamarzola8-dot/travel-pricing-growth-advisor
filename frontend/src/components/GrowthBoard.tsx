import type { GrowthResponse } from "../types";

interface Props {
  growth: GrowthResponse | null;
}

export function GrowthBoard({ growth }: Props) {
  if (!growth) {
    return (
      <p className="muted">
        Set a Google Ads budget and run Analyze to see where it should go.
      </p>
    );
  }

  const amounts = growth.allocations.map((a) => Number(a.amount));
  const max = Math.max(...amounts, 1);

  return (
    <div>
      <p className="muted">
        Google Ads budget €{Number(growth.budget).toLocaleString()} split across
        markets by ROI of ad spend — demand × margin ÷ cost-per-click.
      </p>
      <table className="board">
        <thead>
          <tr>
            <th>Market</th>
            <th>Demand</th>
            <th>CPC</th>
            <th>ROI score</th>
            <th>Ad budget</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {growth.markets.map((m) => {
            const alloc = growth.allocations.find((a) => a.market === m.market);
            const amount = alloc ? Number(alloc.amount) : 0;
            return (
              <tr key={m.market}>
                <td className="market">{m.market}</td>
                <td>{m.demandIndex}</td>
                <td>€{m.cpcEur.toFixed(2)}</td>
                <td>{m.score.toFixed(1)}</td>
                <td>€{amount.toLocaleString()}</td>
                <td className="bar-cell">
                  <div
                    className="bar"
                    style={{ width: `${(amount / max) * 100}%` }}
                  />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
