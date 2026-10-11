import { useEffect, useMemo, useRef, useState } from "react";
import { fetchWithFallback } from "@uttg/shared/api";

const MAX_BACKOFF_MS = 5 * 60 * 1000;

export function usePolling(path, intervalMs) {
  const [state, setState] = useState({ status: "loading", body: null, fetchedAt: null, live: false, latencyMs: null });
  const failures = useRef(0);

  useEffect(() => {
    if (!path) return undefined;
    const controller = new AbortController();
    let timer;

    const run = async () => {
      try {
        const result = await fetchWithFallback(path, { signal: controller.signal });
        failures.current = result.live ? 0 : failures.current + 1;
        setState({
          status: result.live ? "live" : "cached",
          body: result.body,
          fetchedAt: result.fetchedAt,
          live: result.live,
          latencyMs: result.latencyMs,
        });
      } catch (error) {
        if (controller.signal.aborted) return;
        failures.current += 1;
        setState((previous) => ({ ...previous, status: previous.body ? "cached" : "error", live: false, error }));
      }
      const backoff = failures.current ? Math.min(intervalMs, 5000 * 2 ** (failures.current - 1)) : intervalMs;
      timer = setTimeout(run, Math.min(backoff, MAX_BACKOFF_MS));
    };

    const onOnline = () => {
      clearTimeout(timer);
      run();
    };
    window.addEventListener("online", onOnline);
    run();
    return () => {
      controller.abort();
      clearTimeout(timer);
      window.removeEventListener("online", onOnline);
    };
  }, [path, intervalMs]);

  return state;
}

const FEATURED_IDS = [25544, 48274, 20580, 33591, 43013, 28654, 25338, 39084];
const TLE_GROUPS = [
  { key: "featured", label: "МКС, Тяньгун, Hubble и метеоспутники", color: "#ff5c00", query: `ids=${FEATURED_IDS.join(",")}&limit=${FEATURED_IDS.length}` },
  { key: "starlink", label: "Starlink", color: "#ffffff", query: "search=STARLINK&limit=900" },
  { key: "oneweb", label: "OneWeb", color: "#ffffff", query: "search=ONEWEB&limit=300" },
  { key: "cosmos", label: "«Космос»", color: "#ffffff", query: "search=COSMOS&limit=200" },
  { key: "iridium", label: "Iridium", color: "#ffffff", query: "search=IRIDIUM&limit=100" },
  { key: "beidou", label: "BeiDou", color: "#ffffff", query: "search=BEIDOU&limit=80" },
  { key: "gps", label: "GPS (NAVSTAR)", color: "#ffffff", query: "search=NAVSTAR&limit=40" },
];

export function useMissionData() {
  const featured = usePolling(`/v1/orbits/tle?${TLE_GROUPS[0].query}`, 30 * 60 * 1000);
  const starlink = usePolling(`/v1/orbits/tle?${TLE_GROUPS[1].query}`, 60 * 60 * 1000);
  const oneweb = usePolling(`/v1/orbits/tle?${TLE_GROUPS[2].query}`, 60 * 60 * 1000);
  const cosmos = usePolling(`/v1/orbits/tle?${TLE_GROUPS[3].query}`, 60 * 60 * 1000);
  const iridium = usePolling(`/v1/orbits/tle?${TLE_GROUPS[4].query}`, 60 * 60 * 1000);
  const beidou = usePolling(`/v1/orbits/tle?${TLE_GROUPS[5].query}`, 60 * 60 * 1000);
  const gps = usePolling(`/v1/orbits/tle?${TLE_GROUPS[6].query}`, 60 * 60 * 1000);
  const launches = usePolling("/v1/launches/upcoming?limit=10", 5 * 60 * 1000);
  const weather = usePolling("/v1/space-weather/overview", 60 * 1000);
  const kpHistory = usePolling("/v1/space-weather/geomagnetic-indices?limit=180", 5 * 60 * 1000);
  const windHistory = usePolling("/v1/space-weather/solar-wind?limit=180", 5 * 60 * 1000);
  const approaches = usePolling("/v1/neos/close-approaches/upcoming?days=30&limit=40", 30 * 60 * 1000);
  const providers = usePolling("/v1/providers", 30 * 1000);
  const ready = usePolling("/v1/ready", 15 * 1000);

  return useMemo(() => {
    const orbitSources = { featured, starlink, oneweb, cosmos, iridium, beidou, gps };
    const sources = { ...orbitSources, launches, weather, kpHistory, windHistory, approaches, providers, ready };
    const tracked = Object.values(sources);
    const fetchedTimes = tracked.map((source) => source.fetchedAt).filter(Boolean);
    const anyLive = tracked.some((source) => source.status === "live");
    const anyCached = tracked.some((source) => source.status === "cached");
    const connection = anyLive && !anyCached ? "live" : fetchedTimes.length ? "degraded" : tracked.some((source) => source.status === "error") ? "offline" : "loading";
    return {
      ...sources,
      connection,
      oldestFetchedAt: fetchedTimes.length ? Math.min(...fetchedTimes) : null,
      satelliteGroups: TLE_GROUPS.map((group) => ({ ...group, records: orbitSources[group.key].body?.data ?? [] })),
    };
  }, [featured, starlink, oneweb, cosmos, iridium, beidou, gps, launches, weather, kpHistory, windHistory, approaches, providers, ready]);
}

export function useNow(intervalMs = 1000) {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), intervalMs);
    return () => clearInterval(timer);
  }, [intervalMs]);
  return now;
}
