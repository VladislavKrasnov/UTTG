# Architecture and operations

UTTG is a modular monolith with separate runtime roles.

```text
client -> reverse proxy -> API workers -> Valkey
                              |         -> PostgreSQL / TimescaleDB
                              +--------> NATS JetStream

scheduler -> fixed provider adapters -> PostgreSQL
worker <- JetStream -> validated, signed webhooks
```

The API never calls a provider while serving a client request. The scheduler performs bounded ingestion and bulk upserts. PostgreSQL is the durable canonical store; TimescaleDB hypertables hold provider time-series and minute-level endpoint metric buckets. Valkey supplies cache, distributed single-flight locks, rate limits, idempotency, provider circuit state, and scheduler leader locks. NATS JetStream supplies durable webhook work and a dead-letter subject.

## Failure behavior

- dependency readiness fails closed without exposing connection strings or driver errors;
- cache stampedes are collapsed with token-owned Lua locks;
- stale values may be served during bounded background refresh;
- cache computation, database pool acquisition, SQL statements, provider HTTP calls, and webhook calls all have finite limits;
- analytics uses a bounded queue and drops metrics under overload instead of adding request latency;
- provider adapters cap response size, connection count, and concurrency;
- webhook consumers acknowledge only after a terminal success or durable dead-letter action.

## Ingestion scheduling

Each job takes a 15-minute lease in Valkey while it runs and extends it to the full interval only after success, so a crashed process retries within minutes instead of hours. Failures back off exponentially from 60 s up to the job interval with ±20% jitter. Health writes are best effort and never stop a job loop; jobs run in an `asyncio.TaskGroup`, so a fatal error terminates the process and the orchestrator restarts it. Provider transports open a 10-minute circuit after five failures in five minutes, including 403 and 429 replies.

| Job | Interval |
|---|---|
| NOAA SWPC | 5 min |
| Launches | 30 min |
| CelesTrak | 2 h |
| JPL close approaches | 6 h |
| Space-Track SATCAT | 24 h |

## Deployment

Local development uses Compose (`compose.yml`). Production runs the single-node Swarm stack in `deploy/stack.yml`: two API replicas with start-first rolling updates and automatic rollback, Caddy with automatic TLS, host-mode ports so client addresses reach the rate limiter, and memory limits sized for 1 vCPU / 2 GB. Caddy discovers API tasks through `tasks.api`, health-checks them and retries a request for up to 15 s during a rollout.

`deploy/release.sh` runs from a workstation: it builds the web apps in `web/`, syncs code and static sites over SSH and calls `deploy/deploy.sh` on the server, which builds the image, applies migrations and rolls the stack. Secrets live only in `deploy/.env` on the server. `deploy/uttg-backup.timer` writes a verified daily `pg_dump`; TimescaleDB retention keeps orbital elements 45 days, space weather 120 days and endpoint metrics 30 days.

Static sites served by Caddy share the API origin under `/v1`, so they need no CORS and run under a strict Content-Security-Policy:

| Host | Content |
|---|---|
| `uttg.oxis.cc` | REST API and `/docs` |
| `demo.uttg.oxis.cc` | live kiosk (`web/demo`) |
| `presentation.uttg.oxis.cc` | slides with presenter mode (`web/presentation`) |
| `hub.uttg.oxis.cc` | index and research paper (`web/hub`) |

## Schema changes

Run `alembic upgrade head` as a one-shot deployment step before starting new workers. Review lock duration and table rewrite risk for every future migration. Large-table index changes should use an online migration strategy rather than the simple development migrations included here.
