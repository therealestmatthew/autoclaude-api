"""Environment-driven configuration for the FastAPI app.

Single source of truth for "where is the repo", "what port", "what origins
should CORS accept", and (8.2) the persistent index DSN + reconciler cadence.
Read from env vars with sensible defaults so the runbook gives a clean
`uv run autoclaude-api` story without a config file.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _repo_root_default() -> Path:
    """Walk up from this file until we find the repo root marker.

    The marker is `pyproject.toml`. Falling back to CWD lets a developer run
    the app from anywhere as long as `AUTOCLAUDE_REPO_ROOT` is set.
    """
    here = Path(__file__).resolve()
    for parent in (here, *here.parents):
        if (parent / "pyproject.toml").is_file() and (parent / "scout").is_dir():
            return parent
    return Path.cwd()


@dataclass(frozen=True)
class Settings:
    repo_root: Path
    host: str
    port: int
    cors_origins: tuple[str, ...]
    log_level: str
    # 8.2 — persistent index knobs.
    index_dsn: str | None
    reconcile_interval: float
    auto_migrate: bool

    @classmethod
    def from_env(cls) -> Settings:
        repo_root = Path(
            os.environ.get("AUTOCLAUDE_REPO_ROOT", str(_repo_root_default()))
        ).resolve()
        host = os.environ.get("AUTOCLAUDE_API_HOST", "127.0.0.1")
        port = int(os.environ.get("AUTOCLAUDE_API_PORT", "8080"))
        origins_env = os.environ.get(
            "AUTOCLAUDE_API_CORS_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000,"
            "http://localhost:3001,http://127.0.0.1:3001",
        )
        cors_origins = tuple(o.strip() for o in origins_env.split(",") if o.strip())
        log_level = os.environ.get("AUTOCLAUDE_API_LOG_LEVEL", "info")

        dsn = os.environ.get("AUTOCLAUDE_INDEX_DSN", "").strip() or None
        reconcile_interval = float(
            os.environ.get("AUTOCLAUDE_INDEX_RECONCILE_INTERVAL", "60")
        )
        # Default ON: dev story is "uv run autoclaude-api just works on a
        # fresh checkout." Production / CI can set it to 0 to keep schema
        # migrations as an explicit deploy step.
        auto_migrate = os.environ.get("AUTOCLAUDE_INDEX_AUTO_MIGRATE", "1").strip() in {
            "1",
            "true",
            "yes",
            "on",
        }

        return cls(
            repo_root=repo_root,
            host=host,
            port=port,
            cors_origins=cors_origins,
            log_level=log_level,
            index_dsn=dsn,
            reconcile_interval=reconcile_interval,
            auto_migrate=auto_migrate,
        )


_settings: Settings | None = None


def get_settings() -> Settings:
    """Singleton accessor used by FastAPI dependency injection."""
    global _settings
    if _settings is None:
        _settings = Settings.from_env()
    return _settings


def reset_settings() -> None:
    """Test hook — clears the singleton so the next call re-reads env."""
    global _settings
    _settings = None
