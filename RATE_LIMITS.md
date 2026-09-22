# Rate limits

Inbound limits use an atomic Valkey fixed-window counter. Each counter expires after 60 seconds, so one request costs constant memory and no request-level rows are written to PostgreSQL.

| Class | Requests/minute per IP | Intended use |
|---|---:|---|
| `public_light` | 600 | metadata and cached reads |
| `public_standard` | 240 | catalog and normal reads |
| `public_expensive` | 60 | orbital calculations and analytics |
| `mutation` | 30 | webhook mutations |

All operations are public. The limiter uses one Valkey counter per IP, route class, and minute, with a short expiry; it does not write a row for each request to PostgreSQL. If Valkey is unavailable, limited routes return `503` rather than bypassing enforcement. A rejected request returns `429`, `Retry-After`, and RateLimit headers.

## Provider budgets

Provider traffic is generated only by scheduler jobs. Space-Track local guards keep calls below 30/minute and 300/hour and add dataset cooldowns based on its published API-use guidance. NASA states a default authenticated allowance of 1,000 requests/hour and substantially lower `DEMO_KEY` limits. Other provider limits can vary by plan and time; deployment operators must confirm current terms and configure schedules conservatively. HTTP 429 opens a bounded failure path and is not retried immediately.
