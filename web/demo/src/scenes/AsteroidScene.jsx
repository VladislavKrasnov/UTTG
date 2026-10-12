import { formatDateTime, formatDecimal, formatInteger } from "@uttg/shared/format";
import { Panel, SourceNote, Waiting } from "../components/Panel.jsx";

const RULER_MIN = 0.05;
const RULER_MAX = 20;

function sizeComparison(diameterKm) {
  const metres = diameterKm * 1000;
  if (metres < 8) return "с легковой автомобиль";
  if (metres < 25) return "с автобус";
  if (metres < 60) return "с девятиэтажку";
  if (metres < 150) return "с футбольное поле";
  if (metres < 400) return "с Останкинскую башню";
  return "с небольшую гору";
}

function rulerPosition(lunarDistance) {
  const clamped = Math.min(Math.max(lunarDistance, RULER_MIN), RULER_MAX);
  return ((Math.log10(clamped) - Math.log10(RULER_MIN)) / (Math.log10(RULER_MAX) - Math.log10(RULER_MIN))) * 100;
}

export function AsteroidScene({ approaches }) {
  if (!approaches) return <Panel eyebrow="Астероиды" title="Кто пролетит рядом с Землёй"><Waiting /></Panel>;
  if (!approaches.length) {
    return (
      <Panel eyebrow="Астероиды" title="Кто пролетит рядом с Землёй">
        <p className="lead">В ближайшие 30 дней нет известных сближений ближе 0,05 а.е. (около 19 расстояний до Луны).</p>
      </Panel>
    );
  }
  const closest = approaches.reduce((best, item) => (item.miss_distance_au < best.miss_distance_au ? item : best));
  const meanDiameter = (item) =>
    item.estimated_diameter_min_km != null ? (item.estimated_diameter_min_km + item.estimated_diameter_max_km) / 2 : null;
  const closestDiameter = meanDiameter(closest);
  return (
    <Panel eyebrow="Астероиды · 30 дней" title="Кто пролетит рядом с Землёй">
      <p className="lead">
        Ближе всех пройдёт <strong>{closest.name}</strong>: {formatDateTime(closest.close_approach_date)} на расстоянии{" "}
        <strong className="num">{formatDecimal(closest.miss_distance_lunar)}</strong> от Земли до Луны
        {closestDiameter != null && <> — объект размером примерно {sizeComparison(closestDiameter)}</>}.
      </p>
      <div className="ruler" role="img" aria-label="Расстояния пролёта в расстояниях до Луны">
        <div className="ruler-earth">Земля</div>
        <div className="ruler-moon" style={{ left: `${rulerPosition(1)}%` }}>Луна</div>
        {approaches.map((item) => (
          <span
            key={`${item.neo_id}-${item.close_approach_date}`}
            className={`ruler-dot ${item === closest ? "closest" : ""} ${item.is_potentially_hazardous ? "hazard" : ""}`}
            style={{ left: `${rulerPosition(item.miss_distance_lunar)}%` }}
            title={item.name}
          />
        ))}
        <div className="ruler-axis num">
          {[0.1, 1, 10].map((tick) => (
            <span key={tick} style={{ left: `${rulerPosition(tick)}%` }}>{formatDecimal(tick)}</span>
          ))}
        </div>
      </div>
      <table className="approach-table">
        <thead>
          <tr><th>Объект</th><th>Дата (МСК)</th><th>До Луны ×</th><th>Скорость</th><th>Размер</th></tr>
        </thead>
        <tbody>
          {approaches.slice(0, 6).map((item) => {
            const diameter = meanDiameter(item);
            return (
              <tr key={`${item.neo_id}-${item.close_approach_date}`}>
                <td>{item.name}{item.is_potentially_hazardous && <span className="badge danger">PHA</span>}</td>
                <td>{formatDateTime(item.close_approach_date)}</td>
                <td className="num">{formatDecimal(item.miss_distance_lunar)}</td>
                <td className="num">{formatDecimal(item.relative_velocity_kms)} км/с</td>
                <td className="num">{diameter != null ? `~${formatInteger(diameter * 1000)} м` : "—"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <SourceNote>Сближения: NASA/JPL Center for Near-Earth Object Studies (CNEOS). Шкала логарифмическая.</SourceNote>
    </Panel>
  );
}
