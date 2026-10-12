import { formatDecimal, formatInteger } from "@uttg/shared/format";
import { Metric, Panel, SourceNote, Waiting } from "../components/Panel.jsx";
import { Sparkline } from "../components/Sparkline.jsx";

function describeKp(kp) {
  if (kp >= 7) return { tone: "danger", level: "Сильная буря (G3+)", text: "Возможны сбои спутниковой навигации и КВ-связи, сияния видны в средних широтах." };
  if (kp >= 5) return { tone: "danger", level: `Магнитная буря (G${Math.min(Math.floor(kp) - 4, 5)})`, text: "Растёт торможение спутников в атмосфере, сияния могут появиться на широте Санкт-Петербурга." };
  if (kp >= 4) return { tone: "warn", level: "Неспокойно", text: "Магнитное поле возмущено, но до бури не дотягивает. Сияния — на севере Скандинавии и Кольском." };
  return { tone: "ok", level: "Спокойно", text: "Магнитное поле Земли спокойное. Сияния видно только за полярным кругом." };
}

export function WeatherScene({ overview, kpHistory, windHistory }) {
  if (!overview || overview.kp_index == null) {
    return <Panel eyebrow="Космическая погода" title="Солнце и магнитное поле Земли"><Waiting /></Panel>;
  }
  const kp = overview.kp_index;
  const description = describeKp(kp);
  const kpValues = (kpHistory ?? []).map((item) => item.kp_index).reverse();
  const wind = (windHistory ?? []).slice().reverse();
  const latestWind = wind.at(-1);
  return (
    <Panel eyebrow="Космическая погода" title="Солнце и магнитное поле Земли">
      <div className="kp-block">
        <div className={`kp-gauge tone-${description.tone}`}>
          <span className="kp-value num">{formatDecimal(kp)}</span>
          <span className="kp-caption">индекс Kp из 9</span>
        </div>
        <div>
          <div className={`kp-level tone-${description.tone}`}>{description.level}</div>
          <p className="lead">{description.text}</p>
        </div>
      </div>
      <div className="kp-scale" aria-hidden="true">
        {Array.from({ length: 10 }, (_, index) => (
          <span key={index} className={`kp-cell ${index <= kp ? "on" : ""} ${index >= 5 ? "storm" : index >= 4 ? "warn" : ""}`}>{index}</span>
        ))}
      </div>
      {kpValues.length > 1 && (
        <figure className="chart">
          <figcaption>Kp за последние 3 часа</figcaption>
          <Sparkline values={kpValues} min={0} max={9} thresholds={[{ value: 5, color: "var(--accent)" }]} />
        </figure>
      )}
      {latestWind && (
        <>
          <div className="metric-grid three">
            <Metric label="Солнечный ветер" value={formatInteger(latestWind.speed_km_s)} unit="км/с" />
            <Metric label="Плотность" value={formatDecimal(latestWind.density_cm3)} unit="частиц/см³" />
            <Metric label="Температура" value={formatDecimal(latestWind.temperature_k / 1000)} unit="тыс. K" />
          </div>
          <figure className="chart">
            <figcaption>Скорость солнечного ветра, км/с</figcaption>
            <Sparkline values={wind.map((item) => item.speed_km_s)} min={Math.min(...wind.map((item) => item.speed_km_s)) * 0.95} color="var(--text)" />
          </figure>
        </>
      )}
      <SourceNote>Данные NOAA SWPC, обновление каждые 5 минут. Кольцо на глобусе — примерная граница полярных сияний при текущем Kp.</SourceNote>
    </Panel>
  );
}
