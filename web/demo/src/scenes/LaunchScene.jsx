import { formatDateTime, pad2, splitCountdown } from "@uttg/shared/format";
import { Panel, SourceNote, Waiting } from "../components/Panel.jsx";

const STATUS_LABELS = {
  Go: "Готов к старту",
  Scheduled: "Время старта назначено",
  TBC: "Ждёт подтверждения",
  TBD: "Дата уточняется",
  Hold: "Отсчёт остановлен",
  "In Flight": "В полёте",
};

const WEATHER_WORDS = [
  ["thunder", "гроза"],
  ["drizzle", "морось"],
  ["rain", "дождь"],
  ["snow", "снег"],
  ["mist", "дымка"],
  ["fog", "туман"],
  ["overcast", "пасмурно"],
  ["cloud", "облачно"],
  ["clear", "ясно"],
  ["sun", "солнечно"],
  ["wind", "ветер"],
];

function translateWeather(summary) {
  if (!summary) return null;
  return summary
    .split(" · ")
    .map((part) => {
      const lower = part.toLowerCase();
      const match = WEATHER_WORDS.find(([english]) => lower.startsWith(english));
      return match ? part.replace(new RegExp(match[0], "i"), match[1]).replace(/^\w/, (c) => c.toUpperCase()) : part;
    })
    .join(" · ")
    .replace("m/s", "м/с");
}

const missionName = (name) => name.split(" | ").at(-1);

function Countdown({ target, now }) {
  const difference = new Date(target).getTime() - now.getTime();
  if (difference <= 0) {
    return <div className="countdown liftoff">Старт!</div>;
  }
  const { days, hours, minutes, seconds } = splitCountdown(difference);
  const units = [
    [days, "дн"],
    [hours, "ч"],
    [minutes, "мин"],
    [seconds, "с"],
  ];
  return (
    <div className="countdown num" aria-live="off">
      {units.map(([value, label]) => (
        <div className="countdown-cell" key={label}>
          <span className="countdown-value">{pad2(value)}</span>
          <span className="countdown-label">{label}</span>
        </div>
      ))}
    </div>
  );
}

export function LaunchScene({ launches, now }) {
  if (!launches) return <Panel eyebrow="Запуски" title="Ближайшие старты ракет"><Waiting /></Panel>;
  const upcoming = launches.filter((launch) => new Date(launch.window_start).getTime() > now.getTime() - 3600_000);
  const [next, ...rest] = upcoming;
  if (!next) {
    return (
      <Panel eyebrow="Запуски" title="Ближайшие старты ракет">
        <p className="lead">В расписании сейчас нет подтверждённых стартов. Планировщик проверяет источник каждые 30 минут.</p>
      </Panel>
    );
  }
  const weather = translateWeather(next.weather_summary);
  return (
    <Panel eyebrow="Ближайший запуск" title={missionName(next.name)}>
      <Countdown target={next.window_start} now={now} />
      <dl className="facts">
        <div><dt>Оператор</dt><dd>{next.operator ?? "—"}</dd></div>
        <div><dt>Ракета</dt><dd>{next.vehicle ?? "—"}</dd></div>
        <div><dt>Площадка</dt><dd>{[next.pad, next.location].filter(Boolean).join(", ") || "—"}</dd></div>
        <div><dt>Старт (МСК)</dt><dd>{formatDateTime(next.window_start)}</dd></div>
        <div><dt>Статус</dt><dd>{STATUS_LABELS[next.status] ?? next.status ?? "—"}</dd></div>
        {weather && <div><dt>Погода на старте</dt><dd>{weather}</dd></div>}
      </dl>
      {rest.length > 0 && (
        <ol className="launch-list">
          {rest.slice(0, 4).map((launch) => (
            <li key={launch.id}>
              <span className="launch-name">{missionName(launch.name)}</span>
              <span className="launch-meta">{[launch.operator, launch.vehicle].filter(Boolean).join(" · ")}</span>
              <span className="launch-date num">{formatDateTime(launch.window_start)}</span>
            </li>
          ))}
        </ol>
      )}
      <SourceNote>Расписание: {next.provider === "rocketlaunch-live" ? "RocketLaunch.Live" : "Launch Library 2"}. Точка на глобусе — стартовая площадка.</SourceNote>
    </Panel>
  );
}
