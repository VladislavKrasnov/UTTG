# Third-party data notices

Apache-2.0 covers UTTG source code only. It does not grant rights to third-party data, provider names, trademarks, imagery, documentation, or user-submitted webhook payloads.

Operators are responsible for reviewing the current terms for every enabled provider, including account eligibility, attribution, redistribution, caching, retention, automated access, privacy, and commercial-use rules. UTTG's technical quota guards do not replace those agreements.

Provider links and the exact enabled status are maintained in [PROVIDER_CATALOG.md](PROVIDER_CATALOG.md). If a provider is not configured, UTTG does not fetch its data. If no configured provider supports a capability, its endpoints are removed from OpenAPI and direct requests return `ENDPOINT_DISABLED`.
