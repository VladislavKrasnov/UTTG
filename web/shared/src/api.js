const REQUEST_TIMEOUT_MS = 8000;
const STORAGE_PREFIX = "uttg:last-good:";

function readStored(path) {
  try {
    const raw = localStorage.getItem(STORAGE_PREFIX + path);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function writeStored(path, entry) {
  try {
    localStorage.setItem(STORAGE_PREFIX + path, JSON.stringify(entry));
  } catch {
    return;
  }
}

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

export async function fetchApi(path, { signal } = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  const abortFromCaller = () => controller.abort();
  signal?.addEventListener("abort", abortFromCaller, { once: true });
  const startedAt = performance.now();
  try {
    const response = await fetch(path, {
      signal: controller.signal,
      headers: { Accept: "application/json" },
      credentials: "omit",
    });
    if (!response.ok) {
      throw new ApiError(response.status, `HTTP ${response.status}`);
    }
    const body = await response.json();
    const entry = {
      body,
      fetchedAt: Date.now(),
      latencyMs: Math.round(performance.now() - startedAt),
    };
    writeStored(path, entry);
    return { ...entry, live: true };
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", abortFromCaller);
  }
}

export async function fetchWithFallback(path, options) {
  try {
    return await fetchApi(path, options);
  } catch (error) {
    if (error?.name === "AbortError" && options?.signal?.aborted) {
      throw error;
    }
    const stored = readStored(path);
    if (stored) {
      return { ...stored, live: false, error };
    }
    throw error;
  }
}
