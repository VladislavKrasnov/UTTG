# Unified Technical Telemetry Gateway (UTTG)

UTTG is a self-hosted REST API that normalizes satellite catalog, orbital, launch, near-Earth-object, and space-weather data. Provider ingestion runs outside the request path; clients read bounded, indexed local data and Valkey cache entries.

This implementation is based on [github.com/VladislavKrasnov/UTTG](https://github.com/VladislavKrasnov/UTTG), authored by [Vladislav Krasnov](https://github.com/VladislavKrasnov). The code is licensed under Apache-2.0. Upstream data remains subject to each provider's terms.

## Start locally

Requirements: Docker with Compose v2. Nix users can enter the reproducible development shell with `nix develop`.

```bash
cp .env.example .env
# Replace every required secret and make the password in UTTG_DATABASE_URL
# match UTTG_POSTGRES_PASSWORD.
docker compose up --build -d
curl http://localhost/v1/ready
```

UTTG is a public API: no account or API key is required. Every request is limited by a privacy-preserving HMAC digest of the client IP address in Valkey. The raw address is never stored.

For production set `UTTG_ENVIRONMENT=production`, use independent random secrets of at least 32 characters, terminate TLS at the edge, restrict host firewall access, pin deployed images by digest, and back up PostgreSQL, Valkey, and NATS volumes.

## Behavior

- Only configured provider capabilities appear in OpenAPI at `/docs`.
- An endpoint with no configured provider is omitted from OpenAPI and returns `503 ENDPOINT_DISABLED` if called directly.
- Every documented operation includes `x-uttg-provider-count`, provider IDs, and a resilience label.
- All documented routes are public. Limits differ by query cost and are enforced per client IP address.
- `/v1/health` is liveness; `/v1/ready` checks the PostgreSQL and Valkey dependencies required to serve API traffic. NATS readiness is isolated to the scheduler and webhook worker.
- `/metrics` is available only on the internal application network in the supplied Compose routing.

## Documentation

- [API guide](API_GUIDE.md)
- [Architecture and operations](ARCHITECTURE.md)
- [Provider catalog](PROVIDER_CATALOG.md)
- [Rate limits](RATE_LIMITS.md)
- [Security](SECURITY.md)
- [Performance and capacity](PERFORMANCE.md)
- [Third-party data notices](THIRD_PARTY_DATA_NOTICES.md)

## Verification

```bash
python -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy api core ingestion providers storage
.venv/bin/pytest
.venv/bin/python -m pip wheel . --no-deps --wheel-dir dist
```
