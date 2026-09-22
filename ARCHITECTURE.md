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

## Deployment

Compose runs migration, API, scheduler, worker, TimescaleDB, Valkey, NATS, and Traefik services. Application containers run as UID 10001 with a read-only root filesystem and `no-new-privileges`. Data services are not published to the host. Prometheus and Grafana are optional and bind only to localhost.

For multiple hosts, move PostgreSQL, Valkey, and NATS to replicated managed or independently operated clusters, use a real secret manager, add TLS and authentication between services, and replace the Docker socket mount with a restricted proxy or a non-Docker service-discovery mechanism. Test backup restoration, graceful shutdown, dependency loss, and rolling migration behavior before accepting production traffic.

## Schema changes

Run `alembic upgrade head` as a one-shot deployment step before starting new workers. Review lock duration and table rewrite risk for every future migration. Large-table index changes should use an online migration strategy rather than the simple development migrations included here.
