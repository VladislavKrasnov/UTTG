from __future__ import annotations

import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import ORJSONResponse

from core.cache_layer import CacheBusyError, CacheValueTooLargeError


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(CacheBusyError)
    async def cache_busy(request: Request, _exc: CacheBusyError) -> ORJSONResponse:
        request.state.error_code = "CACHE_FILL_IN_PROGRESS"
        return ORJSONResponse(
            {
                "type": "https://uttg.example/problems/cache-fill-in-progress",
                "title": "Service temporarily busy",
                "status": 503,
                "detail": "A cache fill is already in progress; retry shortly",
                "instance": request.url.path,
                "code": "CACHE_FILL_IN_PROGRESS",
                "request_id": getattr(request.state, "request_id", str(uuid.uuid4())),
            },
            status_code=503,
            headers={"Retry-After": "1"},
        )

    @app.exception_handler(CacheValueTooLargeError)
    async def cache_value_too_large(
        request: Request, _exc: CacheValueTooLargeError
    ) -> ORJSONResponse:
        request.state.error_code = "CACHE_VALUE_TOO_LARGE"
        return ORJSONResponse(
            {
                "type": "https://uttg.example/problems/cache-value-too-large",
                "title": "Response too large",
                "status": 503,
                "detail": "Computed response exceeds the cache safety limit",
                "instance": request.url.path,
                "code": "CACHE_VALUE_TOO_LARGE",
                "request_id": getattr(request.state, "request_id", str(uuid.uuid4())),
            },
            status_code=503,
        )

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> ORJSONResponse:
        detail = exc.detail if isinstance(exc.detail, dict) else {"message": str(exc.detail)}
        code = str(detail.get("code", _status_code_name(exc.status_code)))
        request.state.error_code = code
        body = {
            "type": f"https://uttg.example/problems/{code.lower().replace('_', '-')}",
            "title": _title(code),
            "status": exc.status_code,
            "detail": detail.get("message", _title(code)),
            "instance": request.url.path,
            "code": code,
            "request_id": getattr(request.state, "request_id", str(uuid.uuid4())),
        }
        return ORJSONResponse(body, status_code=exc.status_code, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> ORJSONResponse:
        request.state.error_code = "VALIDATION_ERROR"
        body = {
            "type": "https://uttg.example/problems/validation-error",
            "title": "Validation error",
            "status": 422,
            "detail": "Request parameters or body failed validation",
            "instance": request.url.path,
            "code": "VALIDATION_ERROR",
            "request_id": getattr(request.state, "request_id", str(uuid.uuid4())),
            "errors": exc.errors(),
        }
        return ORJSONResponse(body, status_code=422)


def _status_code_name(status_code: int) -> str:
    return {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        413: "PAYLOAD_TOO_LARGE",
        422: "VALIDATION_ERROR",
        429: "RATE_LIMIT_EXCEEDED",
        503: "SERVICE_UNAVAILABLE",
        504: "UPSTREAM_TIMEOUT",
    }.get(status_code, "REQUEST_FAILED")


def _title(code: str) -> str:
    return code.replace("_", " ").capitalize()
