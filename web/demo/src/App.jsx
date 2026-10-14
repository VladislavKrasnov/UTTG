import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { formatAge, formatMoscowTime, formatUtcTime } from "@uttg/shared/format";
import { MissionGlobe, globeAltitude } from "./globe/MissionGlobe.js";
import { buildSatrecs, geodeticAt, groundTrack, orbitalPeriodMinutes, subsolarPoint, toVector } from "./orbits.js";
import { useMissionData, useNow } from "./useLiveData.js";
import { OrbitScene } from "./scenes/OrbitScene.jsx";
import { LaunchScene } from "./scenes/LaunchScene.jsx";
import { WeatherScene } from "./scenes/WeatherScene.jsx";
import { AsteroidScene } from "./scenes/AsteroidScene.jsx";
import { SystemScene } from "./scenes/SystemScene.jsx";
import { Icon } from "./components/Icon.jsx";

const SCENES = [
  { id: "orbit", label: "Орбиты", icon: "orbit", seconds: 28 },
  { id: "launch", label: "Запуски", icon: "rocket", seconds: 24 },
  { id: "weather", label: "Погода", icon: "sun", seconds: 24 },
  { id: "asteroid", label: "Астероиды", icon: "asteroid", seconds: 22 },
  { id: "system", label: "Система", icon: "server", seconds: 20 },
];
const IDLE_RESUME_MS = 90_000;
const CURSOR_HIDE_MS = 3000;
const ISS_NORAD_ID = 25544;
const KIOSK_QUERY = "(min-width: 901px) and (orientation: landscape)";

function toggleFullscreen() {
  if (document.fullscreenElement) {
    document.exitFullscreen?.();
  } else {
    document.documentElement.requestFullscreen?.().catch(() => undefined);
  }
}

function useWakeLock() {
  useEffect(() => {
    let sentinel = null;
    const acquire = async () => {
      try {
        sentinel = await navigator.wakeLock?.request("screen");
      } catch {
        sentinel = null;
      }
    };
    const onVisibility = () => document.visibilityState === "visible" && acquire();
    acquire();
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      sentinel?.release?.();
    };
  }, []);
}

function ConnectionPill({ data, now }) {
  const labels = {
    live: ["ok", "Данные живые"],
    degraded: ["warn", `Нет связи · данные ${data.oldestFetchedAt ? formatAge(now - data.oldestFetchedAt) : ""}`],
    offline: ["danger", "Сервер недоступен"],
    loading: ["muted", "Подключаемся…"],
  };
  const [tone, text] = labels[data.connection];
  return (
    <div className={`pill tone-${tone}`} role="status">
      <span className="status-dot" />
      {text}
    </div>
  );
}

export default function App() {
  const data = useMissionData();
  const now = useNow();
  const globeHost = useRef(null);
  const globe = useRef(null);
  const [globeReady, setGlobeReady] = useState(false);
  const [sceneIndex, setSceneIndex] = useState(0);
  const [autoplay, setAutoplay] = useState(() => window.matchMedia(KIOSK_QUERY).matches);
  const [pausedByUser, setPausedByUser] = useState(() => !window.matchMedia(KIOSK_QUERY).matches);
  const [sceneStartedAt, setSceneStartedAt] = useState(() => Date.now());
  const [lastInteraction, setLastInteraction] = useState(() => Date.now());
  const [cursorHidden, setCursorHidden] = useState(false);
  const [showHelp, setShowHelp] = useState(() => window.matchMedia(KIOSK_QUERY).matches);
  const [iss, setIss] = useState(null);
  const scene = SCENES[sceneIndex];

  useWakeLock();

  useEffect(() => {
    globe.current = new MissionGlobe(globeHost.current, { onReady: () => setGlobeReady(true) });
    return () => globe.current?.dispose();
  }, []);

  const satellites = useMemo(
    () =>
      data.satelliteGroups.flatMap((group) => {
        const seen = new Set();
        return buildSatrecs(group.records.filter((record) => !seen.has(record.norad_id) && seen.add(record.norad_id))).map(
          (entry) => ({ ...entry, color: group.color, group: group.key, groupLabel: group.label }),
        );
      }),
    [data.satelliteGroups],
  );
  const issSatrec = useMemo(() => satellites.find((entry) => entry.norad_id === ISS_NORAD_ID)?.satrec ?? null, [satellites]);

  useEffect(() => {
    if (!globe.current) return undefined;
    const update = () => {
      const date = new Date();
      const groups = new Map();
      let issPoint = null;
      for (const entry of satellites) {
        const point = geodeticAt(entry.satrec, date);
        if (!point) continue;
        const item = { ...point, noradId: entry.norad_id, name: entry.name };
        if (entry.norad_id === ISS_NORAD_ID) issPoint = point;
        const key = entry.norad_id === ISS_NORAD_ID ? "highlight" : entry.group;
        if (!groups.has(key)) {
          const highlight = key === "highlight";
          groups.set(key, { items: [], color: highlight || entry.group === "featured" ? "#ff5c00" : entry.color, size: highlight ? 14 : entry.group === "featured" ? 10 : 4.5 });
        }
        groups.get(key).items.push(item);
      }
      globe.current.setSatellites([...groups.values()]);
      setIss(issPoint && issSatrec ? { ...issPoint, periodMinutes: orbitalPeriodMinutes(issSatrec) } : null);
    };
    update();
    const timer = setInterval(update, 1000);
    return () => clearInterval(timer);
  }, [satellites, issSatrec]);

  const trackedSatrec = scene.id === "orbit" ? issSatrec : null;
  useEffect(() => {
    if (!globe.current) return undefined;
    if (!trackedSatrec) {
      globe.current.setTracks([]);
      return undefined;
    }
    const update = () => {
      const half = Math.round(orbitalPeriodMinutes(trackedSatrec) / 2);
      const toPath = (points) => points.map((point) => [point.latitude, point.longitude, globeAltitude(point.altitudeKm)]);
      globe.current.setTracks([
        { points: toPath(groundTrack(trackedSatrec, new Date(), half, 0)), color: "rgba(255, 92, 0, 0.45)", stroke: 0.6, dash: 1, gap: 0, animate: 0 },
        { points: toPath(groundTrack(trackedSatrec, new Date(), 0, half * 2)), color: "#ff5c00", stroke: 0.9, dash: 1, gap: 0, animate: 0 },
      ]);
    };
    update();
    const timer = setInterval(update, 30_000);
    return () => clearInterval(timer);
  }, [trackedSatrec]);

  const launches = data.launches.body?.data ?? null;
  const nextLaunch = launches?.find((launch) => new Date(launch.window_start).getTime() > now.getTime() - 3600_000) ?? null;
  const overview = data.weather.body?.data ?? null;
  const issRef = useRef(null);
  const hasIss = Boolean(iss);

  useEffect(() => {
    issRef.current = iss;
  }, [iss]);

  useEffect(() => {
    const view = globe.current;
    if (!view || !globeReady) return;
    view.setSite(null);
    view.setAurora(null);
    if (scene.id === "orbit" && issRef.current) {
      view.focus(issRef.current.latitude, issRef.current.longitude, "default");
    } else if (scene.id === "launch" && nextLaunch?.latitude != null) {
      view.setSite({ latitude: nextLaunch.latitude, longitude: nextLaunch.longitude, label: nextLaunch.pad ?? nextLaunch.location ?? "" });
      view.focus(nextLaunch.latitude, nextLaunch.longitude, "near");
    } else if (scene.id === "weather") {
      view.setAurora(overview?.kp_index ?? null);
      view.focus(62, 40, "default");
    } else {
      view.spin(scene.id === "asteroid" ? "far" : "default");
    }
  }, [scene.id, globeReady, hasIss, nextLaunch?.id, nextLaunch?.latitude, nextLaunch?.longitude, nextLaunch?.pad, nextLaunch?.location, overview?.kp_index]);

  const goTo = useCallback((index, { manual = true } = {}) => {
    setSceneIndex(((index % SCENES.length) + SCENES.length) % SCENES.length);
    setSceneStartedAt(Date.now());
    if (manual) {
      setAutoplay(false);
      setLastInteraction(Date.now());
    }
  }, []);

  useEffect(() => {
    if (!autoplay) return undefined;
    const remaining = scene.seconds * 1000 - (Date.now() - sceneStartedAt);
    const timer = setTimeout(() => goTo(sceneIndex + 1, { manual: false }), Math.max(remaining, 0));
    return () => clearTimeout(timer);
  }, [autoplay, scene.seconds, sceneIndex, sceneStartedAt, goTo]);

  useEffect(() => {
    if (autoplay || pausedByUser) return undefined;
    const timer = setTimeout(() => {
      setAutoplay(true);
      setSceneStartedAt(Date.now());
    }, Math.max(IDLE_RESUME_MS - (Date.now() - lastInteraction), 0));
    return () => clearTimeout(timer);
  }, [autoplay, pausedByUser, lastInteraction]);

  const togglePlay = useCallback(() => {
    setAutoplay((value) => {
      setPausedByUser(value);
      return !value;
    });
    setSceneStartedAt(Date.now());
    setLastInteraction(Date.now());
  }, []);

  useEffect(() => {
    const onKey = (event) => {
      setLastInteraction(Date.now());
      setShowHelp(false);
      const key = event.key.toLowerCase();
      if (event.key === "ArrowRight" || event.key === "PageDown") goTo(sceneIndex + 1);
      else if (event.key === "ArrowLeft" || event.key === "PageUp") goTo(sceneIndex - 1);
      else if (event.key === " ") {
        event.preventDefault();
        togglePlay();
      } else if (key === "f" || key === "а") toggleFullscreen();
      else if (key === "h" || key === "р" || event.key === "?") setShowHelp((value) => !value);
      else if (/^[1-5]$/.test(event.key)) goTo(Number(event.key) - 1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [goTo, sceneIndex, togglePlay]);

  useEffect(() => {
    let timer;
    const onMove = () => {
      setCursorHidden(false);
      clearTimeout(timer);
      timer = setTimeout(() => setCursorHidden(true), CURSOR_HIDE_MS);
    };
    window.addEventListener("pointermove", onMove);
    onMove();
    return () => {
      clearTimeout(timer);
      window.removeEventListener("pointermove", onMove);
    };
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => setShowHelp(false), 9000);
    return () => clearTimeout(timer);
  }, []);

  const issInDaylight = useMemo(() => {
    if (!iss) return true;
    const sun = subsolarPoint(now);
    const [sx, sy, sz] = toVector(sun.latitude, sun.longitude, 1);
    const [ix, iy, iz] = toVector(iss.latitude, iss.longitude, 1);
    return sx * ix + sy * iy + sz * iz > -0.25;
  }, [iss, now]);

  const groupCounts = data.satelliteGroups.map((group) => ({
    ...group,
    count: satellites.filter((entry) => entry.group === group.key).length,
  }));

  const progress = autoplay ? Math.min((now.getTime() - sceneStartedAt) / (scene.seconds * 1000), 1) : 0;

  return (
    <div className={`kiosk ${cursorHidden ? "hide-cursor" : ""}`}>
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">ЕШКТ</span>
          <span className="brand-sub">Единый шлюз космической телеметрии</span>
        </div>
        <div className="clocks num">
          <div><span>МСК</span>{formatMoscowTime(now)}</div>
          <div><span>UTC</span>{formatUtcTime(now)}</div>
        </div>
        <ConnectionPill data={data} now={now.getTime()} />
      </header>

      <main className="stage">
        <div className="globe-area">
          <div className="globe" ref={globeHost} />
          {!globeReady && <div className="globe-loading">Загружаем Землю…</div>}
        </div>
        <div className="scene-panel" key={scene.id}>
          {scene.id === "orbit" && <OrbitScene iss={iss} trackedCount={satellites.length} groups={groupCounts} issInDaylight={issInDaylight} />}
          {scene.id === "launch" && <LaunchScene launches={launches} now={now} />}
          {scene.id === "weather" && (
            <WeatherScene overview={overview} kpHistory={data.kpHistory.body?.data} windHistory={data.windHistory.body?.data} />
          )}
          {scene.id === "asteroid" && <AsteroidScene approaches={data.approaches.body?.data ?? null} />}
          {scene.id === "system" && <SystemScene providers={data.providers.body} ready={data.ready} now={now} />}
        </div>
      </main>

      <nav className="dock" aria-label="Разделы демонстрации">
        {SCENES.map((item, index) => (
          <button
            key={item.id}
            type="button"
            className={`dock-button ${index === sceneIndex ? "active" : ""}`}
            onClick={() => goTo(index)}
            aria-current={index === sceneIndex ? "true" : undefined}
          >
            <Icon name={item.icon} />
            <span>{item.label}</span>
            <kbd>{index + 1}</kbd>
            {index === sceneIndex && <i className="dock-progress" style={{ transform: `scaleX(${progress})` }} />}
          </button>
        ))}
        <div className="dock-divider" />
        <button type="button" className={`dock-button control ${autoplay ? "" : "paused"}`} onClick={togglePlay}>
          <Icon name={autoplay ? "pause" : "play"} />
          <span>{autoplay ? "Пауза" : "Продолжить"}</span>
        </button>
        <button type="button" className="dock-button control" onClick={toggleFullscreen}>
          <Icon name="expand" />
          <span>Экран</span>
        </button>
        <button type="button" className="dock-button control" onClick={() => setShowHelp((value) => !value)}>
          <Icon name="help" />
          <span>Помощь</span>
        </button>
      </nav>


      {showHelp && (
        <div className="help" role="dialog" aria-label="Как управлять демо" onClick={() => setShowHelp(false)}>
          <div className="help-card">
            <h2>Демо работает само</h2>
            <p>Разделы сменяют друг друга сами. Чтобы открыть нужный, нажмите на него внизу экрана.</p>
            <ul>
              <li><kbd>1</kbd>–<kbd>5</kbd> или <kbd>←</kbd> <kbd>→</kbd> — разделы</li>
              <li><kbd>Пробел</kbd> — пауза и продолжение</li>
              <li><kbd>F</kbd> — во весь экран</li>
              <li>Глобус можно крутить и приближать мышью или пальцем</li>
            </ul>
            <button type="button" className="help-close">Понятно</button>
          </div>
        </div>
      )}
    </div>
  );
}
