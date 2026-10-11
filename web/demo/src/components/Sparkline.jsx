export function Sparkline({ values, height = 90, color = "var(--accent)", thresholds = [], max: fixedMax, min: fixedMin = 0 }) {
  if (values.length < 2) return null;
  const width = 600;
  const max = fixedMax ?? Math.max(...values) * 1.1;
  const min = fixedMin ?? Math.min(...values);
  const range = max - min || 1;
  const x = (index) => (index / (values.length - 1)) * width;
  const y = (value) => height - ((value - min) / range) * height;
  const path = values.map((value, index) => `${index ? "L" : "M"}${x(index).toFixed(1)},${y(value).toFixed(1)}`).join("");
  return (
    <svg className="sparkline" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" role="img" aria-hidden="true">
      {thresholds.map((threshold) => (
        <line key={threshold.value} x1="0" x2={width} y1={y(threshold.value)} y2={y(threshold.value)} stroke={threshold.color} strokeDasharray="6 6" strokeWidth="1.5" opacity="0.6" />
      ))}
      <path d={`${path}L${width},${height}L0,${height}Z`} fill={color} opacity="0.12" />
      <path d={path} fill="none" stroke={color} strokeWidth="3" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}
