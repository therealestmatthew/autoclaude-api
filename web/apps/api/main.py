"""FastAPI app factory + entry point.

`uv run autoclaude-api` calls `serve()` below. Tests build an app via
`create_app(repo_root=...)` and use FastAPI's TestClient.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .cache import CachedIndex, get_cached_index
from .routers import (
    catalog,
    conventions,
    engagements,
    queue,
    search,
    stats,
    threads,
)
from .routers.deps import get_index
from .settings import Settings, get_settings


def create_app(
    *,
    repo_root: Path | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    """Build a FastAPI app. Test code passes its own `repo_root` to override
    the env-driven default; production passes nothing and gets `get_settings()`.
    """
    cfg = settings or get_settings()
    if repo_root is not None:
        cfg = Settings(
            repo_root=repo_root.resolve(),
            host=cfg.host,
            port=cfg.port,
            cors_origins=cfg.cors_origins,
            log_level=cfg.log_level,
        )

    app = FastAPI(
        title="autoclaude web command center",
        version=stats.API_VERSION,
        description=(
            "Read-only view over the autoclaude repo. "
            "Markdown is canonical; this API is a derived index. "
            "See /docs/plans/phase-8-web-command-center.md."
        ),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(cfg.cors_origins),
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
        allow_credentials=False,
    )

    # Pin the index to the configured repo root via a dependency override so
    # tests can swap repos cleanly.
    def _scoped_index() -> CachedIndex:
        return get_cached_index(cfg.repo_root)

    app.dependency_overrides[get_index] = _scoped_index

    app.include_router(stats.router)
    app.include_router(catalog.router)
    app.include_router(queue.router)
    app.include_router(engagements.router)
    app.include_router(conventions.router)
    app.include_router(threads.router)
    app.include_router(search.router)

    return app


# Module-level ASGI app for `uvicorn web.apps.api.main:app` deployments.
app = create_app()


def serve() -> None:
    """Console-script entry point. Reads settings, calls uvicorn.run()."""
    import uvicorn

    cfg = get_settings()
    uvicorn.run(
        "web.apps.api.main:app",
        host=cfg.host,
        port=cfg.port,
        log_level=cfg.log_level,
        reload=False,
    )


if __name__ == "__main__":  # pragma: no cover
    serve()
