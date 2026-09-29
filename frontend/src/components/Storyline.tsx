import type { AdvisorInsight } from "../types";

interface Props {
  lines: string[];
  advisor?: AdvisorInsight[];
}

const KIND_LABEL: Record<string, string> = {
  peak: "Demand peak",
  capacity: "Capacity",
  uplift: "Profit uplift",
  weekday: "Weekday pattern",
  quiet: "Quiet window",
};

/**
 * Client-facing narrative. The advisor block is the consultant's voice: each
 * card states what the numbers show, what to do about it, and the evidence
 * behind both. Nothing here is generated without a computed figure.
 */
export function Storyline({ lines, advisor = [] }: Props) {
  if (lines.length === 0 && advisor.length === 0) {
    return <p className="muted">The client-ready storyline appears here.</p>;
  }
  return (
    <div>
      {advisor.length > 0 && (
        <div className="advisor">
          {advisor.map((a, i) => (
            <article key={i} className={`advice advice-${a.kind}`}>
              <header>
                <span className="advice-kind">{KIND_LABEL[a.kind] ?? a.kind}</span>
              </header>
              <p className="advice-insight">{a.insight}</p>
              <p className="advice-action">
                <strong>Action:</strong> {a.action}
              </p>
              <p className="advice-evidence muted">Evidence: {a.evidence}</p>
            </article>
          ))}
        </div>
      )}
      {lines.length > 0 && (
        <ol className="storyline">
          {lines.map((line, i) => (
            <li key={i}>{line}</li>
          ))}
        </ol>
      )}
    </div>
  );
}
