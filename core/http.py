from __future__ import annotations

from starlette.types import ASGIApp, Message, Receive, Scope, Send


class RequestBodyLimitMiddleware:
    def __init__(self, app: ASGIApp, maximum_bytes: int) -> None:
        self.app = app
        self.maximum_bytes = maximum_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        for name, value in scope.get("headers", []):
            if name.lower() != b"content-length":
                continue
            try:
                if int(value) > self.maximum_bytes:
                    await _payload_too_large(scope, send)
                    return
            except ValueError:
                await _payload_too_large(scope, send)
                return

        consumed = 0

        async def limited_receive() -> Message:
            nonlocal consumed
            message = await receive()
            if message["type"] == "http.request":
                consumed += len(message.get("body", b""))
                if consumed > self.maximum_bytes:
                    raise RequestBodyTooLarge
            return message

        try:
            await self.app(scope, limited_receive, send)
        except RequestBodyTooLarge:
            await _payload_too_large(scope, send)


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        is_docs = path.startswith("/docs") or path == "/openapi.json"

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))

                security_headers = [
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"DENY"),
                    (b"referrer-policy", b"no-referrer"),
                    (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
                ]

                if not is_docs:
                    security_headers.append(
                        (b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'")
                    )

                headers.extend(security_headers)
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_wrapper)


class RequestBodyTooLarge(Exception):
    pass


async def _payload_too_large(scope: Scope, send: Send) -> None:
    body = (
        b'{"type":"https://uttg.example/problems/payload-too-large",'
        b'"title":"Payload too large","status":413,'
        b'"detail":"Request body exceeds the configured limit",'
        b'"code":"PAYLOAD_TOO_LARGE"}'
    )
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [(b"content-type", b"application/problem+json")],
        }
    )
    await send({"type": "http.response.body", "body": body})
