import { useEffect, useState } from "react";
import { fetchWithFallback } from "@uttg/shared/api";
import { formatAge, formatDateTime, formatDecimal } from "@uttg/shared/format";

const SOURCES = {
  weather: "/v1/space-weather/overview",
  launches: "/v1/launches/upcoming?limit=1",
  approaches: "/v1/neos/close-approaches/upcoming?days=30&limit=1",
  ready: "/v1/ready",
};

export function LiveTelemetry() {
  const [state, setState] = useState({});

  useEffect(() => {
    const controller = new AbortController();
    const load = async () => {
      const entries = await Promise.all(
        Object.entries(SOURCES).map(async ([key, path]) => {
          try {
            return [key, await fetchWithFallback(path, { signal: controller.signal })];
          } catch {
            return [key, null];
          }
        }),
      );
      if (!controller.signal.aborted) setState({ ...Object.fromEntries(entries), checkedAt: Date.now() });
    };
    load();
    const timer = setInterval(load, 15000);
    return () => {
      controller.abort();
      clearInterval(timer);
    };
  }, []);

  const weather = state.weather?.body?.data;
  const launch = state.launches?.body?.data?.[0];
  const approach = state.approaches?.body?.data?.[0];
  const ready = state.ready;

  return (
    <div className="telemetry">
      <div className="telemetry-head">
        <span className={`dot ${ready?.live ? "ok" : "warn"}`} />
        {ready?.live ? "Данные прямо сейчас с uttg.oxis.cc" : "Ждём ответ API…"}
      </div>
      <div className="telemetry-grid">
        <div>
          <span className="telemetry-label">Индекс Kp сейчас</span>
          <span className="telemetry-value num">{weather?.kp_index != null ? formatDecimal(weather.kp_index) : "—"}</span>
          <span className="telemetry-note">
            {weather?.kp_observed_at ? `NOAA, ${formatAge(state.checkedAt - new Date(weather.kp_observed_at).getTime())}` : ""}
          </span>
        </div>
        <div>
          <span className="telemetry-label">Солнечный ветер</span>
          <span className="telemetry-value num">
            {weather?.solar_wind_speed_km_s != null ? `${Math.round(weather.solar_wind_speed_km_s)} км/с` : "—"}
          </span>
        </div>
        <div>
          <span className="telemetry-label">Ближайший запуск</span>
          <span className="telemetry-value small">{launch?.name.split(" | ").at(-1) ?? "—"}</span>
          <span className="telemetry-note">{launch ? `${launch.operator ?? ""} · ${formatDateTime(launch.window_start)}` : ""}</span>
        </div>
        <div>
          <span className="telemetry-label">Ближайший астероид</span>
          <span className="telemetry-value small">{approach?.name ?? "—"}</span>
          <span className="telemetry-note">
            {approach ? `${formatDecimal(approach.miss_distance_lunar)} расстояния до Луны · ${formatDateTime(approach.close_approach_date)}` : ""}
          </span>
        </div>
      </div>
    </div>
  );
}
