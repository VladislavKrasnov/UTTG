import { useEffect, useState } from "react";
import { fetchApi } from "@uttg/shared/api";
import { formatAge } from "@uttg/shared/format";
import qrHub from "@uttg/shared/qr/hub.svg";
import { Research } from "./Research.jsx";

const LINKS = [
  {
    href: "https://demo.uttg.oxis.cc",
    title: "Живое демо",
    text: "Центр управления: спутники на глобусе, ближайший запуск, космическая погода и астероиды. Работает само, управляется кнопками внизу.",
    tag: "demo.uttg.oxis.cc",
    accent: true,
  },
  {
    href: "https://presentation.uttg.oxis.cc",
    title: "Презентация",
    text: "12 слайдов о проблеме, исследовании источников, архитектуре и результатах. Стрелки — листать, F — во весь экран.",
    tag: "presentation.uttg.oxis.cc",
  },
  {
    href: "https://uttg.oxis.cc/docs",
    title: "Документация API",
    text: "Интерактивный Swagger: каждый эндпоинт можно вызвать прямо из браузера. Ключ не нужен.",
    tag: "uttg.oxis.cc/docs",
  },
  {
    href: "/research",
    title: "Исследовательская работа",
    text: "Что и как мы проверяли: доступность источников, форматы данных, модель SGP4, надёжность и нагрузка. С источниками.",
    tag: "hub.uttg.oxis.cc/research",
  },
  {
    href: "https://github.com/VladislavKrasnov/UTTG",
    title: "Исходный код",
    text: "Python 3.13, FastAPI, PostgreSQL/TimescaleDB, Valkey, NATS JetStream, React. Лицензия Apache-2.0.",
    tag: "github.com/VladislavKrasnov/UTTG",
  },
];

const PROVIDER_NAMES = {
  celestrak: "CelesTrak — орбиты",
  "noaa-swpc": "NOAA SWPC — космическая погода",
  "jpl-ssd": "NASA/JPL — астероиды",
  "rocketlaunch-live": "RocketLaunch.Live — запуски",
  "the-space-devs": "Launch Library 2 — запуски",
  "space-track": "Space-Track — каталог",
  "nasa-neows": "NASA NeoWs — астероиды",
};

function Status() {
  const [state, setState] = useState({ ready: null, providers: null, latencyMs: null, checkedAt: 0 });
  useEffect(() => {
    const load = async () => {
      const [ready, providers] = await Promise.allSettled([fetchApi("/v1/ready"), fetchApi("/v1/providers")]);
      setState({
        ready: ready.status === "fulfilled",
        latencyMs: ready.status === "fulfilled" ? ready.value.latencyMs : null,
        providers: providers.status === "fulfilled" ? providers.value.body.data : null,
        checkedAt: Date.now(),
      });
    };
    load();
    const timer = setInterval(load, 30000);
    return () => clearInterval(timer);
  }, []);
  return (
    <section className="status" aria-label="Состояние системы">
      <div className="status-head">
        <span className={`dot ${state.ready ? "ok" : state.ready === false ? "bad" : ""}`} />
        <strong>{state.ready ? "Все системы работают" : state.ready === false ? "API недоступен" : "Проверяем…"}</strong>
        {state.latencyMs != null && <span className="muted num">ответ за {state.latencyMs} мс</span>}
      </div>
      {state.providers && (
        <ul>
          {state.providers.map((provider) => (
            <li key={provider.id}>
              <span className={`dot ${provider.status === "active" ? "ok" : "warn"}`} />
              <span>{PROVIDER_NAMES[provider.id] ?? provider.id}</span>
              <span className="muted num">
                {provider.last_success_at ? formatAge(state.checkedAt - new Date(provider.last_success_at).getTime()) : "ожидает загрузки"}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function Home() {
  return (
    <main className="home">
      <header className="masthead">
        <div>
          <div className="brand">ЕШКТ</div>
          <h1>Единый шлюз космической телеметрии</h1>
          <p className="lede">
            Один REST API для орбит спутников, расписания запусков, космической погоды и сближений астероидов. Источники — CelesTrak,
            NOAA, NASA/JPL и сервисы запусков — опрашиваются в фоне, а клиенты получают единый формат за миллисекунды.
          </p>
          <p className="author">Владислав Краснов · fullstack-разработчик</p>
        </div>
        <figure className="qr-block">
          <img src={qrHub} alt="QR-код этой страницы" />
          <figcaption>Откройте на телефоне</figcaption>
        </figure>
      </header>
      <nav className="cards">
        {LINKS.map((link) => (
          <a key={link.href} href={link.href} className={`card ${link.accent ? "accent" : ""}`} rel={link.href.startsWith("http") ? "noopener" : undefined}>
            <span className="card-title">{link.title}</span>
            <span className="card-text">{link.text}</span>
            <span className="card-tag num">{link.tag} →</span>
          </a>
        ))}
      </nav>
      <Status />
      <footer className="footer">Код — Apache-2.0. Данные принадлежат их источникам: CelesTrak, NOAA SWPC, NASA/JPL CNEOS, RocketLaunch.Live.</footer>
    </main>
  );
}

export default function App() {
  return window.location.pathname.replace(/\/$/, "") === "/research" ? <Research /> : <Home />;
}
