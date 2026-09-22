# API guide

Interactive documentation is served at `/docs`; the machine-readable schema is `/openapi.json`. OpenAPI is generated from the active provider configuration, so deployments can expose different route sets without advertising unavailable functionality.

## Response contract

Successful domain responses use `{ "data": ..., "meta": ... }`. Metadata contains the canonical schema version, timestamps, freshness, configured and healthy provider counts, source IDs, partial-result status, and warnings. Cached operations return `X-Cache-State`. Rate-limited operations return `RateLimit-Limit`, `RateLimit-Remaining`, and `RateLimit-Reset`.

Errors use a stable problem-details shape with `type`, `title`, `status`, `detail`, `instance`, `code`, and `request_id`. Validation errors additionally include a bounded field-error list. Send an existing safe `X-Request-Id` to correlate logs; otherwise the API creates one.

## Public access and pagination

No API key or account is required. Limits are enforced per client IP address using a keyed, non-reversible digest in Valkey. Catalog endpoints use a bounded `limit`; satellite and NEO collections also support stable cursor pagination. Limits are validated before database work.

## Endpoint groups

### Platform

- readiness, version, active capabilities, provider list, and provider detail;
- reports only configured providers and observed ingestion health.

### Satellite catalog

- lookup by NORAD catalog number or COSPAR ID;
- cursor-based catalog listing;
- identifiers, catalog metadata, and the provider-supplied status.
- cached catalog totals and value/count facets for country, operator, object type, status, and orbit class;
- decay list and lookup by NORAD ID.

### Orbital data

- latest or historical orbital elements;
- SGP4 position at a supplied UTC instant within 30 days of now;
- bounded ground track, orbit summary, orbital changes, coverage count, and latest-epoch coverage.

SGP4 output is converted from TEME using GMST and WGS-84. It does not apply IERS Earth-orientation parameters and must not be used for safety-of-life, conjunction-avoidance, or precision pointing decisions.

### Launches

- upcoming launches, next launch, bounded calendar, status statistics, recent catalog, and launch detail from locally ingested Launch Library data.

### Space weather

- latest overview derived from ingested Kp and solar-wind observations;
- latest readings, data-age report, and bounded geomagnetic-index and solar-wind histories.

### Near-Earth objects

- cursor-based object catalog, hazardous subset, summary statistics, bounded upcoming close approaches, historical approaches, and object detail;
- present only when a NASA provider credential is configured.

### Webhooks

- create, list, inspect, update, soft-delete, and inspect deliveries;
- registration requires an `Idempotency-Key`;
- secrets are returned once, encrypted at rest, and used for signed delivery;
- records are isolated by the originating IP fingerprint.

### Administration

- provider status and bounded endpoint-analytics time series;
- is public and rate-limited as an expensive operation.

## Disabled paths

Routes that lack a complete implementation are explicitly kept out of OpenAPI. Direct calls return `503` with code `ENDPOINT_DISABLED`; they never return invented provider data or silently empty success payloads. Upstream adapters use fixed, reviewed provider paths rather than accepting caller-controlled upstream paths.
