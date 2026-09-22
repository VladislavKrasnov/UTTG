# Security

## Controls

- Public clients receive a keyed, non-reversible IP fingerprint for limiting and analytics.
- Trusted proxy handling accepts explicit IPs or CIDR ranges; forwarded addresses are ignored from untrusted peers.
- Production startup rejects weak/reused HMAC secrets and wildcard CORS.
- Request bodies, provider responses, cache values, query limits, queues, and concurrency are bounded.
- Webhook URLs are resolved before registration and again before every delivery. Loopback, private, link-local, multicast, reserved, and unspecified targets are rejected to limit SSRF and DNS-rebinding attacks.
- Webhook secrets are encrypted at rest and signatures use HMAC-SHA256 over the exact request body.
- Webhook records and delivery history are filtered by owning IP fingerprint.
- Common browser hardening headers are applied to every response.

## Required production controls

The Compose file is a deployment baseline, not a complete internet perimeter. Terminate modern TLS, keep `/metrics` internal, restrict the Docker socket, ship logs off-host, rotate secrets, and monitor repeated rate-limit, SSRF, and webhook failures.

Do not log provider passwords, webhook secrets, authorization headers, full webhook bodies, or database URLs. Treat PostgreSQL analytics as sensitive because pseudonymous identifiers may still be personal data under applicable law.

## Reporting

Report vulnerabilities privately to the repository owner through GitHub's security-advisory mechanism. Include affected version, impact, reproduction steps, and a proposed mitigation when available. Do not include live credentials or third-party personal data.
