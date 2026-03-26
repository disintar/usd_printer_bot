interface MetricTileProps {
  label: string;
  value: string;
  tone?: "default" | "accent" | "positive" | "negative";
}

export function MetricTile(props: MetricTileProps): JSX.Element {
  return (
    <div className={`metric-tile metric-${props.tone ?? "default"}`}>
      <span>{props.label}</span>
      <strong>{props.value}</strong>
    </div>
  );
}
