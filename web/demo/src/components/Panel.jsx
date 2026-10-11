export function Panel({ eyebrow, title, children, className = "" }) {
  return (
    <section className={`panel ${className}`}>
      {eyebrow && <div className="eyebrow">{eyebrow}</div>}
      {title && <h2 className="panel-title">{title}</h2>}
      {children}
    </section>
  );
}

export function Metric({ label, value, unit, tone }) {
  return (
    <div className={`metric ${tone ? `tone-${tone}` : ""}`}>
      <div className="metric-label">{label}</div>
      <div className="metric-value num">
        {value}
        {unit && <span className="metric-unit">{unit}</span>}
      </div>
    </div>
  );
}

export function Waiting({ children = "Ждём данные от сервера…" }) {
  return (
    <div className="waiting">
      <span className="spinner" aria-hidden="true" />
      {children}
    </div>
  );
}

export function SourceNote({ children }) {
  return <p className="source-note">{children}</p>;
}
