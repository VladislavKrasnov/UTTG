from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from core.capabilities import _UNAVAILABLE_PATHS, providers_for_tag, tag_enabled


def custom_openapi(app: FastAPI) -> dict[str, Any]:
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=(
            f"{app.description}\n\n"
            "Repository: https://github.com/VladislavKrasnov/UTTG\n\n"
            "Author: Vladislav Krasnov — https://github.com/VladislavKrasnov"
        ),
        routes=app.routes,
        contact={
            "name": "Vladislav Krasnov",
            "url": "https://github.com/VladislavKrasnov",
        },
        license_info={
            "name": "Apache License 2.0",
            "identifier": "Apache-2.0",
        },
    )

    filtered_paths: dict[str, Any] = {}
    for path, path_item in schema.get("paths", {}).items():
        if path in _UNAVAILABLE_PATHS:
            continue
        filtered_operations: dict[str, Any] = {}
        for method, operation in path_item.items():
            tags = operation.get("tags", [])
            if not all(tag_enabled(tag) for tag in tags):
                continue
            providers = sorted({provider for tag in tags for provider in providers_for_tag(tag)})
            operation["x-uttg-provider-count"] = len(providers)
            operation["x-uttg-providers"] = providers
            operation["x-uttg-resilience"] = (
                "high" if len(providers) >= 2 else "limited" if providers else "internal"
            )
            filtered_operations[method] = operation
        if filtered_operations:
            filtered_paths[path] = filtered_operations

    schema["paths"] = filtered_paths
    app.openapi_schema = schema
    return schema
