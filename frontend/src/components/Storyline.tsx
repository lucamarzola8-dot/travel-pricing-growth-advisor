interface Props {
  lines: string[];
}

export function Storyline({ lines }: Props) {
  if (lines.length === 0) {
    return <p className="muted">The client-ready storyline appears here.</p>;
  }
  return (
    <ol className="storyline">
      {lines.map((line, i) => (
        <li key={i}>{line}</li>
      ))}
    </ol>
  );
}
