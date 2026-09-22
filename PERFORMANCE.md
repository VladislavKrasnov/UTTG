# Performance and capacity

UTTG is designed so high-volume reads use precomputed PostgreSQL data and Valkey cache entries. API requests never fetch an upstream provider synchronously. This keeps public-provider quotas and latency out of the request path.

## Capacity targets

The repository defines these acceptance targets; they are not benchmark results:

| Workload | Default test rate | Acceptance threshold |
|---|---:|---:|
| Warm Valkey read | 3 requests/s per test IP | p95 < 50 ms, p99 < 150 ms |
| Indexed PostgreSQL read | 1 request/s per test IP | p95 < 250 ms, p99 < 500 ms |
| Combined error rate | — | < 0.5% |
| Dropped k6 iterations | — | 0 |

No throughput number should be presented as achieved until the exact image, host specification, dataset size, command, and resulting k6 summary have been recorded. A small VDS may require lower worker, connection-pool, and arrival-rate settings.

## Load test

The test uses k6 `constant-arrival-rate`; virtual-user count is not treated as requests per second. It requires an ingested record for NORAD 25544 and should stay within the per-IP route quota.

```bash
k6 run \
  --env BASE_URL=https://api.example.com \
  --env CACHE_RPS=3 \
  --env DB_RPS=1 \
  --env DURATION=2m \
  tests/load/k6_script.js
```

Run generators from distinct public IP addresses. Confirm that generator CPU and network are not saturated. Aggregate their results for high-load testing; a single IP is intentionally bounded. Warm the cache before measurement, keep provider ingestion running, and monitor API CPU, event-loop latency, PostgreSQL pool waits, Valkey latency, NATS backlog, dropped analytics metrics, and host network throughput.

## Scaling controls

- API workers are stateless; Valkey shares cache and rate-limit state across replicas.
- The scheduler uses expiring `SET NX` locks so only one replica runs a given ingestion job.
- Cache misses use token-owned single-flight locks and stale-while-revalidate.
- Request metrics enter a bounded in-process queue, are combined by minute/route/method, and use atomic PostgreSQL upserts. This preserves endpoint counts during normal operation without writing one row per request. When the queue is full, metrics are dropped rather than delaying API responses.
- Provider clients have bounded connection pools and concurrency. Webhook delivery consumes bounded JetStream batches.
- PostgreSQL statements and pool acquisition have finite timeouts.

Start with two API workers per container. Increase replicas only after measuring event-loop utilization and total PostgreSQL connections. The total connection ceiling is approximately `replicas × workers × (pool_size + max_overflow)` plus scheduler, worker, migration, and administrative connections.

## Production benchmark record

Before a release is described as meeting the 100,000 requests/minute target, record:

1. commit SHA and container image digest;
2. CPU, RAM, disk, kernel, Docker and network details;
3. row counts and relevant PostgreSQL relation sizes;
4. all `UTTG_DATABASE_*`, worker-count, Valkey memory, and k6 parameters;
5. the complete k6 summary and Prometheus snapshots;
6. a 30-minute soak result and a restart/failover run.

The repository currently contains the reproducible workload and thresholds, not a fabricated benchmark result.
