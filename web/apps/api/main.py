"""FastAPI app factory + entry point.

`uv run autoclaude-api` calls `serve()` below. Tests build an app via
`create_app(repo_root=...)` and use FastAPI's TestClient.

8.2: the app boots with a DB-backed `CachedIndex`. On startup it (optionally)
runs `alembic upgrade head` and then drives an initial sync so the first
request doesn't pay a cold-walk penalty. A polling reconciler runs every
`AUTOCLAUDE_INDEX_RECONCILE_INTERVAL` seconds while the app is up; setting
the interval to `0` disables the loop (useful in tests).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .cache import CachedIndex, get_cached_index
from .db import make_engine, make_session_factory, migrations_dir, resolve_dsn
from .routers import (
    catalog,
    conventions,
    engagements,
    proposals,
    queue,
    search,
    stats,
    threads,
    writes,
)
from .routers.deps import get_index
from .settings import Settings, get_settings

logger = logging.getLogger(__name__)


def _alembic_config(dsn: str) -> AlembicConfig:
    cfg = AlembicConfig(str(migrations_dir() / "alembic.ini"))
    cfg.set_main_option("script_location", str(migrations_dir()))
    cfg.set_main_option("sqlalchemy.url", dsn)
    return cfg


def _build_cached_index(cfg: Settings) -> CachedIndex:
    """Construct a `CachedIndex` honoring the configured DSN.

    A bare `get_cached_index(repo_root)` resolves a DSN from env; tests
    sometimes need to inject one explicitly via `Settings.index_dsn`. We
    prefer the explicit DSN when present."""
    if cfg.index_dsn:
        engine = make_engine(cfg.index_dsn)
        factory = make_session_factory(engine)
        return CachedIndex(cfg.repo_root, engine=engine, session_factory=factory)
    return get_cached_index(cfg.repo_root)


async def _reconciler_loop(index: CachedIndex, interval: float) -> None:
    """Background task that periodically resyncs the DB from the repo."""
    if interval <= 0:
        return
    while True:
        try:
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            return
        try:
            await asyncio.to_thread(index.sync)
        except Exception:  # noqa: BLE001 — best-effort background loop
            logger.exception("reconciler sync failed; continuing")


def _maybe_migrate(cfg: Settings) -> None:
    """If `AUTOCLAUDE_INDEX_AUTO_MIGRATE` is on, run `alembic upgrade head`."""
    if not cfg.auto_migrate:
        return
    dsn = cfg.index_dsn or resolve_dsn(cfg.repo_root)
    alembic_command.upgrade(_alembic_config(dsn), "head")


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
            index_dsn=cfg.index_dsn,
            reconcile_interval=cfg.reconcile_interval,
            auto_migrate=cfg.auto_migrate,
        )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        _maybe_migrate(cfg)
        # Drive an initial sync so the first request doesn't pay a cold walk.
        # `index.sync()` is idempotent so this is cheap on a warm DB.
        try:
            await asyncio.to_thread(_scoped_index().sync)
        except Exception:  # noqa: BLE001
            logger.exception("initial sync failed; continuing without it")
        task = asyncio.create_task(
            _reconciler_loop(_scoped_index(), cfg.reconcile_interval)
        )
        try:
            yield
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    app = FastAPI(
        title="autoclaude web command center",
        version=stats.API_VERSION,
        description=(
            "Read-only view over the autoclaude repo. "
            "Markdown is canonical; this API is a derived index. "
            "See /docs/plans/phase-8-web-command-center.md."
        ),
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(cfg.cors_origins),
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
        allow_credentials=False,
    )

    # Build a per-app cached index instance and pin it to the dependency so
    # tests can swap repos cleanly without leaking the process singleton.
    index = _build_cached_index(cfg)

    def _scoped_index() -> CachedIndex:
        return index

    app.dependency_overrides[get_index] = _scoped_index

    app.include_router(stats.router)
    app.include_router(catalog.router)
    app.include_router(queue.router)
    app.include_router(engagements.router)
    app.include_router(conventions.router)
    app.include_router(threads.router)
    app.include_router(search.router)
    app.include_router(writes.router)
    app.include_router(proposals.router)

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
