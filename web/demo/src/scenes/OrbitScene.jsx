import { formatDecimal, formatInteger } from "@uttg/shared/format";
import { Metric, Panel, SourceNote, Waiting } from "../components/Panel.jsx";

function hemisphere(latitude, longitude) {
  const northSouth = latitude >= 0 ? "Северном" : "Южном";
  const eastWest = longitude >= 0 ? "Восточном" : "Западном";
  return `${northSouth} и ${eastWest} полушариях`;
}

export function OrbitScene({ iss, trackedCount, groups, issInDaylight }) {
  return (
    <Panel eyebrow="Орбиты · прямо сейчас" title="Где сейчас МКС и ещё тысячи спутников">
      {iss ? (
        <>
          <div className="metric-grid four">
            <Metric label="Широта" value={formatDecimal(iss.latitude)} unit="°" />
            <Metric label="Долгота" value={formatDecimal(iss.longitude)} unit="°" />
            <Metric label="Высота" value={formatInteger(iss.altitudeKm)} unit="км" />
            <Metric label="Скорость" value={formatDecimal(iss.speedKmS * 3600 / 1000)} unit="тыс. км/ч" tone="accent" />
          </div>
          <p className="lead">
            МКС сейчас в {hemisphere(iss.latitude, iss.longitude)} и находится
            {issInDaylight ? " на дневной стороне Земли." : " в тени Земли — там сейчас ночь."} Один оборот занимает около{" "}
            {formatInteger(iss.periodMinutes)} минут, за сутки станция облетает планету {formatDecimal(1440 / iss.periodMinutes)} раза.
          </p>
        </>
      ) : (
        <Waiting>Загружаем орбиту МКС…</Waiting>
      )}
      <div className="legend">
        {groups.map((group) => (
          <div className="legend-row" key={group.key}>
            <span className="legend-dot" style={{ background: group.color }} />
            <span>{group.label}</span>
            <span className="legend-count num">{formatInteger(group.count)}</span>
          </div>
        ))}
        <div className="legend-total">
          На глобусе <strong className="num">{formatInteger(trackedCount)}</strong> объектов, положение каждого
          считается в браузере по модели SGP4 раз в секунду.
        </div>
      </div>
      <SourceNote>Орбитальные элементы: CelesTrak. Высота над Землёй на глобусе показана в логарифмическом масштабе.</SourceNote>
    </Panel>
  );
}
