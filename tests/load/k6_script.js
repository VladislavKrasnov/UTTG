import http from 'k6/http';
import { check } from 'k6';
import { Rate } from 'k6/metrics';

const cacheHitRate = new Rate('cache_hit_rate');

export const options = {
  scenarios: {
    cached_read: {
      executor: 'constant-arrival-rate',
      exec: 'cachedRead',
      rate: Number(__ENV.CACHE_RPS || 3),
      timeUnit: '1s',
      duration: __ENV.DURATION || '2m',
      preAllocatedVUs: Number(__ENV.CACHE_VUS || 200),
      maxVUs: Number(__ENV.MAX_VUS || 2000),
    },
    database_read: {
      executor: 'constant-arrival-rate',
      exec: 'databaseRead',
      rate: Number(__ENV.DB_RPS || 1),
      timeUnit: '1s',
      duration: __ENV.DURATION || '2m',
      preAllocatedVUs: 20,
      maxVUs: 200,
      startTime: '10s',
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.005'],
    dropped_iterations: ['count==0'],
    cache_hit_rate: ['rate>0.99'],
    'http_req_duration{workload:cached}': ['p(95)<50', 'p(99)<150'],
    'http_req_duration{workload:database}': ['p(95)<250', 'p(99)<500'],
  },
};

const BASE = __ENV.BASE_URL || 'http://localhost:8000';
const params = {};

export function setup() {
  const warmup = http.get(`${BASE}/v1/satellites/25544/orbital-elements/latest`, params);
  if (warmup.status !== 200) {
    throw new Error(`Warm-up requires ingested NORAD 25544 data; received ${warmup.status}`);
  }
}

export function cachedRead() {
  const response = http.get(`${BASE}/v1/satellites/25544/orbital-elements/latest`, {
    ...params,
    tags: { workload: 'cached' },
  });
  check(response, { 'cached response is 200': (result) => result.status === 200 });
  cacheHitRate.add(response.headers['X-Cache-State'] === 'fresh');
}

export function databaseRead() {
  const response = http.get(`${BASE}/v1/satellites?limit=50`, {
    ...params,
    tags: { workload: 'database' },
  });
  check(response, { 'database response is 200': (result) => result.status === 200 });
}
