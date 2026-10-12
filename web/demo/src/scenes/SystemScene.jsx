import { formatAge } from "@uttg/shared/format";
import { Metric, Panel, SourceNote, Waiting } from "../components/Panel.jsx";

const PROVIDER_NAMES = {
  celestrak: ["CelesTrak", "орбиты спутников"],
  "noaa-swpc": ["NOAA SWPC", "космическая погода"],
  "jpl-ssd": ["NASA / JPL", "сближения астероидов"],
  "rocketlaunch-live": ["RocketLaunch.Live", "расписание запусков"],
  "the-space-devs": ["Launch Library 2", "расписание запусков"],
  "space-track": ["Space-Track", "каталог объектов"],
  "nasa-neows": ["NASA NeoWs", "астероиды"],
};

const PIPELINE = ["Источники", "Планировщик", "PostgreSQL + Valkey", "REST API", "Этот экран"];

export function SystemScene({ providers, ready, now }) {
  const rows = providers?.data ?? null;
  return (
    <Panel eyebrow="Как это работает" title="Экран не ходит в NASA — он читает наш API">
      <div className="pipeline" aria-label="Путь данных">
        {PIPELINE.map((step, index) => (
          <div className="pipeline-step" key={step}>
            <span>{step}</span>
            {index < PIPELINE.length - 1 && <span className="pipeline-flow" aria-hidden="true"><i /><i /><i /></span>}
          </div>
        ))}
      </div>
      <p className="lead">
        Планировщик сам забирает данные у источников по расписанию и с учётом их лимитов. Если источник упал, API продолжает
        отдавать последние сохранённые данные — экран не гаснет.
      </p>
      <div className="metric-grid">
        <Metric label="API" value={ready.status === "live" ? "в строю" : ready.status === "loading" ? "…" : "нет связи"} tone={ready.status === "live" ? "ok" : "warn"} />
        <Metric label="Задержка ответа" value={ready.latencyMs ?? "—"} unit="мс" />
      </div>
      {rows ? (
        <ul className="provider-list">
          {rows.map((row) => {
            const [name, role] = PROVIDER_NAMES[row.id] ?? [row.id, ""];
            const active = row.status === "active";
            return (
              <li key={row.id}>
                <span className={`status-dot ${active ? "ok" : "warn"}`} />
                <span className="provider-name">{name}</span>
                <span className="provider-role">{role}</span>
                <span className="provider-age num">
                  {row.last_success_at ? formatAge(now.getTime() - new Date(row.last_success_at).getTime()) : "ещё не загружен"}
                </span>
              </li>
            );
          })}
        </ul>
      ) : (
        <Waiting />
      )}
      <SourceNote>Статус берётся из /v1/providers и /v1/ready того же сервера, что отдаёт данные.</SourceNote>
    </Panel>
  );
}
